"""Scientific review of finalized extended-batch objects, no model loading."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('MPLBACKEND','Agg')
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code/chronos_fpa'));sys.path.insert(0,str(ROOT/'scripts/runs'))
import bootstrap  # noqa: E402,F401
import numpy as np
import pandas as pd
from chronos_distances import empirical_w1_by_horizon
from chronos_outcomes import compare_fixed22_and_full,weighted_events,window_outcomes,THRESHOLDS
from chronos_offline_precision import distances,supports,bootstrap_distances,permutation_distances,holm
from chronos_propagation_baselines import predicted_paths
from run_chronos_extended_batch import read_block,read_validation,verify_window
from run_chronos_local_pilot import verify_freeze
from run_chronos_microbenchmark import jsonable
from analyze_chronos_pilot_offline import morphology,cpd_and_variance


def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(jsonable(x),indent=2,allow_nan=False),encoding='utf-8')
def csv(out,name,rows):
    f=pd.DataFrame(rows);f.to_csv(out/(name+'.csv'),index=False);return f
def correlation(a,b):
    a,b=pd.Series(a,dtype=float),pd.Series(b,dtype=float)
    return a.rank().corr(b.rank()) if a.nunique()>1 and b.nunique()>1 else np.nan
def ci(x):return {'lo':float(np.quantile(x,.025)),'hi':float(np.quantile(x,.975)),'sd':float(np.std(x,ddof=1))}


def concatenate_arrays(arrays):
    """Analysis-only pool, preserving whole-path alignment and fixed inputs."""
    fixed=['context','greedy_tokens','greedy_values']
    for key in fixed:
        for a in arrays[1:]:np.testing.assert_array_equal(arrays[0][key],a[key])
    return {**{k:arrays[0][k] for k in fixed},
            'tokens':np.concatenate([a['tokens'] for a in arrays]),
            'values':np.concatenate([a['values'] for a in arrays])}


def read_cells(run):
    panel=verify_freeze(run);completed=load(run/'batch_complete.json');cells=[];streams=[];seeds=[]
    for plan in load(run/'cell_plan.json'):
        marker,result,validation=read_block(run,plan)
        bound=next(w['complete_sha256'][plan['cell_id']] for w in completed['windows'] if w['window_id']==plan['window_id'])
        if sha(run/'cells'/plan['cell_id']/'complete.json')!=bound:raise ValueError('Batch checkpoint changed')
        cells.append({'plan':plan,'result':result,'validation':validation,
                      'window':next(w for w in panel['windows'] if w['window_id']==plan['window_id'])})
        streams.extend(m['metadata']['rng']['stream_id'] for m,_ in validation['records'])
        seeds.extend(m['metadata']['rng']['seed'] for m,_ in validation['records'])
    validations={}
    for w in panel['windows']:
        wid=w['window_id'];verify_window(run,wid);marker,snapshot=read_validation(run,wid)
        if sha(run/'validation'/wid/'complete.json')!=completed['validation_complete_sha256'][wid]:raise ValueError('Validation aggregate hash changed')
        validations[wid]={'marker':marker,'records':snapshot['records'],
            'lookup':{(m['identity']['position'],m['identity']['role'],m['identity']['token']):(m,a) for m,a in snapshot['records']}}
        streams.extend(m['metadata']['rng']['stream_id'] for m,_ in snapshot['records'])
        seeds.extend(m['metadata']['rng']['seed'] for m,_ in snapshot['records'])
    if len(streams)!=len(set(streams)) or len(seeds)!=len(set(seeds)):raise ValueError('Reused dense/fresh RNG')
    return cells,validations,panel,{'ensembles':len(streams),'unique_rng_streams':len(set(streams)),
        'unique_derived_seeds':len(set(seeds)),'dense_blocks':len(cells),'original_series':len(panel['windows']),
        'dense_paths':sum(c['validation']['paths'] for c in cells),
        'fresh_paths':sum(v['marker']['paths'] for v in validations.values())}


def verify_saved_policies(run,cells,out):
    """Reconstruct q50/candidates from bound saved logits, no model inference."""
    from types import SimpleNamespace
    import torch
    from chronos_exploratory import policy_probabilities,select_candidates
    from chronos_decoding import _mask_to_chronos_value_tokens
    torch.set_num_threads(4)
    config=load(Path(load(run/'model_cache.json')['snapshot'])/'config.json')['chronos_config']
    mc=SimpleNamespace(**config);checks=0;max_weight_error=0.
    for cell in cells:
        with np.load(run/'cells'/cell['plan']['cell_id']/'fork_logits.npz',allow_pickle=False) as a:logits=a['logits']
        for fork in cell['result']['forks']:
            b=fork['b'];raw=torch.from_numpy(logits[b:b+1]);q=policy_probabilities(raw,mc)[0].cpu()
            selected=select_candidates(q,fork['greedy_token'])
            if list(selected.token_ids)!=fork['selected_tokens'] or list(selected.residual_ids)!=fork['residual_ids']:raise ValueError('Saved logits/candidate support mismatch')
            support=torch.where(q>0)[0].tolist();qn=q.double()/q.double().sum()
            if support!=fork['q50_support_ids']:raise ValueError('Saved q50 support differs from logits')
            np.testing.assert_allclose(qn[support].numpy(),fork['q50_support_weights'],atol=1e-10,rtol=0)
            np.testing.assert_allclose(float(-(qn[qn>0]*qn[qn>0].log()).sum()),fork['entropy_q50_nats'],atol=1e-10,rtol=0)
            np.testing.assert_allclose(selected.weights,fork['selected_weights'],atol=1e-10,rtol=0)
            np.testing.assert_allclose(selected.residual_mass,fork['residual_mass'],atol=1e-10,rtol=0)
            p=torch.softmax(_mask_to_chronos_value_tokens(raw,mc),dim=-1)[0].cpu()
            positive=p[p>0].double()
            np.testing.assert_allclose(float(-(positive*positive.log()).sum()),fork['entropy_p_sel_nats'],atol=1e-10,rtol=0)
            np.testing.assert_allclose([float(p[t]) for t in selected.token_ids],fork['p_sel_selected'],atol=1e-7,rtol=1e-7)
            max_weight_error=max(max_weight_error,float(np.max(abs(np.asarray(selected.weights)-fork['selected_weights']))));checks+=1
    proof={'forks_reconstructed':checks,'max_absolute_selected_weight_error':max_weight_error,'model_inference_calls':0,
        'q50_ties_cap90_residual_p_sel_verified':True}
    save(out/'sampling_policy_reconstruction.json',proof)


def pool_cells(cells):
    pooled=[]
    for wid in dict.fromkeys(c['plan']['window_id'] for c in cells):
        blocks=sorted([c for c in cells if c['plan']['window_id']==wid],key=lambda c:c['plan']['block_index'])
        first=blocks[0];lookup={};records=[]
        for key in first['validation']['lookup']:
            sources=[c['validation']['lookup'][key] for c in blocks]
            arrays=concatenate_arrays([a for _,a in sources])
            # A derived view, never published as a raw ensemble or independent seed.
            manifest={'identity':{**sources[0][0]['identity'],'sample_count':len(arrays['values']),'sampling_seed':'pooled_3x20'},
                      'derived_from_object_ids':[m['task_id'] for m,_ in sources]}
            lookup[key]=(manifest,arrays);records.append((manifest,arrays))
        result=copy.deepcopy(first['result']);result['distances']=[];groups_by_position={}
        result['samples_per_group']=60;result['direct_samples']=60
        result['derived_pool']={'source_block_ids':[c['plan']['cell_id'] for c in blocks],
            'new_model_draws_for_pool':0,'interpretation':'one empirical N60 law from three independent N20 blocks'}
        for fork in result['forks']:
            b,g=fork['b'],fork['greedy_token'];r=lookup[(b,'reference',g)][1];n=lookup[(b,'null',g)][1]
            null,_=compare_fixed22_and_full(r['values'],n['values'],b,r['context'])
            groups=[lookup[(b,'reference' if t==g else 'alternative',t)][1] for t in fork['selected_tokens']]
            weights=list(fork['selected_weights'])
            if fork['residual_mass']>0:groups.append(lookup[(b,'residual',None)][1]);weights.append(fork['residual_mass'])
            groups_by_position[b]=(groups,weights)
            for original in [v for v in first['result']['distances'] if v['b']==b]:
                a=lookup[(b,'alternative',original['token'])][1]
                d,profile=compare_fixed22_and_full(r['values'],a['values'],b,r['context'])
                result['distances'].append({**original,**d,'w1_profile':profile.tolist(),'same_token_null':null})
        outcomes={}
        for position in range(16):
            if position<10:groups,weights=groups_by_position[position]
            else:
                key=(9,'reference',result['greedy_tokens'][9]) if position==10 else (position,'direct_cpd',None)
                groups,weights=[lookup[key][1]],[1.]
            estimate=weighted_events([window_outcomes(g['values'],np.array(result['greedy_values']),result['context_iqr'])['events'] for g in groups],weights)
            expected=np.mean([c['result']['outcome_distributions'][str(position)]['event_probability'] for c in blocks],axis=0)
            np.testing.assert_allclose(estimate['event_probability'],expected,atol=1e-12,rtol=0)
            outcomes[str(position)]={**estimate,'method':'pooled_3x20_'+('q50_mixture' if position<10 else 'reuse_b9_reference' if position==10 else 'direct_prefix')}
        result['outcome_distributions']=outcomes
        plan=copy.deepcopy(first['plan']);plan['scope']['sampling_seed']='pooled_3x20';plan['primary']=True
        pooled.append({'plan':plan,'result':result,'validation':{'lookup':lookup,'records':records,'groups_by_position':groups_by_position},'window':first['window']})
    return pooled


def values(cell,b,role,token=None):
    if role in ('reference','null'):token=cell['result']['greedy_tokens'][b]
    return cell['validation']['lookup'][(b,role,token)][1]['values'].astype(float)


def co(cell):
    w=cell['window'];return {'window_id':w['window_id'],'series':w['series_id'],'dataset':w['dataset_id'],'stratum':w['stratum']}


def core_results(pooled,out):
    branches=[];profiles=[];splits=[];normalizations=[]
    for cell in pooled:
        common=co(cell);result=cell['result'];iqr=result['context_iqr'];context=cell['validation']['records'][0][1]['context'].astype(float)
        for row in result['distances']:
            b,t=row['b'],row['token'];fork=result['forks'][b];r,a,n=values(cell,b,'reference'),values(cell,b,'alternative',t),values(cell,b,'null')
            j=a[0,b]-r[0,b];coords=supports(b)['full'];w1=empirical_w1_by_horizon(r[:,coords],a[:,coords]);wn=empirical_w1_by_horizon(r[:,coords],n[:,coords])
            delta=a[:,coords].mean(axis=0)-r[:,coords].mean(axis=0);variance=a[:,coords].var(axis=0,ddof=1)-r[:,coords].var(axis=0,ddof=1)
            tiny=max(.01*iqr,1e-12*max(1,abs(context).max()));eligible=abs(j)>tiny
            branches.append({**common,'N':60,**{k:v for k,v in row.items() if k not in ['w1_profile','same_token_null']},
                'null_w1_post':row['same_token_null']['w1_post'],'null_ed_post':row['same_token_null']['ed_post'],
                'null_w1_fixed22':row['same_token_null']['w1_fixed22'],'null_ed_fixed22':row['same_token_null']['ed_fixed22'],
                'entropy_q50':fork['entropy_q50_nats'],'entropy_p_sel':fork['entropy_p_sel_nats'],'phi':cell['window']['lag1'],
                'token_offset':t-fork['greedy_token'],'bin_width_iqr':abs(j/(t-fork['greedy_token']))/iqr,
                **{k:cell['window'][k] for k in ['trend_iqr','diff_std_iqr','half_shift_iqr','context_std']}})
            for k,h in enumerate(coords):
                profiles.append({**common,'b':b,'token':t,'coordinate':h,'h':h-b,'N':60,'iqr':iqr,'J':j,
                    'w1':w1[k],'null_w1':wn[k],'delta_mean':delta[k],'null_delta_mean':n[:,h].mean()-r[:,h].mean(),
                    'delta_variance':variance[k],'reference_sd':r[:,h].std(ddof=1),'gain':delta[k]/j if eligible else np.nan,
                    'persistent_mean_response':j,'ar1_mean_response':j*cell['window']['lag1']**(h-b)})
            splits.append({**common,'b':b,'token':t,'split':'first8_last8','alt_increase':w1[-8:].mean()>w1[:8].mean(),
                'null_increase':wn[-8:].mean()>wn[:8].mean(),'excess_increase':(w1-wn)[-8:].mean()>(w1-wn)[:8].mean(),
                'early_mean':delta[:8].mean(),'late_mean':delta[-8:].mean(),'sign_reversal':delta[:8].mean()*delta[-8:].mean()<0,
                'gain_eligible':eligible,'early_gain':delta[:8].mean()/j if eligible else np.nan,'late_gain':delta[-8:].mean()/j if eligible else np.nan})
        for name,scale in [('protocol_iqr',iqr),('sensitivity_std',context.std()),('sensitivity_range',np.ptp(context)),('sensitivity_recent128_iqr',np.quantile(context[-128:],.75)-np.quantile(context[-128:],.25))]:
            valid=bool(np.isfinite(scale) and scale>1e-12)
            normalizations.append({**common,'normalization':name,'scale':scale,'valid':valid,
                'median_w1_scaled':np.median([r['w1_post'] for r in result['distances']])/scale if valid else np.nan,
                'median_null_scaled':np.median([r['same_token_null']['w1_post'] for r in result['distances']])/scale if valid else np.nan})
    bf=csv(out,'branch_effects_N60',branches);pf=csv(out,'propagation_profiles_N60',profiles)
    csv(out,'propagation_splits_N60',splits);csv(out,'normalization_sensitivity',normalizations)
    window_rows=[];associations=[]
    for (wid,series,dataset,stratum),g in bf.groupby(['window_id','series','dataset','stratum'],sort=False):
        row={'window_id':wid,'series':series,'dataset':dataset,'stratum':stratum,'alternatives':len(g)}
        for metric in ['w1_post','ed_post','w1_fixed22','ed_fixed22','w1_post_over_context_iqr','ed_post_over_context_iqr','w1_fixed22_over_context_iqr','ed_fixed22_over_context_iqr']:
            row[metric+'_median']=g[metric].median()
        row['w1_le_null']=int((g.w1_post<=g.null_w1_post).sum());window_rows.append(row)
        for effect in ['w1_fixed22_over_context_iqr','ed_fixed22_over_context_iqr']:
            for pred in ['signed_direct_token_jump_over_context_iqr','direct_token_jump_over_context_iqr','q50','p_sel','entropy_q50','entropy_p_sel','bin_width_iqr']:
                associations.append({'window_id':wid,'series':series,'dataset':dataset,'effect':effect,'predictor':pred,'spearman':correlation(g[effect],g[pred]),'branches':len(g),'independent_source_series':1})
    wf=csv(out,'per_series_summary',window_rows);csv(out,'within_series_associations',associations)
    csv(out,'dataset_series_aggregation',wf.groupby('dataset',sort=False).agg(original_series=('series','size'),
        equal_series_mean_of_median_w1_iqr=('w1_fixed22_over_context_iqr_median','mean'),
        equal_series_mean_of_median_ed_iqr=('ed_fixed22_over_context_iqr_median','mean')).reset_index().to_dict('records'))


def precision(cells,out,config):
    rng=np.random.default_rng(config['resampling_seed']);reps=config['bootstrap_replicates']
    designs={'N20_block0':np.arange(20),'N20_block1':np.arange(20,40),'N20_block2':np.arange(40,60),
        'N40_01':np.arange(40),'N40_02':np.r_[np.arange(20),np.arange(40,60)],'N40_holdout12':np.arange(20,60),'N60_pool':np.arange(60)}
    canonical=['N20_block0','N40_holdout12','N60_pool'];points=[];uncertainty=[];ranks=[];matched=[]
    for wid in dict.fromkeys(c['plan']['window_id'] for c in cells):
        blocks=[c for c in cells if c['plan']['window_id']==wid];first=blocks[0];common=co(first);iqr=first['result']['context_iqr'];by_design={d:{} for d in designs}
        for fork in first['result']['forks']:
            b,g=fork['b'],fork['greedy_token'];coords=supports(b)['relative22']
            r,n=[np.concatenate([values(c,b,role) for c in blocks])[:,coords]/iqr for role in ('reference','null')]
            bootrefs={d:rng.integers(len(ix),size=(reps,len(ix))) for d,ix in designs.items() if d in canonical}
            bootnull={d:bootstrap_distances(r[ix],n[ix],bootrefs[d],rng.integers(len(ix),size=(reps,len(ix)))) for d,ix in designs.items() if d in canonical}
            boot_alts={d:{} for d in canonical}
            for token in fork['selected_tokens'][1:]:
                a=np.concatenate([values(c,b,'alternative',token) for c in blocks])[:,coords]/iqr
                for design,ix in designs.items():
                    d,nd=distances(r[ix],a[ix]),distances(r[ix],n[ix]);by_design[design][(b,token)]=d
                    points.append({**common,'b':b,'token':token,'design':design,'N':len(ix),'support':'relative22','normalization':'context_iqr',**d,**{'null_'+m:v for m,v in nd.items()}})
                    if design in canonical:
                        ba=bootstrap_distances(r[ix],a[ix],bootrefs[design],rng.integers(len(ix),size=(reps,len(ix))));boot_alts[design][token]=ba
                        for metric in ('w1','ed'):
                            uncertainty.append({**common,'b':b,'token':token,'design':design,'N':len(ix),'metric':metric,'estimate':d[metric],
                                **ci(ba[metric]),'excess':d[metric]-nd[metric],**{'excess_'+k:v for k,v in ci(ba[metric]-bootnull[design][metric]).items()}})
            for down in fork['selected_tokens'][1:]:
                up=2*g-down
                if down>=g or up not in fork['selected_tokens']:continue
                for design in designs:
                    for metric in ('w1','ed'):
                        row={**common,'b':b,'down_token':down,'up_token':up,'design':design,'N':len(designs[design]),'metric':metric,
                            'up_minus_down':by_design[design][(b,up)][metric]-by_design[design][(b,down)][metric]}
                        if design in canonical:row.update(ci(boot_alts[design][up][metric]-boot_alts[design][down][metric]))
                        matched.append(row)
        keys=sorted(by_design['N60_pool'])
        for d1,d2 in itertools.combinations(designs,2):
            independent=not bool(set(designs[d1])&set(designs[d2]))
            for metric in ('w1','ed'):
                a=np.array([by_design[d1][k][metric] for k in keys]);bv=np.array([by_design[d2][k][metric] for k in keys])
                for top in (5,10):
                    k=min(top,len(keys));ranks.append({**common,'design1':d1,'design2':d2,'metric':metric,'top_k':k,
                        'independent_draw_sets':independent,'spearman':correlation(a,bv),
                        'top_k_overlap':len(set(np.argsort(a)[-k:])&set(np.argsort(bv)[-k:]))/k,
                        'median_absolute_difference':np.median(abs(a-bv))})
        print('Precision',common['series'],flush=True)
    csv(out,'precision_estimates',points);u=csv(out,'precision_uncertainty',uncertainty)
    u['width']=u.hi-u.lo
    csv(out,'precision_summary',u.groupby(['series','dataset','metric','N'],sort=False).agg(branches=('estimate','size'),
        median_distance=('estimate','median'),median_interval_width=('width','median'),median_bootstrap_sd=('sd','median')).reset_index().to_dict('records'))
    csv(out,'rank_stability',ranks);csv(out,'matched_jump_contrasts',matched)


def direct_baselines(cells,out,config):
    rows=[];matched=[];rng=np.random.default_rng(config['resampling_seed']+2);reps=config['bootstrap_replicates']
    for wid in dict.fromkeys(c['plan']['window_id'] for c in cells):
        blocks=[c for c in cells if c['plan']['window_id']==wid];first=blocks[0];common=co(first);iqr=first['result']['context_iqr'];phi=first['window']['lag1']
        designs={**{f'N20_block{i}':[blocks[i]] for i in range(3)},'N40_holdout12':blocks[1:],'N60_pool':blocks}
        for design,chosen in designs.items():
            for fork in first['result']['forks']:
                b,g=fork['b'],fork['greedy_token'];r,n=[np.concatenate([values(c,b,role) for c in chosen]) for role in ('reference','null')];size=len(r)
                inn=rng.integers(size,size=(reps,size));points={};boots={}
                for token in fork['selected_tokens'][1:]:
                    a=np.concatenate([values(c,b,'alternative',token) for c in chosen]);j=a[0,b]-r[0,b]
                    ia=rng.integers(size,size=(reps,size))
                    for support,coords in supports(b).items():
                        raw=distances(a[:,coords],r[:,coords]);null=distances(r[:,coords],n[:,coords])
                        for model in ('persistent','ar1'):
                            pred=predicted_paths(n,b,j,phi,coords,model);d=distances(a[:,coords],pred)
                            magnitude=distances(r[:,coords],pred)
                            for metric in ('w1','ed'):
                                row={**common,'design':design,'N':size,'b':b,'token':token,'support':support,'model':model,'metric':metric,
                                    'J':j,'iqr':iqr,'residual_raw':d[metric],'residual_iqr':d[metric]/iqr,
                                    'untransformed_raw':raw[metric],'untransformed_iqr':raw[metric]/iqr,
                                    'MC_control_raw':null[metric],'MC_control_iqr':null[metric]/iqr,
                                    'old_magnitude_raw':magnitude[metric]}
                                rows.append(row);points[(token,support,model,metric)]=row
                            if support=='relative22' and design in ('N40_holdout12','N60_pool'):
                                boots[(token,model)]=bootstrap_distances(a[:,coords]/iqr,pred/iqr,ia,inn)
                for down in fork['selected_tokens'][1:]:
                    up=2*g-down
                    if down>=g or up not in fork['selected_tokens']:continue
                    for support,model,metric in itertools.product(supports(b),('persistent','ar1'),('w1','ed')):
                        lo,hi=points[(down,support,model,metric)],points[(up,support,model,metric)]
                        row={**common,'design':design,'N':size,'b':b,'down_token':down,'up_token':up,'support':support,'model':model,'metric':metric,
                            'down_J':lo['J'],'up_J':hi['J'],'raw_asymmetry_up_minus_down':hi['untransformed_iqr']-lo['untransformed_iqr'],
                            'residual_asymmetry_up_minus_down':hi['residual_iqr']-lo['residual_iqr']}
                        if support=='relative22' and design in ('N40_holdout12','N60_pool'):
                            row.update(ci(boots[(up,model)][metric]-boots[(down,model)][metric]))
                        matched.append(row)
        print('Direct baseline fit',common['series'],flush=True)
    csv(out,'direct_baseline_distances',rows);csv(out,'matched_baseline_asymmetry',matched)


def independent_validation(run,cells,validations,out,config):
    rng=np.random.default_rng(config['resampling_seed']+3);reps=config['bootstrap_replicates'];nperm=config['permutations']
    rows=[];nullrows=[];selected_rows=[]
    for wid in dict.fromkeys(c['plan']['window_id'] for c in cells):
        blocks=[c for c in cells if c['plan']['window_id']==wid];first=blocks[0];result=first['result'];common=co(first)
        selection=load(run/'selections'/(wid+'.json'));selected=selection['selected'];control=selection['random_control'];iqr=result['context_iqr'];phi=first['window']['lag1']
        for slot,(b,t) in enumerate(selected):selected_rows.append({**common,'b':b,'token':t,'class':'selected_ED' if slot==0 else 'selected_W1_remaining','fresh_N60':True})
        if control:selected_rows.append({**common,'b':control[0],'token':control[1],'class':'random_control','fresh_N60':False})
        for phase,contrasts in [('holdout40',selected+([control] if control else [])),('fresh60',selected)]:
            boot_shared={};observed_null={}
            def array(b,role,t=None):
                token=result['greedy_tokens'][b] if role in ('reference','null') else t
                if phase=='holdout40':return np.concatenate([values(c,b,role,token) for c in blocks[1:]])
                return validations[wid]['lookup'][(b,role,token)][1]['values'].astype(float)
            for b,t in contrasts:
                r,a,n=array(b,'reference'),array(b,'alternative',t),array(b,'null');size=len(r);coords=supports(b)['relative22'];j=a[0,b]-r[0,b]
                category='random_control' if control==[b,t] else 'selected_ED' if selected[0]==[b,t] else 'selected_W1_remaining'
                if b not in boot_shared:
                    ir=rng.integers(size,size=(reps,size));inn=rng.integers(size,size=(reps,size))
                    nb=bootstrap_distances(r[:,coords]/iqr,n[:,coords]/iqr,ir,inn)
                    boot_shared[b]=(ir,inn,nb)
                    nd=distances(r[:,coords],n[:,coords]);observed_null[b]=nd
                    pp=permutation_distances(r[:,coords]/iqr,n[:,coords]/iqr,nperm,rng)
                    for metric in ('w1','ed'):nullrows.append({**common,'phase':phase,'b':b,'metric':metric,'N':size,'p':pp['p_'+metric],
                        'distance_iqr':nd[metric]/iqr,'shared_by_all_alternatives_at_b':True})
                ir,inn,nb=boot_shared[b];nd=observed_null[b];ia=rng.integers(size,size=(reps,size))
                rawboot=bootstrap_distances(a[:,coords]/iqr,r[:,coords]/iqr,ia,ir)
                for method in ('raw','persistent','ar1'):
                    prediction=r[:,coords] if method=='raw' else predicted_paths(n,b,j,phi,coords,method)
                    point=distances(a[:,coords],prediction);pp=permutation_distances(a[:,coords]/iqr,prediction/iqr,nperm,rng)
                    boot=rawboot if method=='raw' else bootstrap_distances(a[:,coords]/iqr,prediction/iqr,ia,inn)
                    for metric in ('w1','ed'):
                        rows.append({**common,'phase':phase,'class':category,'b':b,'token':t,'N':size,'support':'relative22','method':method,
                            'metric':metric,'J_raw':j,'J_iqr':j/iqr,'p':pp['p_'+metric],'distance_raw':point[metric],'distance_iqr':point[metric]/iqr,
                            'null_distance_iqr':nd[metric]/iqr,**ci(boot[metric]),
                            **{'paired_difference_from_raw_'+k:v for k,v in ci(boot[metric]-rawboot[metric]).items()},
                            **{'excess_over_null_'+k:v for k,v in ci(boot[metric]-nb[metric]).items()},
                            'practical_0p02_iqr_sensitivity':point[metric]/iqr>.02,
                            'CI_interpretation':'pointwise finite-pool percentile, biased near equality; no equivalence claim'})
                print('Validation statistics',common['series'],phase,b,t,category,flush=True)
    f=pd.DataFrame(rows);nf=pd.DataFrame(nullrows)
    for phase in f.phase.unique():
        mask=f.phase.eq(phase);f.loc[mask,'holm']=holm(f.loc[mask,'p']);f.loc[mask,'family_size']=int(mask.sum())
        mask=nf.phase.eq(phase);nf.loc[mask,'holm']=holm(nf.loc[mask,'p']);nf.loc[mask,'family_size']=int(mask.sum())
    f.to_csv(out/'independent_validation.csv',index=False);nf.to_csv(out/'independent_null_tests.csv',index=False)
    csv(out,'frozen_contrast_selection',selected_rows)
    # Source-series summaries keep selected and random contrasts visible separately.
    enrichment=[]
    for (phase,series,klass,method,metric),g in f.groupby(['phase','series','class','method','metric'],sort=False):
        enrichment.append({'phase':phase,'series':series,'class':klass,'method':method,'metric':metric,'contrasts':len(g),
            'reject_Holm':int((g.holm<=.05).sum()),'median_distance_iqr':g.distance_iqr.median(),
            'median_interval_width':(g.hi-g.lo).median()})
    csv(out,'selection_enrichment_by_series',enrichment)


def plots(pooled,out):
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    p=pd.read_csv(out/'precision_summary.csv');d=pd.read_csv(out/'continuous_cpd_drift.csv');v=pd.read_csv(out/'independent_validation.csv')
    with PdfPages(out/'EXTENDED_BATCH_FIGURES.pdf') as pdf:
        fig,axes=plt.subplots(4,2,figsize=(12,12))
        for ax,cell in zip(axes.flat,pooled):
            x=cell['validation']['records'][0][1]['context'];w=cell['window'];ax.plot(np.arange(-512,0),x,lw=1)
            ax.set(title=f"{w['dataset_id']}/{w['series_id']} ({w['stratum']}); IQR={cell['result']['context_iqr']:.5g}",xlabel='context coordinate, future excluded')
        fig.tight_layout();pdf.savefig(fig);plt.close(fig)
        fig,axes=plt.subplots(4,2,figsize=(12,12))
        for ax,cell in zip(axes.flat,pooled):
            for metric in ('w1','ed'):
                g=p[p.series.eq(cell['window']['series_id'])&p.metric.eq(metric)].sort_values('N')
                ax.plot(g.N,g.median_distance,'o-',label=metric+' median')
                ax.plot(g.N,g.median_interval_width,'x--',label=metric+' pointwise bootstrap width')
            ax.set(title=cell['window']['series_id'],xlabel='N; 20 selection,40 independent holdout,60 nested pool',ylabel='context IQR units');ax.legend(fontsize=7)
        fig.tight_layout();pdf.savefig(fig);plt.close(fig)
        fig,axes=plt.subplots(4,2,figsize=(12,12))
        for ax,cell in zip(axes.flat,pooled):
            g=v[v.series.eq(cell['window']['series_id'])&v.metric.eq('ed')&v['class'].ne('random_control')]
            labels=[];pos=0
            for phase in ('holdout40','fresh60'):
                for (b,t),c in g[g.phase.eq(phase)].groupby(['b','token'],sort=False):
                    for method in ('raw','persistent','ar1'):
                        q=c[c.method.eq(method)].iloc[0]
                        ax.vlines(pos,q.lo,q.hi,lw=1);ax.plot([pos],[q.distance_iqr],'o',ms=3)
                        labels.append(f'{phase[:1]} {b}/{t} {method[:1]}');pos+=1
            ax.set_xticks(range(pos),labels,rotation=70,fontsize=6);ax.set(title=cell['window']['series_id'],ylabel='ED/IQR; pointwise finite-pool bands')
        fig.tight_layout();pdf.savefig(fig);plt.close(fig)
        fig,axes=plt.subplots(4,2,figsize=(12,12))
        for ax,cell in zip(axes.flat,pooled):
            g=d[d.series.eq(cell['window']['series_id'])&d.kind.eq('cumulative')&d.outcome.eq('terminal_value')]
            ax.plot(g.to_position,g.w1_iqr,'o-',ms=3);ax.fill_between(g.to_position,g.w1_iqr_lo,g.w1_iqr_hi,alpha=.2)
            ax.axvline(10.5,color='gray',ls='--');ax.set(title=cell['window']['series_id'],xlabel='prefix t; both sides N60',ylabel='P0 vs Pt terminal W1/IQR; MC bands not tests')
        fig.tight_layout();pdf.savefig(fig);plt.close(fig)


def review_summary(pooled,out,account):
    branches=pd.read_csv(out/'branch_effects_N60.csv');splits=pd.read_csv(out/'propagation_splits_N60.csv')
    validation=pd.read_csv(out/'independent_validation.csv');ranks=pd.read_csv(out/'rank_stability.csv')
    uncertainty=pd.read_csv(out/'precision_uncertainty.csv');temporal=pd.read_csv(out/'temporal_support_distances.csv')
    local=pd.read_csv(out/'local_cancellation.csv');variance=pd.read_csv(out/'future_variance_partition.csv')
    bounds=[];binary_overlap=[];reuse=[];boundary=[]
    for cell in pooled:
        greedy=np.asarray(cell['result']['greedy_values']);iqr=cell['result']['context_iqr']
        for position in (0,9,10):
            estimate=cell['result']['outcome_distributions'][str(position)]
            direct=cell['validation']['lookup'][(position,'overlap_direct',None)][1]['values']
            events=window_outcomes(direct,greedy,iqr)['events'].reshape(len(direct),10)
            probability=np.asarray(estimate['event_probability']).reshape(10)
            gap=probability-events.mean(axis=0)
            if position<10:
                groups,weights=cell['validation']['groups_by_position'][position]
                proxy=sum(w*w/len(g['values']) for w,g in zip(weights,groups))
            else:proxy=1/60
            totalproxy=proxy+1/len(direct)
            point_radius=np.sqrt(np.log(40)/2*totalproxy)
            family_radius=np.sqrt(np.log(2*len(pooled)*3*10/.05)/2*totalproxy)
            for e in range(10):
                binary_overlap.append({**co(cell),'position':position,'outcome':'terminal' if e<5 else 'last8','threshold':THRESHOLDS[e%5],
                    'probability':probability[e],'direct_probability':events[:,e].mean(),'gap':gap[e],
                    'gap_plugin_se':np.sqrt(np.asarray(estimate['conditional_mc_se']).reshape(10)[e]**2+events[:,e].var(ddof=1)/len(events)),
                    'pointwise_hoeffding_radius':point_radius,'family_hoeffding_radius':family_radius,
                    'pointwise_excludes_zero':abs(gap[e])>point_radius,'family_excludes_zero':abs(gap[e])>family_radius})
        reference=values(cell,9,'reference');events=window_outcomes(reference,greedy,iqr)['events'].reshape(60,10)
        w_g=cell['result']['forks'][9]['selected_weights'][0]
        v9=np.asarray(cell['result']['outcome_distributions']['9']['conditional_mc_se']).reshape(10)**2
        v10=np.asarray(cell['result']['outcome_distributions']['10']['conditional_mc_se']).reshape(10)**2
        v11=np.asarray(cell['result']['outcome_distributions']['11']['conditional_mc_se']).reshape(10)**2
        covariance=w_g*events.var(axis=0,ddof=1)/60
        for e in range(10):
            label={'outcome':'terminal' if e<5 else 'last8','threshold':THRESHOLDS[e%5]}
            reuse.append({**co(cell),**label,'covariance_p9_p10':covariance[e],
                'naive_se_p9_minus_p10':np.sqrt(v9[e]+v10[e]),'corrected_se_p9_minus_p10':np.sqrt(max(0,v9[e]+v10[e]-2*covariance[e]))})
            boundary.append({**co(cell),**label,'P10_N':60,'P11_N':60,'P10_plugin_variance':v10[e],'P11_plugin_variance':v11[e],
                'P10_Hoeffding_proxy':1/60,'P11_Hoeffding_proxy':1/60,'adjacent_independent_se':np.sqrt(v10[e]+v11[e])})
        for fork in cell['result']['forks']:
            b=fork['b'];groups,weights=cell['validation']['groups_by_position'][b]
            proxy=(1-weights[0])**2/len(groups[0]['values'])+sum(w*w/len(g['values']) for w,g in zip(weights[1:],groups[1:]))
            radius=np.sqrt(np.log(40)/2*proxy)
            for _,row in local[(local.window_id==cell['window']['window_id'])&local.b.eq(b)].iterrows():
                bounds.append({**co(cell),'b':b,'event':row.event,'net':row.local_mix_minus_greedy,'cancellation':row.cancellation,
                    'sum_abs_contributions':row.sum_abs_contributions,'hoeffding_radius':radius,
                    'pointwise_bound_excludes_zero':abs(row.local_mix_minus_greedy)>radius})
    bounds=csv(out,'local_contribution_bounds',bounds)
    bo=csv(out,'binary_direct_overlap',binary_overlap);csv(out,'reuse_covariance_N60',reuse);csv(out,'p10_p11_uncertainty',boundary)
    agreement=[]
    for metric in ('w1','ed'):
        g=validation[validation.metric.eq(metric)&validation['class'].ne('random_control')]
        for method in ('raw','persistent','ar1'):
            a=g[g.method.eq(method)].pivot(index=['series','b','token'],columns='phase',values='holm')
            agreement.append({'metric':metric,'method':method,'contrasts':len(a),
                'reject_holdout':int((a.holdout40<=.05).sum()),'reject_fresh':int((a.fresh60<=.05).sum()),
                'reject_both':int(((a.holdout40<=.05)&(a.fresh60<=.05)).sum())})
    csv(out,'independent_rejection_agreement',agreement)
    summary={**account,'primary_alternatives':len(branches),'primary_forks':sum(len(c['result']['forks']) for c in pooled),
        'pooled_N60_alt_le_null_full_W1':int((branches.w1_post<=branches.null_w1_post).sum()),
        'propagation':{'alt_increasing':int(splits.alt_increase.sum()),'null_increasing':int(splits.drop_duplicates(['window_id','b']).null_increase.sum()),
            'excess_increasing':int(splits.excess_increase.sum()),'gain_eligible':int(splits.gain_eligible.sum()),'sign_reversals':int(splits.sign_reversal.sum())},
        'binary_cancellation':{'events':len(local),'nonzero_unsigned':int((local.sum_abs_contributions>0).sum()),
            'cancellation_at_least_half':int((local.cancellation>=.5).sum()),'pointwise_bound_exclusions':int(bounds.pointwise_bound_excludes_zero.sum())},
        'validation_agreement':agreement,'family_sizes':validation.groupby('phase').size().to_dict(),
        'rare_event_zero_plugin_SE':int((pd.read_csv(out/'binary_event_curves.csv').mc_se==0).sum())}
    summary['binary_overlap']={'comparisons':len(bo),'max_absolute_gap':float(bo.gap.abs().max()),
        'pointwise_exclusions':int(bo.pointwise_excludes_zero.sum()),'family_exclusions':int(bo.family_excludes_zero.sum())}
    final=variance[variance.strict_post_fork&(variance.coordinate>=24)].copy()
    final['between_fraction']=final.between_corrected/final.total_corrected
    final['bias_fraction']=final.between_bias/final.between_plugin
    csv(out,'variance_final8_summary',final.groupby(['series','dataset'],sort=False).agg(median_between_fraction=('between_fraction','median'),
        median_bias_fraction=('bias_fraction','median'),negative_corrected=('between_corrected',lambda x:int((x<0).sum()))).reset_index().to_dict('records'))
    summary['negative_between_final8']=int((final.between_corrected<0).sum());summary['variance_final8_estimates']=len(final)
    summary['N20_vs_holdout_rank']=ranks[ranks.design1.eq('N20_block0')&ranks.design2.eq('N40_holdout12')&ranks.top_k.eq(5)][['series','metric','spearman','top_k_overlap']].to_dict('records')
    tests=pd.read_csv(out.parent/'stage_a/independent_baseline_tests.csv')
    direct=pd.read_csv(out.parent/'stage_a/direct_baseline_distances.csv')
    keys=['window_id','series','dataset','b','token','model','metric']
    point=direct[direct.design.eq('holdout40')&direct.support.eq('relative22')]
    point=point[keys+['residual_raw','residual_iqr','untransformed_iqr','same_law_MC_iqr','J_raw','phi','iqr']]
    stage_review=tests.merge(point,on=keys,validate='one_to_one',suffixes=('','_point'))
    stage_review.to_csv(out/'stage_a_review.csv',index=False)
    summary['stage_a_family_size']=len(stage_review);summary['stage_a_rejected_tests']=int((stage_review.holm276<=.05).sum())
    propagated=pd.read_csv(out/'propagation_profiles_N60.csv')
    associations=[]
    for series,g in propagated.groupby('series'):
        unique=g.drop_duplicates(['b','coordinate'])
        associations.append({'series':series,'null_W1_vs_reference_sd_spearman':correlation(unique.null_w1,unique.reference_sd),
            'alternative_W1_vs_reference_sd_spearman':correlation(g.w1,g.reference_sd)})
    csv(out,'dispersion_associations',associations)
    context=[]
    for cell in pooled:
        forks=cell['result']['forks'];w=cell['window'];g=branches[branches.window_id.eq(w['window_id'])]
        context.append({**co(cell),**{k:w[k] for k in ['context_iqr','context_std','lag1','lag24','trend_iqr','diff_std_iqr','half_shift_iqr','zero_fraction']},
            'mean_q50_entropy':np.mean([f['entropy_q50_nats'] for f in forks]),'mean_p_sel_entropy':np.mean([f['entropy_p_sel_nats'] for f in forks]),
            'minimum_selected_mass':min(f['selected_mass'] for f in forks),'maximum_residual_mass':max(f['residual_mass'] for f in forks),
            'cap8_positions':sum(len(f['selected_tokens'])==8 for f in forks),'positions_below90pct':sum(not f['target_attained'] for f in forks),
            'median_abs_J_iqr':g.direct_token_jump_over_context_iqr.median(),'median_bin_width_iqr':g.bin_width_iqr.median(),
            'median_W1_relative22_iqr':g.w1_fixed22_over_context_iqr.median(),'median_ED_relative22_iqr':g.ed_fixed22_over_context_iqr.median()})
    csv(out,'context_regime_by_series',context)
    save(out/'scientific_summary.json',summary)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    parser.add_argument('--stage',choices=['all','core','validation','plots'],default='all');args=parser.parse_args()
    run=args.run.resolve();out=run/'analysis';out.mkdir(exist_ok=True);start=time.perf_counter()
    cells,validations,panel,account=read_cells(run);pooled=pool_cells(cells);config=panel['config']
    verify_saved_policies(run,cells,out)
    csv(out,'cohort_provenance',[{k:w.get(k) for k in ['dataset_id','series_id','stratum','selection_round','window_id',
        'forecast_origin','context_start','context_end_exclusive','context_sha256','context_iqr','source_file','source_sha256',
        'source_row','training_overlap','prior_FPA_exposure']} for w in panel['windows']])
    sources=[Path(__file__).resolve(),ROOT/'scripts/viz/analyze_chronos_pilot_offline.py']
    source_dir=out/'source';source_dir.mkdir(exist_ok=True)
    for path in sources:(source_dir/path.name).write_bytes(path.read_bytes())
    if args.stage in ('all','core'):
        core_results(pooled,out);precision(cells,out,config);direct_baselines(cells,out,config)
        morphology(pooled,out);cpd_and_variance(pooled,out,config['bootstrap_replicates'],config['resampling_seed'])
        events=pd.read_csv(out/'binary_event_curves.csv')
        events['method']=events.method.replace({'reuse20':'reuse_N60_pool3x20','direct60':'direct_N60_pool3x20','mixture':'q50_mixture_N60_pool3x20'})
        events['outcome']=np.where(events.event<5,'terminal','last8');events['threshold']=[THRESHOLDS[int(e)%5] for e in events.event]
        events.to_csv(out/'binary_event_curves.csv',index=False)
    if args.stage in ('all','validation'):independent_validation(run,cells,validations,out,config)
    if args.stage in ('all','plots'):plots(pooled,out)
    attempts=[load(p) for p in (run/'attempts').glob('*.json')]
    account.update(total_paths=account['dense_paths']+account['fresh_paths'],
        model_process_tree_seconds=sum(a['elapsed_seconds'] for a in attempts),
        peak_job_committed_bytes=max(a['peak_job_committed_bytes'] for a in attempts),
        failed_attempts=sum(a['exit_code']!=0 for a in attempts),attempts=len(attempts),
        source_analysis_sha256=sha(__file__),analysis_seconds=time.perf_counter()-start,
        analysis_source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        utc=datetime.now(timezone.utc).isoformat(),pre_user_commit_head=load(run/'environment.json')['git_head'])
    if args.stage=='all':review_summary(pooled,out,account)
    save(out/('execution_'+args.stage+'.json'),account);print(json.dumps(account,indent=2),flush=True)


if __name__=='__main__':main()
