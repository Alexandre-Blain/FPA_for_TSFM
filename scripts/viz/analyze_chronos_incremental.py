"""Offline, prospectively specified H1/H2 evaluation; never starts a model."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'code/chronos_fpa'),str(ROOT/'scripts/runs')]
import bootstrap  # noqa: E402,F401
import numpy as np
import pandas as pd

from ensemble_store import read_snapshot
from chronos_discovery import behaviour_codes
from chronos_incremental import future_events,EVENT_NAMES
from chronos_incremental_features import FPA_FEATURES
from chronos_incremental_risk import (ridge_calibrate,risk_metrics,risk_curve,
    bootstrap_delta,paired_block_randomization,hierarchical_indices,holm)
from run_chronos_incremental import load,save,digest,verify_complete,verify_sources,charged_seconds,new_bytes


def clean(obj):
    if isinstance(obj,np.ndarray):return clean(obj.tolist())
    if isinstance(obj,np.generic):return clean(obj.item())
    if isinstance(obj,float) and not np.isfinite(obj):return None
    if isinstance(obj,dict):return {str(k):clean(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)):return [clean(v) for v in obj]
    return obj


def save_clean(path,obj):save(path,clean(obj))


def csv(path,rows):
    frame=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(path,index=False,encoding='utf-8',lineterminator='\n')


def natural_features(paths,context):
    """Exact existing definitions with blocked pair distances to bound RAM."""
    a=np.asarray(paths,float);iqr=float(np.subtract(*np.percentile(context,[75,25])))
    total=0.
    for begin in range(0,len(a),32):
        total+=np.linalg.norm(a[begin:begin+32,None]-a[None,:],axis=2).sum()
    _,counts=np.unique(behaviour_codes(a,context),return_counts=True);p=counts/counts.sum()
    return {'mean_sd_iqr':float(a.std(0,ddof=1).mean()/iqr),
        'interval80_iqr':float(np.mean(np.quantile(a,.9,axis=0)-np.quantile(a,.1,axis=0))/iqr),
        'trajectory_rms_diversity_iqr':float(total/len(a)**2/np.sqrt(32)/iqr),
        'scenario_entropy':float(-np.sum(p*np.log(p))),'scenario_groups':len(counts)}


def metadata_design(windows,training):
    columns=[];arrays=[]
    for field in ('dataset_id','frequency','domain','exposure'):
        categories=sorted({w[field] for w,t in zip(windows,training) if t})
        for category in categories:
            columns.append(field+'='+category)
            arrays.append(np.array([float(w[field]==category) for w in windows]))
    return columns,np.stack(arrays,axis=1)


def verify_selected_source_alignment(run,windows,targets):
    """Verify C512 and the next H32 values against pinned original Parquet.

    Called only AFTER the analysis freeze. A mismatch stops analysis; it never
    triggers origin reselection, outcome filtering or a replacement window.
    """
    import pyarrow.parquet as pq
    by_file={};checked=[]
    for w in windows:by_file.setdefault(w['source_file'],{})[w['series_id']]=w
    with np.load(run/'contexts.npz') as contexts:
        for filename,expected in by_file.items():
            source=ROOT/filename
            if digest(source)!=next(iter(expected.values()))['source_sha256']:
                raise ValueError('Pinned source file changed')
            remaining=set(expected)
            for batch in pq.ParquetFile(source).iter_batches(batch_size=1,columns=['id','target','timestamp']):
                source_id=batch.column(0)[0].as_py()
                if source_id not in expected:continue
                w=expected[source_id];origin=w['forecast_origin'];wid=w['window_id']
                values=batch.column(1)[0].values
                context=values.slice(origin-512,512).to_numpy(zero_copy_only=False).astype(np.float32)
                target=values.slice(origin,32).to_numpy(zero_copy_only=False).astype(np.float32)
                np.testing.assert_array_equal(contexts[wid],context)
                np.testing.assert_array_equal(targets[wid],target)
                dates=batch.column(2)[0].values.slice(origin,32).to_numpy(zero_copy_only=False).astype('datetime64[ns]').astype(np.int64)
                if int(dates[0])!=w['target_start_ns'] or int(dates[-1])!=w['target_end_ns']:
                    raise ValueError('Origin/target calendar metadata mismatch')
                checked.append(wid);remaining.remove(source_id)
                if not remaining:break
            if remaining:raise ValueError('Original source identities missing: '+str(remaining))
    save(run/'target_source_alignment.json',{'status':'passed','checked_original_windows':len(checked),
        'window_ids':checked,'rule':'context[source origin-512:origin], target[source origin:origin+32], exact float32 copy, same calendar endpoints'})


def h1_inputs(run,windows,targets,out):
    rows=[];features=[];extra_features=[];costs=[];forecast_rows=[];cheap=[]
    for w in windows:
        wid=w['window_id'];marker,snapshot=verify_complete(run,'H1',wid)
        fs=load(run/'H1'/wid/'features.json');features.append(fs)
        naturals=sorted([(m,a) for m,a in snapshot['records'] if m['identity']['role']=='natural'],key=lambda t:t[0]['identity']['block'])
        if [len(a['values']) for _,a in naturals]!=[20,20,20]:raise ValueError('Missing independent N60 natural blocks')
        a=np.concatenate([a['values'] for _,a in naturals]);context=naturals[0][1]['context'];greedy=naturals[0][1]['greedy_values']
        target=targets[wid];iqr=fs['context_iqr'];seasonal=fs['seasonal_scale']
        forks=[f for f in load(run/'H1'/wid/'forks.json') if f['b'] in (0,4,9)]
        jumps=[];weighted_rms=[];direct_mass=0.
        for f in forks:
            values=np.array([f['candidate_values'][str(t)] for t in f['selected_tokens']])
            weights=np.array([f['probabilities'][str(t)] for t in f['selected_tokens']])
            jump=(values-greedy[f['b']])/iqr;jumps.extend(abs(jump))
            weighted_rms.append(np.sqrt(np.sum(weights*jump**2)/weights.sum()))
            if f['b']==9:direct_mass=float(weights[(values<=context[-1]-iqr)|(values>=context[-1]+iqr)].sum())
        cheap.append({'cheap_selected_J_max':float(max(jumps)),
            'cheap_selected_q_J_RMS':float(np.mean(weighted_rms)),
            'cheap_b9_selected_direct_excursion_mass':direct_mass,
            'cheap_natural_SD_seasonal':fs['mean_sd_iqr']*iqr/seasonal,
            'cheap_natural_I80_seasonal':fs['interval80_iqr']*iqr/seasonal,
            'cheap_natural_diversity_seasonal':fs['trajectory_rms_diversity_iqr']*iqr/seasonal})
        point=a.mean(0);available=bool(np.isfinite(target).all())
        mae=float(np.mean(abs(point-target))) if available else np.nan
        potentially_exposed=max(0,min(32,w['documented_temporal_boundary']-w['forecast_origin'])) if w['exposure']=='in_domain' else 0
        row={k:w[k] for k in ('window_id','dataset_id','series_id','split','frequency','domain','exposure','forecast_origin','lag')}
        row.update(target_available=available,MAE=mae,MASE=mae/seasonal,MAE_IQR=mae/iqr,
            median_MAE=float(np.mean(abs(np.median(a,axis=0)-target))) if available else np.nan,
            greedy_MAE=float(np.mean(abs(greedy-target))) if available else np.nan,
            context_iqr=iqr,seasonal_scale=seasonal,matched_cost_member=w['matched_cost_member'],
            potentially_pretraining_exposed_target_fraction=potentially_exposed/32)
        rows.append(row)
        for t in range(32):forecast_rows.append({'window_id':wid,'horizon':t,'mean':point[t],
            'median':np.median(a,axis=0)[t],'greedy':greedy[t],'target':target[t]})
        extra=[a['values'] for m,a in snapshot['records'] if m['identity']['role']=='matched_natural']
        extra_feature_start=time.perf_counter()
        extra_features.append({**fs,**natural_features(np.concatenate([a,*extra]),context)} if extra else fs)
        extra_feature_seconds=time.perf_counter()-extra_feature_start
        cost={'window_id':wid,'dataset_id':w['dataset_id'],'model_loading_seconds':marker['worker_model_loading_seconds'],
            'window_seconds':marker['window_seconds'],'common_setup_seconds':marker['setup_seconds'],
            'natural_seconds':0.,'FPA_generation_seconds':0.,'SGA_replay_seconds':0.,'SGA_graph_seconds':0.,'extra_natural_seconds':0.}
        for m,_ in snapshot['records']:
            meta=m['metadata'];role=m['identity']['role']
            if role=='natural':cost['natural_seconds']+=meta['generation_seconds']
            if role in ('conditional','residual','null'):cost['FPA_generation_seconds']+=meta['generation_seconds']
            if role=='matched_natural':cost['extra_natural_seconds']+=meta['generation_seconds']
            cost['SGA_replay_seconds']+=meta.get('sga_replay_seconds',0.)
            cost['SGA_graph_seconds']+=meta.get('sga_graph_seconds',0.)
        cost['all_feature_seconds']=load(run/'H1'/wid/'feature_cost.json')['all_feature_seconds']
        cost['extra_natural_feature_seconds']=extra_feature_seconds
        shared=cost['common_setup_seconds']+cost['model_loading_seconds']+cost['natural_seconds']
        sga=cost['SGA_replay_seconds']+cost['SGA_graph_seconds'];fpa=cost['FPA_generation_seconds']+cost['all_feature_seconds']
        for method,seconds in [('M0',shared),('M1',shared+sga),('M2',shared+fpa),('M3',shared+sga+fpa)]:cost[method+'_seconds']=seconds
        cost['extra_MC_to_FPA_actual_cost_ratio']=(cost['extra_natural_seconds']+extra_feature_seconds)/fpa if extra else np.nan
        costs.append(cost)
    # All process startup, failed attempts and filesystem overhead remain in
    # actual phase totals; component tables are not standalone speed claims.
    phase_receipts=[load(p) for p in (run/'attempts').glob('*.json')]
    phase_seconds=sum(r['elapsed_seconds'] for r in phase_receipts if r['phase']=='H1')
    overhead=max(0.,phase_seconds-sum(c['window_seconds'] for c in costs))/len(costs)
    for cost in costs:
        cost['phase_subprocess_seconds']=phase_seconds
        cost['allocated_process_startup_and_failure_seconds']=overhead
        measured=sum(cost[k] for k in ('common_setup_seconds','natural_seconds','FPA_generation_seconds',
            'SGA_replay_seconds','SGA_graph_seconds','extra_natural_seconds','all_feature_seconds'))
        cost['unallocated_collection_overhead_seconds']=max(0.,cost['window_seconds']-measured)
        cost['actual_joint_collection_end_to_end_seconds']=cost['window_seconds']+overhead
    frame=pd.DataFrame(rows);csv(out/'H1_forecast_errors.csv',frame)
    csv(out/'H1_forecasts_by_horizon.csv',forecast_rows);csv(out/'H1_features.csv',[{**r,**f} for r,f in zip(rows,features)])
    csv(out/'H1_actual_costs.csv',costs)
    csv(out/'H1_predeclared_cheap_controls.csv',[{'window_id':w['window_id'],**f} for w,f in zip(windows,cheap)])
    return frame,features,extra_features,pd.DataFrame(costs),cheap


def evaluate_h1(run,windows,targets,out,config):
    frame,features,extra,costs,cheap=h1_inputs(run,windows,targets,out)
    train=frame['split'].eq('train').to_numpy();validation=frame['split'].eq('validation').to_numpy()
    within=frame['split'].eq('test').to_numpy();ood=frame['split'].eq('ood_test').to_numpy()
    # Cohort uses the string stored by its preparer. Fail closed on a typo.
    if not ood.any():ood=frame['dataset_id'].eq('monash_weather').to_numpy()
    if (ood & (train|validation|within)).any():raise ValueError('OOD dataset entered development partitions')
    valid=frame['target_available'].to_numpy()
    meta_names,metadata=metadata_design(windows,train)
    conventional=[k for k in features[0] if k not in FPA_FEATURES and k!='sga']
    definitions={'M0':conventional,'M1':conventional+['sga'],
        'M2':conventional+list(FPA_FEATURES),'M3':conventional+['sga']+list(FPA_FEATURES),
        'M1_cheap':conventional+['sga'],'M3_cheap':conventional+['sga']+list(FPA_FEATURES),
        'scale_metadata':['seasonal_scale','context_iqr','seasonal_over_iqr','iqr_over_seasonal']}
    metrics=[];predictions=[];fits=[];all_scores={};comparisons=[];formal=[];learning_costs=[];influence=[]
    subset=frame['matched_cost_member'].to_numpy()
    for population,keep in [('full',np.ones(len(frame),bool)),('matched_subset',subset)]:
        for target_name in ('MASE','MAE_IQR'):
            loss=frame[target_name].to_numpy();mtrain=train&keep&valid;mval=validation&keep&valid
            model_names=list(definitions) if population=='full' else ['M0','M1','M2','M3','M1_extra_MC']
            for method in model_names:
                names=definitions['M1'] if method=='M1_extra_MC' else definitions[method]
                source=extra if method=='M1_extra_MC' else features
                x=np.column_stack([np.array([[float(f[k]) for k in names] for f in source]),metadata])
                augmented=list(cheap[0]) if method.endswith('_cheap') else []
                if augmented:x=np.column_stack([x,np.array([[c[k] for k in augmented] for c in cheap])])
                learning_start=time.perf_counter()
                fit=ridge_calibrate(x[mtrain],loss[mtrain],x[mval],loss[mval],x,
                    config['risk_ridge_alphas']);score=fit['log_prediction']
                learning_costs.append({'population':population,'target':target_name,'method':method,
                    'training_validation_prediction_seconds':time.perf_counter()-learning_start,
                    'feature_count':x.shape[1]})
                all_scores[(population,target_name,method)]=score
                fits.append({'population':population,'target':target_name,'method':method,
                    'features':names+meta_names+augmented,'train_N':int(mtrain.sum()),'validation_N':int(mval.sum()),**fit})
                for i,w in enumerate(windows):
                    if keep[i]:predictions.append({'window_id':w['window_id'],'dataset_id':w['dataset_id'],
                        'series_id':w['series_id'],'split':w['split'],'population':population,
                        'target':target_name,'method':method,'score_log_loss':score[i],
                        'predicted_loss':np.expm1(np.clip(score[i],0,30)),'actual_loss':loss[i],
                        'alpha':fit['alpha'],'target_available':bool(valid[i])})
                groups=[('within_test',within),('OOD_weather',ood)]
                groups += [(dataset,frame['dataset_id'].eq(dataset).to_numpy()&within)
                    for dataset in frame.loc[within,'dataset_id'].unique()]
                for group,mask in groups:
                    ix=mask&keep&valid
                    if ix.sum()<2:continue
                    metrics.append({'population':population,'target':target_name,'group':group,'method':method,
                        'alpha':fit['alpha'],**risk_metrics(score[ix],loss[ix],score[ix])})
                    if target_name=='MASE' and group not in ('within_test','OOD_weather'):
                        metrics.append({'population':population,'target':'raw_MAE_using_MASE_scores','group':group,'method':method,
                            'alpha':fit['alpha'],**risk_metrics(score[ix],frame.loc[ix,'MAE'].to_numpy())})
            raw={'raw_SGA':np.array([f['sga'] for f in features]),
                'raw_FPA_W1':np.array([f['F1_mean_W1'] for f in features]),
                'raw_interval80':np.array([f['interval80_iqr'] for f in features]),
                'raw_seasonal_scale':np.array([f['seasonal_scale'] for f in features]),
                'raw_context_IQR':np.array([f['context_iqr'] for f in features]),
                'raw_seasonal_over_IQR':np.array([f['seasonal_over_iqr'] for f in features]),
                'raw_IQR_over_seasonal':np.array([f['iqr_over_seasonal'] for f in features])}
            if population=='full':
                for method,score in raw.items():
                    for group,mask in [('within_test',within),('OOD_weather',ood)]:
                        ix=mask&valid
                        if ix.sum()<2:continue
                        metrics.append({'population':population,'target':target_name,'group':group,'method':method,
                            **risk_metrics(score[ix],loss[ix])})
            for group,mask in [('within_test',within),('OOD_weather',ood)]:
                ix=mask&keep&valid
                if ix.sum()<2:continue
                for left,right in ([('M3','M1'),('M2','M0'),('M3_cheap','M1_cheap')] if population=='full' else [('M3','M1'),('M3','M1_extra_MC')]):
                    a=all_scores[(population,target_name,left)][ix];b=all_scores[(population,target_name,right)][ix]
                    am=risk_metrics(a,loss[ix]);bm=risk_metrics(b,loss[ix]);groups=frame.loc[ix,'dataset_id'].to_numpy()
                    comparison={'population':population,'target':target_name,'group':group,
                        'comparison':left+'-'+right,'N':int(ix.sum()),
                        'delta_NEAURC':am['NEAURC']-bm['NEAURC'],'delta_AURC':am['AURC']-bm['AURC'],
                        'relative_AURC_reduction':1-am['AURC']/bm['AURC']}
                    if left.startswith('M3'):comparison.update(bootstrap_delta(a,b,loss[ix],groups,repeats=config['bootstrap_replicates']))
                    comparisons.append(comparison)
                    if population=='full' and target_name=='MASE' and right=='M1':
                        formal.append({'name':'H1_'+group,**paired_block_randomization(a,b,loss[ix],groups)})
                        indices=np.flatnonzero(ix)
                        for omitted in indices:
                            keep_index=indices[indices!=omitted]
                            left_metrics=risk_metrics(all_scores[(population,target_name,left)][keep_index],loss[keep_index])
                            right_metrics=risk_metrics(all_scores[(population,target_name,right)][keep_index],loss[keep_index])
                            influence.append({'group':group,'omitted_window_id':windows[omitted]['window_id'],
                                'omitted_dataset_id':windows[omitted]['dataset_id'],'omitted_actual_loss':loss[omitted],
                                'delta_NEAURC_without_source':left_metrics['NEAURC']-right_metrics['NEAURC'],
                                'delta_AURC_without_source':left_metrics['AURC']-right_metrics['AURC'],
                                'fitted_models':'held fixed; source influence on evaluation, no label-based reselection'})
    csv(out/'H1_model_metrics.csv',metrics);csv(out/'H1_out_of_sample_predictions.csv',predictions)
    csv(out/'H1_learning_costs.csv',learning_costs)
    save_clean(out/'H1_fitted_models.json',fits);save_clean(out/'H1_incremental_comparisons.json',comparisons)
    coefficients=[]
    for fit in fits:
        for name,coef,mean,scale in zip(fit['features'],fit['coefficient'],fit['mean'],fit['scale']):
            coefficients.append({'population':fit['population'],'target':fit['target'],'method':fit['method'],
                'feature':name,'standardized_coefficient':coef,'training_mean':mean,'training_SD':scale,
                'intercept_log_loss':fit['intercept'],'alpha':fit['alpha']})
    csv(out/'H1_ridge_coefficients.csv',coefficients);csv(out/'H1_source_influence.csv',influence)
    csv(out/'H1_incremental_comparisons.csv',comparisons)
    feature_associations=[]
    for target in ('MASE','MAE_IQR'):
        for group,mask in [('train',train),('within_test',within),('OOD_weather',ood)]:
            ix=mask&valid
            for name in [*FPA_FEATURES,'sga','interval80_iqr','seasonal_over_iqr']:
                score=np.array([f[name] for f in features])
                feature_associations.append({'target':target,'group':group,'feature':name,
                    'Spearman':risk_metrics(score[ix],frame.loc[ix,target].to_numpy())['Spearman'],
                    'interpretation':'descriptive fixed feature catalogue; no feature selection'})
    csv(out/'H1_feature_associations.csv',feature_associations)
    return {'frame':frame,'features':features,'scores':all_scores,'costs':costs,
        'comparisons':comparisons,'metrics':metrics,'formal':formal}


def wilson(count,n,z=1.959963984540054):
    p=np.asarray(count,float)/n;denominator=1+z*z/n
    center=(p+z*z/(2*n))/denominator
    radius=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return np.maximum(0,center-radius),np.minimum(1,center+radius)


def dataset_source_ci(values,groups,seed=2026112635,repeats=999):
    rng=np.random.default_rng(seed);values=np.asarray(values,float)
    return np.quantile([values[hierarchical_indices(groups,rng)].mean() for _ in range(repeats)],[.025,.975])


def evaluate_h2(run,windows,targets,out,config):
    rows=[];reference_rows=[];taskb=[];feasibility=[];window_cost=[]
    for w in windows:
        wid=w['window_id'];marker,snapshot=verify_complete(run,'H2',wid)
        d=load(run/'H2'/wid/'event_estimates.json');p=np.array(d['reference']['probability'])
        n=d['reference_N'];counts=np.sum(d['reference_block_counts'],axis=0);lo,hi=wilson(counts,n)
        receipts=[load(p) for p in (run/'attempts').glob('*.json')]
        receipt=next(r for r in receipts if r['phase']=='H2' and r.get('exit_code')==0 and r['windows']==[wid])
        shared_setup_and_startup=marker['setup_seconds']+max(0.,receipt['elapsed_seconds']-marker['window_seconds'])
        ref_var=p*(1-p)/(n-1);ref_raw=next(a for m,a in snapshot['records'] if m['identity']['role']=='h2_reference')
        actual=targets[wid];actual_valid=bool(np.isfinite(actual).all())
        actual_events=future_events(actual[None],ref_raw['context'],ref_raw['greedy_values'])[0] if actual_valid else None
        for event,name in enumerate(EVENT_NAMES):
            reference_rows.append({'window_id':wid,'dataset_id':w['dataset_id'],'series_id':w['series_id'],'event':name,
                'reference_probability':p[event],'N':n,'successes':counts[event],'wilson_lo':lo[event],'wilson_hi':hi[event],
                'reference_variance_estimate':ref_var[event],
                'zero_count_95pct_one_sided_upper':1-.05**(1/n) if counts[event]==0 else np.nan,
                'block0_probability':d['reference_block_counts'][0][event]/d['reference_block_N'][0],
                'block1_probability':d['reference_block_counts'][1][event]/d['reference_block_N'][1],
                'actual_event':int(actual_events[event]) if actual_valid else np.nan,'actual_available':actual_valid})
        for r in d['rows']:
            if not r['feasible']:
                feasibility.append({k:r[k] for k in ('window_id','dataset_id','method','anchor','rep','feasible')});continue
            feasibility.append({k:r[k] for k in ('window_id','dataset_id','method','anchor','rep','feasible')})
            for e,name in enumerate(EVENT_NAMES):
                estimate=r['probability'][e]
                row={k:r.get(k) for k in ('window_id','dataset_id','series_id','rep','method','anchor','matched_to','N',
                    'production_seconds','pilot_seconds_charged','variable_seconds','common_setup_seconds',
                    'actual_cost_ratio_to_method','within_25pct_actual_cost','matching_capped')}
                row.update(event=name,estimate=estimate,reference=p[e],reference_variance=ref_var[e],
                    shared_setup_and_startup_seconds=shared_setup_and_startup,
                    accounted_end_to_end_model_seconds=shared_setup_and_startup+r['variable_seconds']+r.get('aggregation_seconds',0.),
                    absolute_error=abs(estimate-p[e]),squared_error=(estimate-p[e])**2,
                    reference_corrected_squared_error=(estimate-p[e])**2-ref_var[e],
                    estimated_variance=r['variance'][e],interval_lo=r['lo'][e],interval_hi=r['hi'][e],
                    reference_point_in_interval=r['lo'][e]<=p[e]<=r['hi'][e],
                    interval_overlaps_reference_CI=r['lo'][e]<=hi[e] and r['hi'][e]>=lo[e],
                    prevalence_regime='<.05' if p[e]<.05 else '.05-.25' if p[e]<.25 else '.25-.75' if p[e]<.75 else '>=.75',
                    relative_error=abs(estimate-p[e])/p[e] if p[e]>=.01 else np.nan)
                rows.append(row)
        window_cost.append({'window_id':wid,'dataset_id':w['dataset_id'],
            'window_seconds':marker['window_seconds'],'model_loading_seconds':marker['worker_model_loading_seconds'],
            'reference_seconds':d['reference_seconds'],'repetitions':marker['h2_repetitions'],
            'paths':marker['paths'],'ensembles':marker['ensembles']})
    frame=pd.DataFrame(rows);refs=pd.DataFrame(reference_rows)
    csv(out/'H2_event_estimates.csv',frame);csv(out/'H2_independent_references.csv',refs)
    csv(out/'H2_feasibility.csv',feasibility);csv(out/'H2_window_costs.csv',window_cost)
    # Average events, then repetitions, then original sources. Never count four
    # events or ten repetitions as four/ten independent population identities.
    source_columns=['window_id','dataset_id','method','anchor','matched_to']
    source=frame.groupby(source_columns,dropna=False).agg(MSE=('squared_error','mean'),
        MAE=('absolute_error','mean'),reference_corrected_MSE=('reference_corrected_squared_error','mean'),
        seconds=('variable_seconds','mean'),N=('N','mean'),actual_cost_ratio=('actual_cost_ratio_to_method','mean'),
        matched_fraction=('within_25pct_actual_cost','mean'),reference_agreement=('reference_point_in_interval','mean')).reset_index()
    csv(out/'H2_source_averages.csv',source)
    summaries=[]
    for (method,anchor,matched),group in source.groupby(['method','anchor','matched_to'],dropna=False):
        summaries.append({'method':method,'anchor':anchor,'matched_to':matched,'original_sources':len(group),
            'RMSE_to_reference':np.sqrt(group['MSE'].mean()),'MAE_to_reference':group['MAE'].mean(),
            'mean_seconds':group['seconds'].mean(),'median_seconds':group['seconds'].median(),
            'mean_N':group['N'].mean(),'reference_corrected_MSE':group['reference_corrected_MSE'].mean(),
            'mean_actual_cost_ratio':group['actual_cost_ratio'].mean(),'matched_fraction':group['matched_fraction'].mean()})
    csv(out/'H2_budget_summary.csv',summaries)
    comparisons=[];source_deltas=[]
    for method in config['h2_methods']:
        if method=='MC':continue
        for anchor in config['h2_budget_anchors']:
            a=source[(source.method==method)&(source.anchor==anchor)]
            b=source[(source.method=='matched_MC')&(source.matched_to==method)&(source.anchor==anchor)]
            pairs=a.merge(b,on=['window_id','dataset_id','anchor'],suffixes=('_method','_MC'))
            if pairs.empty:continue
            delta=(pairs.MSE_method-pairs.MSE_MC).to_numpy()
            for (_,pair),difference in zip(pairs.iterrows(),delta):
                source_deltas.append({'window_id':pair.window_id,'dataset_id':pair.dataset_id,'method':method,'anchor':anchor,
                    'MSE_method':pair.MSE_method,'MSE_MC':pair.MSE_MC,'delta_MSE':difference,
                    'method_seconds':pair.seconds_method,'matched_MC_seconds':pair.seconds_MC,
                    'MC_to_method_time_ratio':pair.actual_cost_ratio_MC,'matched_fraction':pair.matched_fraction_MC})
            groups=pairs.dataset_id.to_numpy();ci=dataset_source_ci(delta,groups,repeats=config['bootstrap_replicates'])
            comparisons.append({'method':method,'anchor':anchor,'N_sources':len(pairs),
                'MSE_method':pairs.MSE_method.mean(),'MSE_MC':pairs.MSE_MC.mean(),'delta_MSE':delta.mean(),
                'delta_MSE_CI95':ci,'RMSE_ratio':np.sqrt(pairs.MSE_method.mean()/pairs.MSE_MC.mean()),
                'source_win_fraction':float((delta<0).mean()),'mean_actual_MC_to_method_time_ratio':pairs.actual_cost_ratio_MC.mean(),
                'matching_fraction':pairs.matched_fraction_MC.mean()})
    csv(out/'H2_paired_comparisons.csv',comparisons);save_clean(out/'H2_paired_comparisons.json',comparisons)
    csv(out/'H2_source_deltas.csv',source_deltas)
    # Repeat the fixed primary comparison against BOTH independent reference
    # blocks; no policy/threshold/allocation is selected from this sensitivity.
    reference_sensitivity=[]
    for block in (0,1):
        r=frame[frame.anchor==480].merge(refs[['window_id','event',f'block{block}_probability']],on=['window_id','event'])
        r['block_squared_error']=(r.estimate-r[f'block{block}_probability'])**2
        for method,matched in [('first_deviation_neyman_cost',None),('matched_MC','first_deviation_neyman_cost')]:
            g=r[r.method==method]
            if matched:g=g[g.matched_to==matched]
            source_means=g.groupby('window_id').block_squared_error.mean()
            reference_sensitivity.append({'reference_block':block,'reference_N':1000,'method':method,
                'N_originals':len(source_means),'MSE':source_means.mean()})
    csv(out/'H2_reference_block_sensitivity.csv',reference_sensitivity)
    primary=next((x for x in comparisons if x['method']=='first_deviation_neyman_cost' and x['anchor']==480),None)
    primary_a=source[(source.method=='first_deviation_neyman_cost')&(source.anchor==480)]
    primary_b=source[(source.method=='matched_MC')&(source.matched_to=='first_deviation_neyman_cost')&(source.anchor==480)]
    paired=primary_a.merge(primary_b,on=['window_id','dataset_id'],suffixes=('_method','_MC'))
    formal={'name':'H2_primary','one_sided_p':1.,'unit':'dataset','clusters':0}
    if len(paired):
        delta=paired.MSE_method-paired.MSE_MC;cluster=[delta[paired.dataset_id==g].to_numpy() for g in sorted(paired.dataset_id.unique())]
        observed=float(delta.mean());randomized=[]
        for signs in itertools.product([-1,1],repeat=len(cluster)):
            randomized.append(float(np.concatenate([s*a for s,a in zip(signs,cluster)]).mean()))
        formal.update(one_sided_p=float(np.mean(np.array(randomized)<=observed+1e-15)),clusters=len(cluster),
            delta_MSE=observed,randomizations=len(randomized),exhaustive=True,
            assumption='paired sharp exchangeability at whole-dataset block; very few independent datasets')
    # True replication variance only for the preselected repeated windows.
    variances=[]
    for keys,group in frame.groupby(['window_id','dataset_id','method','matched_to','anchor','event'],dropna=False):
        if group['rep'].nunique()<2:continue
        variances.append(dict(zip(['window_id','dataset_id','method','matched_to','anchor','event'],keys),
            rep_N=group['rep'].nunique(),empirical_variance=group['estimate'].var(ddof=1),
            mean_estimator_variance=group['estimated_variance'].mean(),mean_probability=group['estimate'].mean()))
    csv(out/'H2_independent_replication_variance.csv',variances)
    # Task B: each actual source/event counted once, averaging its repeats.
    for keys,group in frame.groupby(['window_id','dataset_id','method','matched_to','anchor','event'],dropna=False):
        wid,ds,method,matched,anchor,event=keys
        truth=refs[(refs.window_id==wid)&(refs.event==event)].iloc[0]
        if not truth.actual_available:continue
        raw=group['estimate'].mean();prob=float(np.clip(raw,0,1));actual=float(truth.actual_event)
        taskb.append({'window_id':wid,'dataset_id':ds,'method':method,'matched_to':matched,'anchor':anchor,
            'event':event,'probability':prob,'raw_estimate':raw,'clipped_for_TaskB':raw!=prob,
            'actual_event':actual,'Brier':(prob-actual)**2,'repetitions_averaged':len(group)})
    for _,truth in refs.iterrows():
        if truth.actual_available:taskb.append({'window_id':truth.window_id,'dataset_id':truth.dataset_id,
            'method':'independent_reference_N2000','matched_to':None,'anchor':2000,'event':truth.event,
            'probability':truth.reference_probability,'raw_estimate':truth.reference_probability,
            'clipped_for_TaskB':False,'actual_event':truth.actual_event,
            'Brier':(truth.reference_probability-truth.actual_event)**2,'repetitions_averaged':1})
    taskb=pd.DataFrame(taskb);csv(out/'H2_actual_future_Brier.csv',taskb)
    reliability=[]
    for keys,group in taskb.groupby(['method','matched_to','anchor','event'],dropna=False):
        for bin_index in range(5):
            mask=(group.probability>=bin_index/5)&((group.probability<(bin_index+1)/5) if bin_index<4 else (group.probability<=1))
            selected=group[mask]
            if len(selected):reliability.append(dict(zip(['method','matched_to','anchor','event'],keys),
                bin_lower=bin_index/5,N_originals=len(selected),mean_probability=selected.probability.mean(),
                observed_fraction=selected.actual_event.mean(),Brier=selected.Brier.mean(),
                interpretation='exploratory actual-future calibration; at most36 original outcomes per event'))
    csv(out/'H2_reliability_bins.csv',reliability)
    return {'frame':frame,'references':refs,'source':source,'comparisons':comparisons,
        'summaries':summaries,'primary':primary,'formal':formal,'taskb':taskb}


def plotting_interval_errors(center, lower, upper):
    """Nonnegative plotting lengths; tolerate only floating point roundoff.

    A Wilson lower endpoint can round slightly above p=0. This helper changes
    display lengths only; the saved interval and probability are untouched.
    """
    errors=np.array([np.asarray(center)-np.asarray(lower),np.asarray(upper)-np.asarray(center)])
    if not np.isfinite(errors).all() or np.min(errors)<-1e-12:
        raise ValueError('Interval does not contain its point estimate beyond numerical roundoff')
    return np.maximum(0.,errors)


def make_figures(run,out,h1,h2):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':130})
    figs=[];frame=h1['frame'];valid=frame.target_available.to_numpy()
    fig,axes=plt.subplots(2,2,figsize=(10,7))
    for row,target in enumerate(('MASE','MAE_IQR')):
        for col,(group,mask) in enumerate([('Within-dataset test',frame.split.eq('test').to_numpy()),
            ('Entire weather held out',frame.dataset_id.eq('monash_weather').to_numpy())]):
            ix=mask&valid
            for method in ('M0','M1','M2','M3'):
                score=h1['scores'][('full',target,method)][ix];c,r=risk_curve(score,frame.loc[ix,target].to_numpy())
                axes[row,col].plot(c,r,label=method)
            axes[row,col].set(title=f'{group}, N={ix.sum()}',xlabel='Coverage',ylabel=f'Selective risk ({target})')
            axes[row,col].legend(ncol=2)
    fig.suptitle('H1: identical N60 mean forecast; equally calibrated risk models');fig.tight_layout();figs.append(('H1_risk_coverage',fig))
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,target in zip(axes,('MASE','MAE_IQR')):
        rows=[r for r in h1['comparisons'] if r['population']=='full' and r['target']==target and r['comparison']=='M3-M1']
        values=[r['delta_NEAURC'] for r in rows]
        bounds=np.array([r['delta_NEAURC_CI95'] for r in rows]);y=np.arange(len(rows))
        ax.hlines(y,bounds[:,0],bounds[:,1]);ax.scatter(values,y)
        ax.axvline(0,color='gray',ls='--');ax.set(yticks=y,yticklabels=[r['group'] for r in rows],xlabel='M3 minus M1 NEAURC (lower favors FPA)',title=target)
    fig.tight_layout();figs.append(('H1_incremental_uncertainty',fig))
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    summary=pd.DataFrame(h2['summaries'])
    for method in ('MC','first_token_proportional','first_deviation_uniform','first_deviation_proportional','first_deviation_neyman_cost','stratum_mixture_IS'):
        d=summary[summary.method==method].sort_values('anchor')
        if len(d):
            axes[0].plot(d.mean_seconds,d.RMSE_to_reference,'o-',label=method)
            axes[1].plot(d.anchor,d.RMSE_to_reference,'o-',label=method)
            for _,point in d.iterrows():
                if point.original_sources<36:axes[1].annotate(f'N={int(point.original_sources)}',
                    (point.anchor,point.RMSE_to_reference),fontsize=5)
    axes[0].set(xlabel='Actual variable inference seconds (pilot charged)',ylabel='RMSE to independent finite N2000 reference')
    axes[1].set(xlabel='Natural-equivalent budget anchor',ylabel='RMSE to finite reference')
    axes[1].legend(fontsize=6);fig.suptitle('H2: feasible sources (counts shown when <36); paired comparisons govern claims');fig.tight_layout();figs.append(('H2_cost_error',fig))
    source=h2['source'];fig,ax=plt.subplots(figsize=(7,4));paired_points={'method':[],'MC':[]}
    for anchor in (60,120,240,480):
        a=source[(source.method=='first_deviation_neyman_cost')&(source.anchor==anchor)]
        b=source[(source.method=='matched_MC')&(source.matched_to=='first_deviation_neyman_cost')&(source.anchor==anchor)]
        paired=a.merge(b,on=['window_id','dataset_id'],suffixes=('_method','_MC'))
        if len(paired):
            for name in paired_points:paired_points[name].append((paired['seconds_'+name].mean(),
                np.sqrt(paired['MSE_'+name].mean()),len(paired),anchor))
    for name,points in paired_points.items():
        if points:
            points=np.array(points);ax.plot(points[:,0],points[:,1],'o-',label='Neyman first-deviation' if name=='method' else 'Matched ordinary MC')
            for x,y,n,anchor in points:ax.annotate(f'{int(anchor)}, N={int(n)}',(x,y),fontsize=7,xytext=(3,3),textcoords='offset points')
    ax.set(xlabel='Actual variable generation seconds, pilot charged',ylabel='RMSE to finite N2000 reference',
        title='Same original sources in each method/MC pair');ax.legend();fig.tight_layout();figs.append(('H2_primary_paired_cost_error',fig))
    ref=h2['references'];fig,axes=plt.subplots(1,2,figsize=(10,4))
    for name,d in ref.groupby('event'):
        axes[0].scatter(d.block0_probability,d.block1_probability,s=12,alpha=.65,label=name)
    axes[0].plot([0,1],[0,1],'k--',lw=1);axes[0].set(xlabel='Independent reference block0 (N1000)',ylabel='Reference block1 (N1000)');axes[0].legend(fontsize=6)
    d=h2['taskb'];d=d[d.method=='independent_reference_N2000']
    for name,g in d.groupby('event'):
        axes[1].scatter(g.probability,g.actual_event,s=10,alpha=.5,label=name)
    axes[1].set(xlabel='Independent N2000 model probability',ylabel='Observed future event (one/source)',title='Task B is separate from MC accuracy')
    fig.tight_layout();figs.append(('H2_reference_and_actual_future',fig))
    # Explicitly post-hoc illustrations: the most favorable and unfavorable
    # SOURCE-AVERAGED cases. They do not define the primary population test.
    s=h2['source'];a=s[(s.method=='first_deviation_neyman_cost')&(s.anchor==480)]
    b=s[(s.method=='matched_MC')&(s.matched_to=='first_deviation_neyman_cost')&(s.anchor==480)]
    pairs=a.merge(b,on=['window_id','dataset_id'],suffixes=('_method','_MC'))
    if len(pairs):
        pairs['delta']=pairs.MSE_method-pairs.MSE_MC
        selected=[pairs.sort_values('delta').iloc[0],pairs.sort_values('delta').iloc[-1]]
        fig,axes=plt.subplots(2,2,figsize=(11,7));illustrations=[]
        for row,item in enumerate(selected):
            _,snapshot=verify_complete(run,'H2',item.window_id)
            arrays=[a for m,a in snapshot['records'] if m['identity']['role']=='h2_reference'][0]
            c=arrays['context'];v=arrays['values'];g=arrays['greedy_values']
            axes[row,0].plot(np.arange(-64,0),c[-64:],color='black',label='context')
            for trajectory in v[:12]:axes[row,0].plot(np.arange(32),trajectory,color='tab:blue',alpha=.15)
            axes[row,0].plot(np.arange(32),g,color='tab:orange',label='greedy')
            axes[row,0].set(title=f'Post-hoc {"smallest" if row==0 else "largest"} delta MSE: {item.dataset_id}\n{item.window_id[:10]}, delta={item.delta:.3g}, time(method/MC)={item.seconds_method:.1f}/{item.seconds_MC:.1f}s',xlabel='Absolute forecast coordinate');axes[row,0].legend(fontsize=7)
            d=h2['frame'];d=d[(d.window_id==item.window_id)&(d.anchor==480)]
            x=np.arange(4)
            for method,offset in [('first_deviation_neyman_cost',-.15),('matched_MC',.15)]:
                z=d[d.method==method]
                if method=='matched_MC':z=z[z.matched_to=='first_deviation_neyman_cost']
                means=z.groupby('event')['estimate'].mean().reindex(EVENT_NAMES)
                axes[row,1].scatter(x+offset,means,label=method)
            r=ref[ref.window_id==item.window_id].set_index('event').reindex(EVENT_NAMES)
            axes[row,1].errorbar(x,r.reference_probability,yerr=plotting_interval_errors(r.reference_probability,r.wilson_lo,r.wilson_hi),fmt='k_',capsize=3,label='N2000 reference + Wilson CI')
            axes[row,1].set(xticks=x,xticklabels=['E1','E2','E3','E4'],ylabel='q50 event probability');axes[row,1].legend(fontsize=6)
            illustrations.append(item.to_dict())
        fig.tight_layout();figs.append(('H2_trajectories_extreme_comparisons',fig));save_clean(out/'posthoc_illustrations.json',illustrations)
    with PdfPages(out/'FPA_incremental_scientific_figures.pdf') as pdf:
        for name,fig in figs:fig.savefig(out/(name+'.png'));pdf.savefig(fig);plt.close(fig)


def main(run,allow_partial=False):
    config=load(run/'frozen_config.json');verify_sources(run,'H1')
    cohort=load(run/'cohort.json')['windows'];selected=[];collection_status={}
    for phase in ('H1','H2'):
        planned=[w for w in cohort if w['study']==phase]
        complete=[w for w in planned if (run/phase/w['window_id']/'complete.json').exists()]
        if len(complete)!=len(planned) and not allow_partial:
            raise RuntimeError('Full bounded phases must finish before target analysis; explicit --partial only after a resource stop')
        selected.extend(complete)
        collection_status[phase]={'planned':len(planned),'complete_originals':len(complete),
            'minimum_informative':240 if phase=='H1' else 24,
            'status':'full' if len(complete)==len(planned) else 'bounded partial; no outcome-based reselection'}
    if not any(w['study']=='H2' for w in selected):raise RuntimeError('No complete H2 probability cell; cannot fabricate H2 analysis')
    freeze={'utc':datetime.now(timezone.utc).isoformat(),'analysis_script_sha256':digest(Path(__file__)),
        'methodology_sha256':digest(run/'methodology.json'),'collection_source_id':load(run/'frozen.json')['source_id'],
        'targets_sha256':digest(run/'sealed_targets.npz'),
        'secondary_controls_sha256':digest(run/'pretarget_analysis_controls.json'),
        'selected_complete_markers':{w['window_id']:digest(run/w['study']/w['window_id']/'complete.json') for w in selected},
        'collection_status':collection_status,
        'first_target_access_follows_this_receipt':True}
    path=run/'analysis_freeze.json'
    if path.exists():
        old=load(path)
        if any(old[k]!=v for k,v in freeze.items() if k!='utc'):raise ValueError('Analysis source changed after target access; retain old analysis and document explicit revision')
    else:save(path,freeze)
    started=time.perf_counter();out=run/'analysis';out.mkdir(exist_ok=True)
    def flattened(value,prefix=''):
        if isinstance(value,dict):
            for key,child in value.items():yield from flattened(child,prefix+'.'+key if prefix else key)
        else:yield {'field':prefix,'value':json.dumps(value,ensure_ascii=False),'canonical_source':'methodology.json'}
    csv(out/'frozen_methodology.csv',list(flattened(load(run/'methodology.json'))))
    # This is the FIRST deliberate reading of new held-out target values.
    with np.load(run/'sealed_targets.npz') as archive:targets={w['window_id']:archive[w['window_id']].copy() for w in selected}
    verify_selected_source_alignment(run,selected,targets)
    h1=evaluate_h1(run,[w for w in selected if w['study']=='H1'],targets,out,config)
    h2=evaluate_h2(run,[w for w in selected if w['study']=='H2'],targets,out,config)
    available={t['name']:t for t in h1['formal']+[h2['formal']]}
    tests=[available.get(name,{'name':name,'one_sided_p':1.,'status':'not evaluable'})
        for name in ('H1_within_test','H1_OOD_weather','H2_primary')]
    adjusted=holm([t['one_sided_p'] for t in tests])
    for test,p in zip(tests,adjusted):test['Holm_family3_p']=p
    save_clean(out/'primary_tests.json',tests)
    make_figures(run,out,h1,h2)
    save_clean(out/'scientific_summary.json',{'H1_comparisons':h1['comparisons'],'H2_primary':h2['primary'],
        'formal_tests':tests,'H1_evaluable_targets':int(h1['frame'].target_available.sum()),
        'H2_evaluable_actual_outcomes':int(h2['references'].groupby('window_id').actual_available.first().sum()),
        'model_subprocess_seconds':charged_seconds(run),'new_data_and_run_bytes':new_bytes(run),
        'collection_status':collection_status,
        'analysis_seconds':time.perf_counter()-started})
    save(run/'analysis_complete.json',{'utc':datetime.now(timezone.utc).isoformat(),
        'analysis_script_sha256':digest(Path(__file__)),'outputs':{p.name:digest(p) for p in out.iterdir() if p.is_file()}})
    print('OFFLINE ANALYSIS COMPLETE',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--partial',action='store_true',help='Only after resource stop; completed source IDs, no outcome selection')
    args=parser.parse_args();main(args.run.resolve(),args.partial)
