"""Frozen targeted questions, independent validation and scientific figures.

No model inference. The natural N120 reference is opened only after the
benchmark and N120 contrast plans have been frozen and collection completed.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
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
from chronos_discovery import EVENT_NAMES,scenario_events,behaviour_codes,coverage,choose_validation,risk_ranking
from analyze_chronos_discovery import read_dense,candidate_rows,analyze,group,first_deviation_groups,policies
from run_chronos_discovery import validate_allocation,verify_extra
from run_chronos_extended_batch import read_block
from run_chronos_local_pilot import verify_freeze,load,digest
from run_chronos_microbenchmark import write_json
from ensemble_store import read_snapshot,read_object
from chronos_outcomes import compare_fixed22_and_full


def table(out,name,rows):pd.DataFrame(rows).to_csv(out/name,index=False)
def derived_seed(label):return int(hashlib.sha256(label.encode()).hexdigest()[:16],16)


def freeze_validation(out):
    panel=verify_freeze(out);rows=[];bound={}
    if not (out/'dense_complete.json').exists():raise ValueError('Complete dense collection required before allocation')
    for c in load(out/'cell_plan.json'):
        if c['block_index']!=0:continue
        _,result,v=read_block(out,c);w=next(w for w in panel['windows'] if w['window_id']==c['window_id'])
        rows.extend(candidate_rows({'plan':c,'result':result,'validation':v,'window':w}));bound[c['cell_id']]=digest(out/'cells'/c['cell_id']/'complete.json')
    chosen=choose_validation(rows,seed=panel['config']['validation_selection_seed']);validate_allocation(chosen)
    if len(chosen)!=8:raise ValueError('Available cohort should support exactly8 predefined contrast evaluations')
    benchmark={'methods':['natural','dense','early3','regular3','random3','entropy3','probability2','numeric_extremes2','stratified2','probability_allocation','uniform_allocation'],
        'outcomes':list(EVENT_NAMES),'grouping':'context-IQR terminal/slope/excursion fixed bins, never labelled true modes',
        'budgets':[20,40],'evaluation':'independent holdout40 method samples vs fresh natural120 reference',
        'reference_limit':'finite sample, not oracle; out-of-reference groups remain unobserved',
        'runtime':'actual whole-ensemble times; prorated subset generation cost explicitly an offline estimate',
        'SGA':'pinned author-code conventions, K20/H32; separate teacher-forced entropy replay cost',
        'ground_truth':'only A1 forecast-error/ranking evaluation; never indicators or window selection',
        'source_sha256':digest(ROOT/'scripts/viz/analyze_chronos_discovery.py')}
    plan={'utc':datetime.now(timezone.utc).isoformat(),'contrasts':chosen,'selected_using_blocks':[0],
          'block0_complete_sha256':bound,'scientific_maximum':6,'random_controls':2,'fresh_N':120,
          'permutation_family':'one two-sided fixed-event test per contrast, Holm8',
          'practical_sensitivity':'0.10 absolute event probability; exploratory sensitivity, not a researcher-certified utility threshold',
          'benchmark_plan_sha256':hashlib.sha256(json.dumps(benchmark,sort_keys=True).encode()).hexdigest(),
          'source_sha256':digest(Path(__file__)),'natural_reference_used_for_selection':False}
    for name,doc in [('benchmark_plan.json',benchmark),('validation_plan.json',plan)]:
        path=out/name
        if path.exists():
            existing=load(path)
            if name=='validation_plan.json':doc['utc']=existing['utc']
            if existing!=doc:raise ValueError('Frozen validation/benchmark plan would change')
        else:write_json(path,doc)
    table(out,'frozen_N120_contrasts.csv',chosen)
    print('Frozen8 contrast evaluations;6 scientific+2 random; no natural reference opened',flush=True)


def wilson(successes,n):
    z=1.959963984540054;p=successes/n;d=1+z*z/n;center=(p+z*z/(2*n))/d
    half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return max(0.,center-half),min(1.,center+half)


def event_permutation(a,b,seed,reps=4999):
    # Permuting complete paths under a fixed binary outcome is exactly this
    # hypergeometric label randomization, with no horizon-wise independence.
    a,b=np.asarray(a,bool),np.asarray(b,bool);s=int(a.sum()+b.sum());n=len(a)+len(b);obs=float(a.mean()-b.mean())
    k=np.random.default_rng(seed).hypergeometric(s,n-s,len(a),size=reps)
    null=k/len(a)-(s-k)/len(b)
    return (1+int(np.sum(abs(null)>=abs(obs)-1e-14)))/(reps+1)


def holm(values):
    p=np.asarray(values,float);order=np.argsort(p,kind='stable');adj=np.minimum(1,np.maximum.accumulate(p[order]*(len(p)-np.arange(len(p)))));result=np.empty(len(p));result[order]=adj;return result


def bootstrap_gap(a,b,reference_label,alternative_label,reps=399):
    ia=np.random.default_rng(derived_seed(alternative_label)).integers(len(a),size=(reps,len(a)))
    ib=np.random.default_rng(derived_seed(reference_label)).integers(len(b),size=(reps,len(b)))
    draws=np.asarray(a)[ia].mean(1)-np.asarray(b)[ib].mean(1)
    return float(np.quantile(draws,.025)),float(np.quantile(draws,.975))


def fresh_results(out,analysis):
    panel=verify_freeze(out);plan=load(out/'validation_plan.json');validate_allocation(plan['contrasts']);rows=[];profiles=[];mass=[]
    for number,r in enumerate(plan['contrasts']):
        wid,b,t=r['window_id'],r['b'],r['token'];marker,snapshot=verify_extra(out,wid,'fresh_validation',32)
        lookup={(m['identity']['position'],m['identity']['role'],m['identity']['token']):(m,a) for m,a in snapshot['records']}
        w=next(w for w in panel['windows'] if w['window_id']==wid);base=next(c for c in load(out/'cell_plan.json') if c['window_id']==wid and c['block_index']==0)
        _,result,_=read_block(out,base);g=result['greedy_tokens'][b];ma,a=lookup[(b,'alternative',t)];mr,ref=lookup[(b,'reference',g)];mn,null=lookup[(b,'null',g)]
        context=a['context'];greedy=a['greedy_values'];event=r['validation_outcome'];ae=scenario_events(a['values'],context,greedy)[:,event];re=scenario_events(ref['values'],context,greedy)[:,event];ne=scenario_events(null['values'],context,greedy)[:,event]
        delta=float(ae.mean()-re.mean());lo,hi=bootstrap_gap(ae,re,f'{wid}:{b}:ref',f'{wid}:{b}:{t}:alt')
        al,ah=wilson(int(ae.sum()),len(ae));rl,rh=wilson(int(re.sum()),len(re));metrics,_=compare_fixed22_and_full(ref['values'],a['values'],b,context);nm,_=compare_fixed22_and_full(ref['values'],null['values'],b,context)
        p=event_permutation(ae,re,derived_seed(f'fresh:{wid}:{b}:{t}'))
        signed_jump=float(a['values'][0,b]-ref['values'][0,b]);predictions={}
        for model in ('persistent','ar1'):
            predicted=null['values'].astype(float).copy();predicted[:,b]+=signed_jump
            k=np.arange(1,32-b);shift=np.ones(len(k)) if model=='persistent' else float(w['lag1'])**k
            predicted[:,b+1:]+=signed_jump*shift
            probability=float(scenario_events(predicted,context,greedy)[:,event].mean())
            predictions[model+'_prediction_probability']=probability
            predictions[model+'_event_residual']=float(ae.mean()-probability)
        # Independent holdout selected outcome, preserving the frozen event even if another looks stronger.
        blocks=[c for c in load(out/'cell_plan.json') if c['window_id']==wid and c['block_index'] in (1,2)];ha=[];hr=[]
        for c in blocks:
            _,_,v=read_block(out,c);ha.append(v['lookup'][(b,'alternative',t)][1]['values']);hr.append(v['lookup'][(b,'reference',g)][1]['values'])
        hold=float(scenario_events(np.concatenate(ha),context,greedy)[:,event].mean()-scenario_events(np.concatenate(hr),context,greedy)[:,event].mean())
        prefix_mass=float(np.prod([f['selected_weights'][f['selected_tokens'].index(f['greedy_token'])] for f in result['forks'][:b]]))
        branch_mass=prefix_mass*r['q50']
        rows.append({**r,'N':120,'event_name':EVENT_NAMES[event],'alternative_probability':ae.mean(),'reference_probability':re.mean(),'null_probability':ne.mean(),
            'alternative_wilson_lo':al,'alternative_wilson_hi':ah,'reference_wilson_lo':rl,'reference_wilson_hi':rh,
            'fresh_gap':delta,'fresh_gap_lo':lo,'fresh_gap_hi':hi,'holdout40_gap':hold,'block0_gap':r['signed_event_gap'],
            'direction_reproduced_holdout_fresh':bool(np.sign(r['signed_event_gap'])==np.sign(hold)==np.sign(delta)),
            'sensitivity_abs_gap_at_least_0p10':abs(delta)>=.1,'p':p,'W1_relative22_iqr':metrics['w1_fixed22_over_context_iqr'],
            'ED_relative22_iqr':metrics['ed_fixed22_over_context_iqr'],'same_token_W1_iqr':nm['w1_fixed22_over_context_iqr'],
            'same_token_ED_iqr':nm['ed_fixed22_over_context_iqr'],'alternative_object_id':ma['task_id'],'reference_object_id':mr['task_id'],'null_object_id':mn['task_id'],
            'conditioning_prefix_mass':prefix_mass,'first_deviation_branch_mass':branch_mass,
            'event_natural_mass_component':branch_mass*ae.mean(),'mass_component_wilson_lo':branch_mass*al,'mass_component_wilson_hi':branch_mass*ah,
            'signed_numeric_jump':signed_jump,'signed_jump_iqr':signed_jump/w['context_iqr'],**predictions,
            'CI_status':'pointwise finite-pool bootstrap with shared reference indices; Wilson conditional probabilities'})
        for h in range(32):profiles.append({'window_id':wid,'series':w['series_id'],'b':b,'token':t,'coordinate':h,'strict_post_fork':h>b,
            'mean_response_iqr':float((a['values'][:,h].mean()-ref['values'][:,h].mean())/w['context_iqr']),
            'reference_sd_iqr':float(ref['values'][:,h].std(ddof=1)/w['context_iqr']),
            'alternative_sd_iqr':float(a['values'][:,h].std(ddof=1)/w['context_iqr'])})
    for r,p in zip(rows,holm([r['p'] for r in rows])):r['holm']=p;r['family_size']=len(rows)
    table(analysis,'fresh_N120_validation.csv',rows);table(analysis,'fresh_response_profiles.csv',profiles)
    return rows


def cpd_results(out,analysis):
    curves=[];transitions=[];continuous=[]
    for wid in load(out/'cpd_windows.json')['windows']:
        _,snapshot=verify_extra(out,wid,'cpd',64);_,fresh=verify_extra(out,wid,'cpd_fresh',64)
        lookup={(m['identity']['block'],m['identity']['position']):a for m,a in snapshot['records']};fl={m['identity']['position']:a for m,a in fresh['records']}
        base=lookup[(0,0)];context,greedy=base['context'],base['greedy_values'];scale=float(np.subtract(*np.percentile(context,[75,25])))
        for p in range(31):
            arrays=[lookup[(block,p)]['values'] for block in range(3)]
            for phase,paths in [('block0',arrays[0]),('holdout40',np.concatenate(arrays[1:])),('pool60',np.concatenate(arrays))]:
                events=scenario_events(paths,context,greedy)
                for event,name in enumerate(EVENT_NAMES):
                    lo,hi=wilson(int(events[:,event].sum()),len(events));curves.append({'window_id':wid,'prefix':p,'phase':phase,'event':event,'event_name':name,'N':len(paths),'probability':events[:,event].mean(),'wilson_lo':lo,'wilson_hi':hi})
                continuous.append({'window_id':wid,'prefix':p,'phase':phase,'terminal_mean_iqr':float(np.mean((paths[:,-1]-context[-1])/scale)),
                    'late8_mean_iqr':float(np.mean((paths[:,-8:]-context[-1])/scale)),
                    'terminal_sd_iqr':float(paths[:,-1].std(ddof=1)/scale),'late8_mean_absolute_from_greedy_iqr':float(np.mean(abs(paths[:,-8:]-greedy[-8:]))/scale),
                    'same_absolute_coordinates':'terminal63, late56..63 at every prefix; no mixture/direct estimator boundary'})
        for t in load(out/'cpd_selections'/(wid+'.json'))['transitions']:
            p,q,event=t['left'],t['right'],t['event'];ae=scenario_events(fl[q]['values'],context,greedy)[:,event];re=scenario_events(fl[p]['values'],context,greedy)[:,event]
            ha=np.concatenate([lookup[(b,q)]['values'] for b in (1,2)]);hr=np.concatenate([lookup[(b,p)]['values'] for b in (1,2)])
            hold=float(scenario_events(ha,context,greedy)[:,event].mean()-scenario_events(hr,context,greedy)[:,event].mean())
            lo,hi=bootstrap_gap(ae,re,f'cpd:{wid}:P{p}',f'cpd:{wid}:P{q}')
            transitions.append({'window_id':wid,**t,'event_name':EVENT_NAMES[event],'holdout40_gap':hold,
                'fresh120_gap':float(ae.mean()-re.mean()),'fresh_gap_lo':lo,'fresh_gap_hi':hi,
                'left_probability':re.mean(),'right_probability':ae.mean(),
                'p':event_permutation(ae,re,derived_seed(f'cpd:{wid}:{p}:{q}')),
                'direction_reproduced':bool(np.sign(t['block0_gap'])==np.sign(hold)==np.sign(ae.mean()-re.mean())),
                'interpretation':'conditional probability change under another greedy token; not a formal structural change point'})
    for r,p in zip(transitions,holm([r['p'] for r in transitions])):r['holm']=p;r['family_size']=len(transitions)
    table(analysis,'cpd_H64_event_curves.csv',curves);table(analysis,'cpd_H64_continuous_curves.csv',continuous);table(analysis,'cpd_H64_validation.csv',transitions)
    return transitions


def allocation_results(out,cells,analysis):
    rows=[];runtime_rows=[];mass_rows=[]
    for wid in dict.fromkeys(c['plan']['window_id'] for c in cells):
        blocks=sorted([c for c in cells if c['plan']['window_id']==wid],key=lambda c:c['plan']['block_index']);first=blocks[0]
        _,ref=verify_extra(out,wid,'natural_reference',32);natural=ref['records'][0][1]['values'];context=ref['records'][0][1]['context'];refcodes=behaviour_codes(natural,context)
        keys=policies(first)['dense'];q=np.array([first['result']['forks'][b]['selected_weights'][first['result']['forks'][b]['selected_tokens'].index(t)] for b,t in keys]);q/=q.sum()
        pool={}
        for b,t in keys:
            role='reference' if t==first['result']['greedy_tokens'][b] else 'alternative'
            pool[(b,t)]=np.concatenate([group(c,b,role,t)[1]['values'] for c in blocks[1:]])
        natural_exploration=np.concatenate([group(c,0,'overlap_direct')[1]['values'] for c in blocks[1:]])
        for budget in (20,40):
            for method,policy_keys in {'natural':[(0,None)],**policies(first)}.items():
                paths=[]
                for index in range(budget):
                    k=policy_keys[index%len(policy_keys)];row=index//len(policy_keys)
                    paths.append(natural_exploration[row] if method=='natural' else pool[k][row])
                codes=behaviour_codes(paths,context);covered=np.isin(refcodes,np.unique(codes));lo,hi=wilson(int(covered.sum()),len(covered))
                result={'window_id':wid,'dataset':first['window']['dataset_id'],'series':first['window']['series_id'],
                    'method':method,'budget':budget,'actual_paths':len(paths),**coverage(codes,refcodes),
                    'reference_observed_mass_covered':float(covered.mean()),'reference_mass_wilson_lo':lo,'reference_mass_wilson_hi':hi,
                    'reference':'independent natural120, finite observed mass; forced sample frequencies are never probability masses'}
                mass_rows.append(result)
                if method=='natural':mass_rows.append({**result,'method':'SGA_natural_sampler_same_paths'})
        for budget in (20,40):
            for allocation in ('uniform_allocation','probability_allocation'):
                rng=np.random.default_rng(derived_seed(wid+allocation+str(budget)));counts={k:0 for k in keys};paths=[]
                for _ in range(budget):
                    weights=q.copy() if allocation.startswith('probability') else np.ones(len(keys))
                    for i,k in enumerate(keys):
                        if counts[k]>=len(pool[k]):weights[i]=0
                    index=int(rng.choice(len(keys),p=weights/weights.sum()));k=keys[index];paths.append(pool[k][counts[k]]);counts[k]+=1
                codes=behaviour_codes(paths,context)
                result={'window_id':wid,'dataset':first['window']['dataset_id'],'series':first['window']['series_id'],
                    'method':allocation,'budget':budget,'actual_paths':len(paths),'represented_branches':sum(v>0 for v in counts.values()),
                    **coverage(codes,refcodes),'reference_observed_mass_covered':float(np.isin(refcodes,np.unique(codes)).mean()),
                    'status':'offline allocation among observed conditional samples; weights across positions are exploration heuristics, not natural mass'}
                rows.append(result);mass_rows.append(result)
        natural_costs=[group(c,0,'overlap_direct')[0]['metadata']['generation_seconds'] for c in blocks[1:]]
        for target_blocks in (1,2):
            budget=float(sum(natural_costs[:target_blocks]))
            for method,policy_keys in {'natural':[(0,None)],**policies(first)}.items():
                observed=[]
                for c in blocks[1:]:
                    for b,t in policy_keys:
                        role='overlap_direct' if method=='natural' else 'reference' if t==first['result']['greedy_tokens'][b] else 'alternative'
                        observed.append(group(c,b,role,t))
                paths=[];cost=0.;ensembles=0
                for m,a in observed:
                    elapsed=float(m['metadata']['generation_seconds'])
                    if cost+elapsed>budget+1e-9:break
                    paths.append(a['values']);cost+=elapsed;ensembles+=1
                values=np.concatenate(paths) if paths else np.empty((0,32))
                runtime_rows.append({'window_id':wid,'method':method,'budget_seconds':budget,'actual_recorded_generation_seconds':cost,
                    'ensembles':ensembles,'paths':len(values),**coverage(behaviour_codes(values,context),refcodes),
                    'status':'offline prefix of fixed policy order using whole measured N20 ensemble costs; excludes shared encoder/greedy and reload costs; no prescient skipping'})
    table(analysis,'allocation_coverage.csv',rows)
    table(analysis,'runtime_matched_whole_ensembles.csv',runtime_rows)
    table(analysis,'discovery_mass_coverage.csv',mass_rows)


def sga_results(out,analysis):
    rows=[]
    for w in load(out/'selection_manifest.json')['windows']:
        wid=w['window_id'];directory=out/'sga_replay'/wid;marker=load(directory/'complete.json')
        for n,h in marker['files'].items():
            if digest(directory/n)!=h:raise ValueError('SGA inputs changed')
        d=pd.read_csv(directory/'scores.csv');d['dataset']=w['dataset_id'];d['series']=w['series_id'];rows.extend(d.to_dict('records'))
    table(analysis,'sga_independent_blocks.csv',rows)
    scores=pd.DataFrame(rows).groupby(['window_id','dataset','series'],as_index=False).agg(sga_score_mean=('sga_author_code','mean'),sga_score_min=('sga_author_code','min'),sga_score_max=('sga_author_code','max'))
    point=pd.read_csv(analysis/'new_H32/forecast_uncertainty.csv');scores=scores.merge(point[point.point_forecast=='natural_mean'][['window_id','mase']],on='window_id',validate='one_to_one')
    table(analysis,'sga_by_source.csv',scores.to_dict('records'));rankings=[]
    for scope,d in [('cohort',scores)]+[(ds,g) for ds,g in scores.groupby('dataset')]:
        if len(d)>1 and np.isfinite(d.mase).all():rankings.append({'scope':scope,'indicator':'SGA_author_code_H32_K20_mean_of_three_independent_blocks',**risk_ranking(d.sga_score_mean,d.mase)})
    table(analysis,'sga_uncertainty_ranking.csv',rankings)


def conventional_comparison(out,cells,analysis):
    point=pd.read_csv(analysis/'new_H32/forecast_uncertainty.csv');extras=[]
    for wid in dict.fromkeys(c['plan']['window_id'] for c in cells):
        c=next(c for c in cells if c['plan']['window_id']==wid);forks=c['result']['forks']
        greedy_q=[f['selected_weights'][f['selected_tokens'].index(f['greedy_token'])] for f in forks]
        greedy_p=[f['p_sel_selected'][f['selected_tokens'].index(f['greedy_token'])] for f in forks]
        sg=pd.read_csv(out/'sga_replay'/wid/'scores.csv')
        extras.append({'window_id':wid,'greedy_token_uncertainty':1-np.mean(greedy_q),
            'p_sel_greedy_uncertainty':1-np.mean(greedy_p),'p_sel_entropy':np.mean([f['entropy_p_sel_nats'] for f in forks]),
            'SGA_author_code_H32_3xK20':sg.sga_author_code.mean()})
    merged=point.merge(pd.DataFrame(extras),on='window_id',validate='many_to_one');merged.to_csv(analysis/'conventional_comparison_by_window.csv',index=False)
    indicators=['mean_sd_iqr','interval80_iqr','trajectory_rms_diversity_iqr','scenario_entropy','scenario_groups','local_entropy',
        'local_margin_uncertainty','greedy_token_uncertainty','p_sel_greedy_uncertainty','p_sel_entropy','numeric_jump',
        'dense_FPA_W1','sparse_FPA_W1','dense_FPA_ED','SGA_author_code_H32_3xK20'];rows=[]
    for forecast,ss in merged.groupby('point_forecast'):
        for scope,d in [('new_cohort',ss)]+[(ds,g) for ds,g in ss.groupby('dataset')]:
            for indicator in indicators:
                if np.isfinite(d[indicator]).all() and np.isfinite(d.mase).all():rows.append({'scope':scope,'point_forecast':forecast,'indicator':indicator,**risk_ranking(d[indicator],d.mase)})
    table(analysis,'conventional_uncertainty_ranking.csv',rows)


def cohort_review(out,cells,analysis):
    panel=load(out/'selection_manifest.json');point=pd.read_csv(analysis/'conventional_comparison_by_window.csv');rows=[];seasonal=[]
    with np.load(out/'evaluation_targets.npz') as y:
        for w in panel['windows']:
            wid=w['window_id'];c=next(c for c in cells if c['plan']['window_id']==wid);context=group(c,0,'reference')[1]['context']
            p=point[(point.window_id==wid)&(point.point_forecast=='natural_mean')].iloc[0]
            row={**w,**{k:p[k] for k in ['mae','mae_iqr','mase','mean_sd_iqr','interval80_iqr','dense_FPA_W1','scenario_entropy','SGA_author_code_H32_3xK20']}}
            row['selection_role']='context diversity' if w['selection_slot']==1 else 'uniform representative draw'
            row['exposure_label_authority']='documented_pretraining_status and index boundary; shared raw stratum suffixes are not exposure labels'
            row['lag48_context']=float(np.corrcoef(context[:-48],context[48:])[0,1]);row['lag336_context']=float(np.corrcoef(context[:-336],context[336:])[0,1]);rows.append(row)
            prediction=np.resize(context[-48:],32);truth=y[wid][:32]
            for lead in range(32):seasonal.append({'window_id':wid,'series':w['series_id'],'dataset':w['dataset_id'],'lead':lead+1,
                'seasonal_naive_error_iqr':float(abs(prediction[lead]-truth[lead])/w['context_iqr']),
                'baseline':'repeat last48 context values; no model or future inputs'})
    table(analysis,'dataset_provenance_review.csv',rows);table(analysis,'seasonal_naive_exposure_control.csv',seasonal)


def first_deviation_reproducibility(cells,analysis,name):
    rows=[]
    for wid in dict.fromkeys(c['plan']['window_id'] for c in cells):
        blocks=sorted([c for c in cells if c['plan']['window_id']==wid],key=lambda c:c['plan']['block_index']);first=blocks[0]
        gs=first_deviation_groups(first);context=group(first,0,'reference')[1]['context'];greedy=first['result']['greedy_values']
        for phase,indices in [('block0',[0]),('block1',[1]),('block2',[2]),('holdout40',[1,2]),('pool60',[0,1,2])]:
            probability=np.zeros(8);variance=np.zeros(8)
            for weight,(manifest,_) in gs:
                identity=manifest['identity'];b,role,t=identity['position'],identity['role'],identity.get('token')
                paths=np.concatenate([group(blocks[i],b,role,t)[1]['values'] for i in indices]);events=scenario_events(paths,context,greedy)
                probability+=weight*events.mean(0);variance+=weight**2*events.var(0,ddof=1)/len(events)
            natural=np.concatenate([group(blocks[i],0,'overlap_direct')[1]['values'] for i in indices]);ne=scenario_events(natural,context,greedy)
            for event in range(8):rows.append({'window_id':wid,'series':first['window']['series_id'],'dataset':first['window']['dataset_id'],
                'phase':phase,'event':EVENT_NAMES[event],'first_deviation_probability':probability[event],'plugin_se':np.sqrt(variance[event]),
                'natural_probability':ne[:,event].mean(),'natural_count':int(ne[:,event].sum()),'natural_N':len(ne),
                'interpretation':'independent conditional-group mixture; finite plug-in SE can be optimistic near zero; not independent source replication'})
    table(analysis,name,rows)


def natural_reference_comparison(out,cells,analysis):
    estimates=pd.read_csv(analysis/'first_deviation_independent_blocks.csv');rows=[]
    for wid in dict.fromkeys(c['plan']['window_id'] for c in cells):
        blocks=[c for c in cells if c['plan']['window_id']==wid];first=next(c for c in blocks if c['plan']['block_index']==0)
        _,snapshot=verify_extra(out,wid,'natural_reference',32);m,reference=snapshot['records'][0]
        events=scenario_events(reference['values'],reference['context'],reference['greedy_values']);generation=sum(item[0]['metadata']['generation_seconds'] for c in blocks for _,item in first_deviation_groups(c))
        for event,name in enumerate(EVENT_NAMES):
            d=estimates[(estimates.window_id==wid)&(estimates.event==name)];pooled=d[d.phase=='pool60'].iloc[0];hold=d[d.phase=='holdout40'].iloc[0]
            count=int(events[:,event].sum());lo,hi=wilson(count,120)
            rows.append({'window_id':wid,'series':first['window']['series_id'],'dataset':first['window']['dataset_id'],'event':name,
                'first_deviation_holdout40_probability':hold.first_deviation_probability,'first_deviation_pool60_probability':pooled.first_deviation_probability,
                'first_deviation_pool60_plugin_se':pooled.plugin_se,'natural_reference_count':count,'natural_reference_N':120,
                'natural_reference_probability':count/120,'natural_reference_wilson_lo':lo,'natural_reference_wilson_hi':hi,
                'first_deviation_generation_seconds':generation,'natural120_generation_seconds':m['metadata']['generation_seconds'],
                'estimated_zero_count_chance_at_FPA_point_probability':float((1-pooled.first_deviation_probability)**120),
                'interpretation':'finite independent reference; plug-in miss chance is descriptive, not a p-value; probability weights are q50 first-deviation masses'})
    table(analysis,'natural_reference_comparison.csv',rows)


def execution_costs(out,analysis):
    rows=[];streams=[];derived=[]
    for phase in ['cells','fresh_validation','natural_reference','cpd','cpd_fresh']:
        for directory in sorted((out/phase).glob('*/ensembles')):
            snap=read_snapshot(directory)
            for m,a in snap['records']:
                i=m['identity'];rng=m['metadata']['rng'];streams.append(rng['stream_id']);derived.append(rng['seed'])
                rows.append({'phase':phase,'window_id':i['window_id'],'dataset':i['dataset_id'],'series':i['series_id'],
                    'role':i['role'],'position':i['position'],'token':i.get('token'),'N':len(a['tokens']),'horizon':a['tokens'].shape[1],
                    'fixed_prefix_length':len(i['prefix']),'stochastic_generated_tokens':len(a['tokens'])*(a['tokens'].shape[1]-len(i['prefix'])),
                    'generation_seconds':m['metadata']['generation_seconds'],'stream_id':rng['stream_id'],'derived_seed':rng['seed'],
                    'root_seed':rng['root_seed'],'scope_sampling_seed':i['sampling_seed'],'object_id':m['task_id']})
    if len(streams)!=len(set(streams)) or len(derived)!=len(set(derived)):raise ValueError('Reused RNG across discovery phases')
    attempts=[load(p) for p in (out/'attempts').glob('*.json')]
    report={'ensembles':len(rows),'unique_rng_streams':len(set(streams)),'unique_derived_seeds':len(set(derived)),
        'trajectories':sum(r['N'] for r in rows),'stochastic_generated_tokens':sum(r['stochastic_generated_tokens'] for r in rows),
        'phase_counts':{},'model_process_tree_seconds':sum(x['elapsed_seconds'] for x in attempts),
        'peak_job_committed_bytes':max(x['peak_job_committed_bytes'] for x in attempts),
        'min_system_free_bytes':min(s['system_free_bytes'] for x in attempts for s in x['samples']),
        'attempts':len(attempts),'failed_attempts':sum(x['exit_code']!=0 for x in attempts),
        'scope_seed_note':'CPD uses a phase-level scope sampling_seed; actual independent N20 root seeds are rng.root_seed and derived_seed, with block-specific role labels',
        'source_head':load(out/'environment.json')['git_head']}
    for phase in ['cells','fresh_validation','natural_reference','cpd','cpd_fresh']:
        r=[x for x in rows if x['phase']==phase];report['phase_counts'][phase]={'ensembles':len(r),'trajectories':sum(x['N'] for x in r),'generation_seconds':sum(x['generation_seconds'] for x in r),'stochastic_generated_tokens':sum(x['stochastic_generated_tokens'] for x in r)}
    table(analysis,'actual_execution_costs.csv',rows);write_json(analysis/'execution_cost_summary.json',report)
    return report


def make_whitebox_plan(out):
    rows=pd.read_csv(out/'analysis/fresh_N120_validation.csv').to_dict('records')
    positives=[r for r in rows if r['holm']<=.05 and abs(r['fresh_gap'])>=.1]
    strong=max(positives or rows,key=lambda r:abs(r['fresh_gap']));weak=min(rows,key=lambda r:abs(r['fresh_gap']))
    cases=[]
    for name,row,role in [('consequential' if positives else 'strongest_unresolved',strong,'alternative'),('weak_event_contrast',weak,'alternative'),('same_token_control',weak,'null')]:
        wid=row['window_id'];verify_extra(out,wid,'fresh_validation',32)
        selected=[row['reference_object_id'],row['alternative_object_id'] if role=='alternative' else row['null_object_id']]
        cases.append({'name':name,'window_id':wid,'b':int(row['b']),'validation_holm':row['holm'],'validation_event_gap':row['fresh_gap'],
            'paths':[{'object_directory':f'fresh_validation/{wid}/ensembles/{object_id}','row':0} for object_id in selected]})
    first=next(c for c in load(out/'cell_plan.json') if c['block_index']==0);summary=load(out/'cells'/first['cell_id']/'capture_summary.json');capture_id=summary['profiles'][0]['task_id']
    relative=f'cells/{first["cell_id"]}/captures/{capture_id}'
    cases.append({'name':'historical_sentinel','window_id':first['window_id'],'b':0,'paths':[{'object_directory':relative,'row':i} for i in (0,1)],
                  'historical_capture_directory':relative,'historical_encoder_directory':f'cells/{first["cell_id"]}/captures/{summary["shared_encoder_task_id"]}'})
    doc={'cases':cases,'selection':'fresh results: strongest corrected >=10pp consequence if any, otherwise explicitly unresolved; weakest fixed-event gap (not a globally null law); independent same-token control; first fixed original capture',
        'inference_limit':'deterministic replay of existing paths only, no new draws; original online activations absent',
        'source_results_sha256':digest(out/'analysis/fresh_N120_validation.csv')}
    path=out/'whitebox_plan.json'
    if path.exists():
        if load(path)!=doc:raise ValueError('White-box plan changed')
    else:write_json(path,doc)


def run_analysis(out):
    start=time.perf_counter();analysis=out/'analysis';analysis.mkdir(exist_ok=True)
    if not (out/'validation_plan.json').exists():raise ValueError('Freeze the questions first')
    if load(out/'validation_plan.json')['source_sha256']!=digest(Path(__file__)):raise ValueError('Scientific question/analysis code changed after allocation')
    cfg=verify_freeze(out)['config']
    benchmark=load(out/'benchmark_plan.json')
    if hashlib.sha256(json.dumps(benchmark,sort_keys=True).encode()).hexdigest()!=load(out/'validation_plan.json')['benchmark_plan_sha256']:raise ValueError('Benchmark plan changed after contrast freeze')
    if benchmark['source_sha256']!=digest(ROOT/'scripts/viz/analyze_chronos_discovery.py'):raise ValueError('Benchmark code changed after plan')
    cells,pooled,candidates=analyze(out,analysis/'new_H32',natural_reference=True)
    fresh=fresh_results(out,analysis);cpd=cpd_results(out,analysis);allocation_results(out,cells,analysis);sga_results(out,analysis);conventional_comparison(out,cells,analysis);cohort_review(out,cells,analysis);execution_costs(out,analysis)
    first_deviation_reproducibility(cells,analysis,'first_deviation_independent_blocks.csv')
    natural_reference_comparison(out,cells,analysis)
    make_whitebox_plan(out)
    write_json(analysis/'scientific_execution.json',{'status':'complete','new_model_draws':0,'seconds':time.perf_counter()-start,
        'source_sha256':digest(Path(__file__)),'fresh_contrasts':len(fresh),'cpd_transitions':len(cpd),'natural_reference_opened_after_plan_freeze':True})
    print('SCIENTIFIC ANALYSIS COMPLETE',len(fresh),'contrasts;',len(cpd),'transitions',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--freeze-validation',action='store_true');p.add_argument('--analyze',action='store_true');args=p.parse_args()
    if args.freeze_validation:freeze_validation(args.output)
    elif args.analyze:run_analysis(args.output)
    else:p.error('Select freeze or analysis')
