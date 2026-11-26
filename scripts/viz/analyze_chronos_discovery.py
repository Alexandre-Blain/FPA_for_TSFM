"""Scenario discovery/uncertainty benchmarks on complete saved ensembles only.

No inference. Offline policy subsets are limited to observed tokens. All
choices use block0/greedy/context, while evaluation uses independent blocks.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'code/chronos_fpa'),str(ROOT/'scripts/runs')]
import bootstrap  # noqa: E402,F401
from chronos_discovery import EVENT_NAMES,scenario_events,behaviour_codes,coverage,uncertainty_features,risk_ranking
from run_chronos_extended_batch import read_block
from analyze_chronos_extended_batch import pool_cells,concatenate_arrays
from run_chronos_local_pilot import verify_freeze


def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,d):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    Path(p).write_text(json.dumps(d,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else x),encoding='utf-8')
def table(out,name,rows):pd.DataFrame(rows).to_csv(out/name,index=False)


def read_dense(run):
    panel=verify_freeze(run);cells=[]
    for plan in load(run/'cell_plan.json'):
        marker,result,v=read_block(run,plan)
        cells.append({'plan':plan,'result':result,'validation':v,
                      'window':next(w for w in panel['windows'] if w['window_id']==plan['window_id'])})
    return cells,panel


def group(cell,b,role,token=None):
    if role in ('reference','null'):token=cell['result']['greedy_tokens'][b]
    return cell['validation']['lookup'][(b,role,token)]


def first_deviation_groups(cell):
    """Disjoint first-nongreedy prefix partition, plus all-ten-greedy remainder."""
    prefix_mass=1.;groups=[]
    for f in cell['result']['forks']:
        b,g=f['b'],f['greedy_token']
        for t,q in zip(f['selected_tokens'],f['selected_weights']):
            if t!=g:groups.append((prefix_mass*q,group(cell,b,'alternative',t)))
        if f['residual_mass']>0:groups.append((prefix_mass*f['residual_mass'],group(cell,b,'residual')))
        prefix_mass*=f['selected_weights'][f['selected_tokens'].index(g)]
    groups.append((prefix_mass,group(cell,9,'reference')))
    if not np.isclose(sum(w for w,_ in groups),1.,atol=1e-10):raise ValueError('First-deviation partition not normalized')
    return groups


def candidate_rows(cell):
    w=cell['window'];context=group(cell,0,'reference')[1]['context'];greedy=np.asarray(cell['result']['greedy_values']);rows=[]
    for d in cell['result']['distances']:
        b,t=d['b'],d['token'];a=group(cell,b,'alternative',t)[1]['values'];r=group(cell,b,'reference')[1]['values']
        ae,re=scenario_events(a,context,greedy).mean(0),scenario_events(r,context,greedy).mean(0)
        # Consequential fixed outcomes; terminal/persistent/reversal only for candidate selection.
        event=max(range(2,7),key=lambda i:abs(ae[i]-re[i]));delta=(a.mean(0)-r.mean(0))/w['context_iqr']
        rows.append({'window_id':w['window_id'],'dataset':w['dataset_id'],'series':w['series_id'],'b':b,'token':t,
                     'event':event,'event_name':EVENT_NAMES[event],'event_gap':float(abs(ae[event]-re[event])),
                     'signed_event_gap':float(ae[event]-re[event]),'persistent_score':float(abs(delta[-8:].mean())),
                     'transient_score':float(max(0,abs(delta[b+1:b+9].mean())-abs(delta[-8:].mean()))),
                     'sparse_miss_score':float(abs(ae[event]-re[event])*(b>=3)),
                     'q50':d['q50'],'J':d['direct_token_jump'],'w1_iqr':d['w1_fixed22_over_context_iqr']})
    return rows


def targets(w,run):
    if (run/'evaluation_targets.npz').exists():
        with np.load(run/'evaluation_targets.npz') as f:return f[w['window_id']][:32].astype(float)
    with (ROOT/w['source_file']).open(encoding='utf-8') as f:
        row=next(json.loads(s) for s in f if str(json.loads(s)['series_id'])==w['series_id'])
    return np.asarray(row['target'][w['forecast_origin']:w['forecast_origin']+32],float)


def policies(cell,seed=2026112461):
    rng=np.random.default_rng(seed);forks=cell['result']['forks']
    entropy_order=sorted(range(10),key=lambda b:(-forks[b]['entropy_q50_nats'],b))
    positions={'dense':list(range(10)),'early3':[0,1,2],'regular3':[0,4,9],
               'random3':sorted(rng.choice(10,3,replace=False).tolist()),'entropy3':sorted(entropy_order[:3])}
    result={}
    for name,bs in positions.items():
        result[name]=sorted([(b,t) for b in bs for t in forks[b]['selected_tokens']],key=lambda k:(forks[k[0]]['selected_tokens'].index(k[1]),k[0]))
    for label in ['probability2','numeric_extremes2','stratified2']:
        keys=[]
        for f in forks:
            ts=f['selected_tokens']
            if label=='probability2':chosen=ts[:2]
            elif label=='numeric_extremes2':chosen=sorted({min(ts),max(ts)})
            else:chosen=sorted({sorted(ts)[len(ts)//3],sorted(ts)[min(len(ts)-1,2*len(ts)//3)]})
            keys.extend((f['b'],t) for t in chosen)
        result[label]=keys
    return result


def analyze(run,out,*,natural_reference=False):
    start=time.perf_counter();out.mkdir(parents=True,exist_ok=True);cells,panel=read_dense(run);pooled=pool_cells(cells)
    for c in pooled:
        blocks=[x for x in cells if x['plan']['window_id']==c['plan']['window_id']]
        for key,(m,a) in c['validation']['lookup'].items():
            m['metadata']={'generation_seconds':sum(x['validation']['lookup'][key][0]['metadata']['generation_seconds'] for x in blocks)}
    a1=[];candidates=[];effects=[];efficiency=[];discovery=[];probabilities=[];exposure=[]
    for cell in pooled:
        w=cell['window'];wid=w['window_id'];context=group(cell,0,'reference')[1]['context'];greedy=np.asarray(cell['result']['greedy_values']);iqr=w['context_iqr']
        blocks=sorted([c for c in cells if c['plan']['window_id']==wid],key=lambda c:c['plan']['block_index']);first=blocks[0]
        hold={k:concatenate_arrays([blocks[i]['validation']['lookup'][k][1] for i in (1,2)]) for k in cell['validation']['lookup']}
        nat=group(cell,0,'overlap_direct')[1]['values'];y=targets(w,run)
        seasonal_lag={'m4_daily':1,'ercot':24,'exchange_rate':1}.get(w['dataset_id'],48)
        denominator=float(np.mean(abs(context[seasonal_lag:]-context[:-seasonal_lag])))
        features=uncertainty_features(nat,context);dist=cell['result']['distances'];forks=cell['result']['forks']
        features.update({'local_entropy':float(np.mean([f['entropy_q50_nats'] for f in forks])),
            'local_margin_uncertainty':float(np.mean([1-(sorted(f['q50_support_weights'],reverse=True)+[0])[0]+(sorted(f['q50_support_weights'],reverse=True)+[0])[1] for f in forks])),
            'numeric_jump':float(np.mean([d['direct_token_jump']/iqr for d in dist])),
            'dense_FPA_W1':float(np.mean([d['w1_fixed22_over_context_iqr'] for d in dist])),
            'sparse_FPA_W1':float(np.mean([d['w1_fixed22_over_context_iqr'] for d in dist if d['b'] in (0,4,9)])),
            'dense_FPA_ED':float(np.mean([d['ed_fixed22_over_context_iqr'] for d in dist]))})
        for point_name,pred in [('natural_mean',nat.mean(0)),('natural_median',np.median(nat,axis=0)),('greedy',greedy)]:
            mae=float(np.mean(abs(pred-y)));mase=mae/denominator if denominator>0 else np.nan
            a1.append({'window_id':wid,'series':w['series_id'],'dataset':w['dataset_id'],'point_forecast':point_name,
                       'mae':mae,'mae_iqr':mae/iqr,'mase':mase,'seasonal_scale_lag':seasonal_lag,**features})
        local_candidates=candidate_rows(first);candidates.extend(local_candidates)
        for r in local_candidates:
            b,t=r['b'],r['token'];g=cell['result']['greedy_tokens'][b]
            for phase,lookup in [('block0',{k:a for k,(_,a) in first['validation']['lookup'].items()}),('holdout40',hold)]:
                a,ref=lookup[(b,'alternative',t)]['values'],lookup[(b,'reference',g)]['values']
                gap=scenario_events(a,context,greedy).mean(0)-scenario_events(ref,context,greedy).mean(0)
                for event in range(len(EVENT_NAMES)):effects.append({**{k:r[k] for k in ['window_id','series','dataset','b','token']},'phase':phase,'event':event,'event_name':EVENT_NAMES[event],'signed_gap':gap[event]})
        gs=first_deviation_groups(cell)
        for event in range(len(EVENT_NAMES)):
            estimate=0.;variance=0.
            for weight,(_,a) in gs:
                x=scenario_events(a['values'],context,greedy)[:,event];estimate+=weight*x.mean();variance+=weight**2*x.var(ddof=1)/len(x)
            probabilities.append({'window_id':wid,'dataset':w['dataset_id'],'series':w['series_id'],'event':EVENT_NAMES[event],
                                  'natural_probability_first_deviation_estimate':estimate,'plugin_se':np.sqrt(variance),
                                  'natural_N60_probability':scenario_events(nat,context,greedy)[:,event].mean(),
                                  'weights_sum':sum(z[0] for z in gs),'ensembles':len(gs),
                                  'interpretation':'disjoint first deviation q50 mixture, shared inputs, finite independent conditional samples'})
        configured=policies(first);frozen_keys={k:sorted(v) for k,v in configured.items()}
        save(out/(wid+'_offline_policy_subsets.json'),{'chosen_from':'context and deterministic greedy logits only','observed_tokens_only':True,'policies':frozen_keys})
        for phase,lookup in [('block0',first['validation']['lookup']),('holdout40',{k:(cell['validation']['lookup'][k][0],a) for k,a in hold.items()})]:
            ref=nat
            if natural_reference:
                from ensemble_store import read_snapshot
                snap=read_snapshot(run/'natural_reference'/wid/'ensembles');ref=next(a['values'] for m,a in snap['records'] if m['identity']['role']=='natural_reference')
            ref_codes=behaviour_codes(ref,context)
            for budget in ((20,) if phase=='block0' else (20,40)):
                for method,keys in {'natural':[(0,None)],**configured}.items():
                    paths=[];cost=0.
                    # Round-robin allocation. Observed rows only; no bootstrap creates new draws.
                    for index in range(budget):
                        b,t=keys[index%len(keys)];row=index//len(keys)
                        if method=='natural':m,a=group(cell,0,'overlap_direct');a={**a,'values':a['values'][:20] if phase=='block0' else a['values'][20:]}
                        else:
                            role='reference' if t==cell['result']['greedy_tokens'][b] else 'alternative';m,a=lookup[(b,role,t)]
                        if row>=len(a['values']):continue
                        paths.append(a['values'][row]);cost+=float(m.get('metadata',{}).get('generation_seconds',0))/max(int(m['identity']['sample_count']) if isinstance(m['identity']['sample_count'],int) else len(a['values']),1)
                    if not paths:continue
                    codes=behaviour_codes(np.asarray(paths),context);d=coverage(codes,ref_codes)
                    discovery.append({'window_id':wid,'series':w['series_id'],'dataset':w['dataset_id'],'phase':phase,'method':method,
                        'requested_budget':budget,'actual_paths':len(paths),'estimated_generation_seconds':cost,
                        'runtime_status':'offline prorated source generation costs; not a measured prospective runtime',
                        'reference':'fresh held-out N120 natural' if natural_reference else 'pooled P0 N60; overlaps natural method, discovery only',**d})
        # Each branch's consequence score is max over the fixed event catalogue.
        truth={}
        for r in effects:
            if r['window_id']==wid and r['phase']=='holdout40' and 2<=r['event']<=6:truth[(r['b'],r['token'])]=max(truth.get((r['b'],r['token']),0),abs(r['signed_gap']))
        total=sum(truth.values())
        for method,keys in configured.items():
            keyset=set(keys);ret=sum(v for k,v in truth.items() if k in keyset);missing=sorted([(v,b,t) for (b,t),v in truth.items() if (b,t) not in keyset],reverse=True)
            efficiency.append({'window_id':wid,'series':w['series_id'],'dataset':w['dataset_id'],'method':method,'observed_alternatives':len(truth),
                'retained_alternatives':sum(k in keyset for k in truth),'consequence_score_retention':ret/total if total else np.nan,
                'positions':len({b for b,_ in keys}),'largest_missed_event_gap':missing[0][0] if missing else 0,
                'largest_missed_b':missing[0][1] if missing else None,'largest_missed_token':missing[0][2] if missing else None,
                'reference_is_incomplete':'b0..9, collected selected tokens only; future unobserved choices not evaluated'})
        boundary=w.get('documented_temporal_boundary',w.get('source_length',w['forecast_origin']+32)-14 if w['dataset_id']=='m4_daily' else None)
        status=w.get('documented_pretraining_status','in_domain' if w['dataset_id']=='m4_daily' else 'zero_shot')
        for lead in range(32):exposure.append({'window_id':wid,'dataset':w['dataset_id'],'series':w['series_id'],'lead':lead+1,'forecast_origin':w['forecast_origin'],
            'documented_dataset_status':status,'boundary':boundary,'target_status':'potentially_exposed' if status=='in_domain' and boundary is not None and w['forecast_origin']+lead<boundary else 'heldout_in_domain' if status=='in_domain' else 'zero_shot',
            'absolute_error':abs(nat.mean(0)[lead]-y[lead]),'error_iqr':abs(nat.mean(0)[lead]-y[lead])/iqr,'forecast_sd_iqr':nat[:,lead].std(ddof=1)/iqr,
            'membership_evidence':'published dataset/split boundary; exact training sampling not known','source_split':w['source_split']})
    for name,rows in [('forecast_uncertainty.csv',a1),('candidate_discovery.csv',candidates),('event_contrasts.csv',effects),('sampling_efficiency.csv',efficiency),('discovery_coverage.csv',discovery),('natural_probability_mass.csv',probabilities),('exposure_by_lead.csv',exposure)]:table(out,name,rows)
    ranks=[];df=pd.DataFrame(a1)
    for forecast,subset in df.groupby('point_forecast'):
        for scope,ss in [('cohort',subset)]+[(ds,s) for ds,s in subset.groupby('dataset')]:
            if len(ss)<2:continue
            for feature in features:
                if np.isfinite(ss[feature]).all() and np.isfinite(ss.mase).all():ranks.append({'point_forecast':forecast,'scope':scope,'indicator':feature,**risk_ranking(ss[feature],ss.mase)})
    table(out,'uncertainty_ranking.csv',ranks)
    save(out/'offline_complete.json',{'status':'complete','source_run':str(run),'windows':len(pooled),'dense_blocks':len(cells),
        'new_model_draws':0,'ground_truth_used_in_indicators':False,'policy_selection':'deterministic prebranch information, block0 discovery',
        'natural_reference_opened':natural_reference,'analysis_seconds':time.perf_counter()-start,
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    print(json.dumps({'offline_complete':True,'windows':len(pooled),'candidates':len(candidates),'seconds':time.perf_counter()-start}),flush=True)
    return cells,pooled,candidates


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--natural-reference',action='store_true');args=p.parse_args()
    analyze(args.run,args.output,natural_reference=args.natural_reference)
