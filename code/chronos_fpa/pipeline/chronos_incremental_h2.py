"""Prospective event estimation; allocation pilots never enter final estimates.

Ordinary stratification and exact stratum-mixture importance sampling estimate
the same q50 path law. No actual held-out future is read by this module.
"""
from __future__ import annotations

import hashlib
import json
import math
import time

import numpy as np

from chronos_incremental import (EVENT_NAMES, first_token_partition,
    first_deviation_partition, future_events, budget_allocation,
    stratified_estimate, importance_estimate)
from chronos_incremental_collection import seed_for
from results_io import save_json


def jsonable(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, dict): return {k:jsonable(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [jsonable(v) for v in value]
    return value


def cost_key(group):
    kind = 'prefix' if not group['support'] else 'single' if len(group['support'])==1 else 'mixed'
    return f'{kind}_b{group["position"]}'


def event_variability(pilot_events):
    """Jeffreys smoothing prevents zero-count pilots removing rare strata.

    This is an allocation heuristic, not the final event-probability estimator.
    All four fixed events receive the same weight.
    """
    return np.array([np.mean(((a.sum(0)+.5)/(len(a)+1)) *
        (1-(a.sum(0)+.5)/(len(a)+1))) for a in pilot_events])


def allocation_plan(partitions, cost_model, pilot_events, pilot_seconds,
                    anchors, minimum=2):
    """All production counts are fixed from independent pilots before drawing.

    Global per-path costs come only from the five technical windows. Outcome-
    adaptive methods pay the complete local pilot cost at EACH estimate/anchor.
    Fixed policies have no local outcome pilot dependency.
    """
    one, dev = partitions['first_token'], partitions['first_deviation']
    w = np.array([g['weight'] for g in dev]); v = event_variability(pilot_events)
    costs = np.array([cost_model[cost_key(g)] for g in dev])
    neyman = w*np.sqrt(v/costs); neyman /= neyman.sum()
    proposal = .5*w+.5*neyman
    methods = {
        'first_token_proportional': (one,'proportional',0.),
        'first_deviation_uniform': (dev,'uniform',0.),
        'first_deviation_proportional': (dev,'proportional',0.),
        'first_deviation_neyman_cost': (dev,'neyman_cost',pilot_seconds),
    }
    plans=[]
    for anchor in anchors:
        budget = anchor*cost_model['natural']
        for name,(groups,strategy,charge) in methods.items():
            group_w=np.array([g['weight'] for g in groups])
            group_c=np.array([cost_model[cost_key(g)] for g in groups])
            n=budget_allocation(group_w,group_c,budget-charge,strategy,
                v if strategy=='neyman_cost' else None,minimum)
            plans.append({'method':name,'anchor':anchor,'feasible':n is not None,
                'counts':None if n is None else n.tolist(),'partition': 'first_token' if groups is one else 'first_deviation',
                'pilot_seconds_charged':charge,'planned_variable_budget_seconds':budget})
        available=budget-pilot_seconds
        n=max(0,int(math.floor(available/float(proposal@costs))))
        plans.append({'method':'stratum_mixture_IS','anchor':anchor,'feasible':n>=2,
            'N':n,'partition':'first_deviation','proposal':proposal.tolist(),
            'pilot_seconds_charged':pilot_seconds,'planned_variable_budget_seconds':budget})
    return {'plans':plans,'pilot_variability':v.tolist(),
            'importance_proposal':proposal.tolist(), 'cost_model':cost_model}


def _events(collector, arrays):
    return future_events(arrays['values'],collector.context,collector.greedy_values)


def collect_h2(collector):
    start=time.perf_counter();config=collector.config;directory=collector.directory
    partitions={'first_token':first_token_partition(collector.forks),
                'first_deviation':first_deviation_partition(collector.forks)}
    pilot_events=[];pilot_seconds=0.;pilot_ids=[]
    for g in partitions['first_deviation']:
        m,a=collector.draw('allocation_pilot_'+g['name'],g['prefix'],g['support'],
            config['h2_allocation_pilot_per_stratum'],'h2_allocation_pilot',g['position'])
        pilot_events.append(_events(collector,a));pilot_seconds+=m['metadata']['generation_seconds']
        pilot_ids.append(m['task_id'])
    plan=allocation_plan(partitions,config['h2_cost_model'],pilot_events,pilot_seconds,
        config['h2_budget_anchors'],config['h2_minimum_per_stratum'])
    repetitions=config['h2_final_repetitions'] if collector.window['replicated10'] else 1
    plan.update(partitions=partitions,repetitions=repetitions,pilot_object_ids=pilot_ids,
        natural_matching_rule='round up to batch multiple using independent stratum runtime / frozen technical natural seconds per path; never use MC outcomes or MC runtime to choose N',
        matched_natural_cap=config['h2_matched_natural_cap'])
    text=json.dumps(plan,sort_keys=True,allow_nan=False)
    plan_hash=hashlib.sha256(text.encode()).hexdigest()
    plan.update(plan_sha256=plan_hash)
    plan_path=directory/'allocation_plan.json'
    if plan_path.exists():
        old=json.loads(plan_path.read_text(encoding='utf-8'))
        if old!=plan:raise ValueError('Frozen per-window allocation changed on resume')
    else:save_json(plan_path,plan)

    rows=[]
    for rep in range(repetitions):
        for method in config['h2_methods']:
            if method=='MC':continue
            specifications=[p for p in plan['plans'] if p['method']==method]
            previous=None;data=None;cumulative=0.
            if method=='stratum_mixture_IS':
                maximum=max([p['N'] for p in specifications if p['feasible']],default=0)
                mixture_seed=seed_for(config['root_seed'],collector.window['window_id']+f':H2:IS_choices:{rep}:{plan_hash}')
                choices=np.random.default_rng(mixture_seed).choice(len(partitions['first_deviation']),
                    size=maximum,p=np.array(plan['importance_proposal']))
            for spec in specifications:
                common={'window_id':collector.window['window_id'],'dataset_id':collector.window['dataset_id'],
                    'series_id':collector.window['series_id'],'rep':rep,'method':method,
                    'anchor':spec['anchor'],'feasible':spec['feasible'],'allocation_plan_sha256':plan_hash}
                if not spec['feasible']:
                    rows.append(common);continue
                groups=partitions[spec['partition']]
                if method=='stratum_mixture_IS':
                    selected=choices[:spec['N']];counts=np.bincount(selected,minlength=len(groups))
                else:counts=np.array(spec['counts'],int)
                if previous is None:
                    previous=np.zeros(len(groups),int);data=[[] for _ in groups]
                if (counts<previous).any():raise ValueError('Budgets must give nested allocation')
                for j,(g,n,old) in enumerate(zip(groups,counts,previous)):
                    if n>old:
                        m,a=collector.draw(f'{method}_rep{rep}_anchor{spec["anchor"]}_{g["name"]}',
                            g['prefix'],g['support'],int(n-old),'h2_production',g['position'],block=rep)
                        cumulative+=m['metadata']['generation_seconds'];data[j].append(_events(collector,a))
                events=[np.concatenate(a) if a else np.empty((0,4),bool) for a in data]
                weights=[g['weight'] for g in groups]
                compute_start=time.perf_counter()
                if method=='stratum_mixture_IS':
                    indices=np.repeat(np.arange(len(groups)),counts)
                    estimate=importance_estimate(indices,np.concatenate(events),weights,spec['proposal'])
                else:estimate=stratified_estimate(events,weights)
                aggregation_seconds=time.perf_counter()-compute_start
                rows.append({**common,**jsonable(estimate),'counts':counts.tolist(),'N':int(counts.sum()),
                    'production_seconds':cumulative,'pilot_seconds_charged':spec['pilot_seconds_charged'],
                    'variable_seconds':cumulative+spec['pilot_seconds_charged'],
                    'common_setup_seconds':collector.setup_seconds,'aggregation_seconds':aggregation_seconds,
                    'importance_choice_seed':mixture_seed if method=='stratum_mixture_IS' else None})
                previous=counts

        # Choose every MC sample size BEFORE drawing this replicate's MC pool.
        # Runtime of independent conditional samples may select N. Natural sample
        # counts are never stopped or selected by their own values or runtimes.
        rep_rows=[r for r in rows if r['rep']==rep and r['feasible']]
        batch=config['batch_size'];cap=config['h2_matched_natural_cap'];needed=set(config['h2_budget_anchors'])
        for r in rep_rows:
            uncapped=max(2,int(math.ceil(r['variable_seconds']/config['h2_cost_model']['natural']/batch))*batch)
            r['matched_MC_N']=min(cap,uncapped);r['matching_capped']=uncapped>cap;needed.add(r['matched_MC_N'])
        pool=[];previous=0;mc_seconds=0.;mc_by_n={}
        for n in sorted(needed):
            m,a=collector.draw(f'MC_rep{rep}_throughN{n}',[],[],n-previous,'h2_natural',0,block=rep)
            pool.append(_events(collector,a));mc_seconds+=m['metadata']['generation_seconds']
            all_events=np.concatenate(pool)
            estimate=stratified_estimate([all_events],[1.])
            mc_by_n[n]={**jsonable(estimate),'N':n,'production_seconds':mc_seconds,
                'pilot_seconds_charged':0.,'variable_seconds':mc_seconds,'common_setup_seconds':collector.setup_seconds}
            previous=n
        for r in rep_rows:
            control=mc_by_n[r['matched_MC_N']]
            ratio=control['variable_seconds']/r['variable_seconds']
            rows.append({'window_id':collector.window['window_id'],'dataset_id':collector.window['dataset_id'],
                'series_id':collector.window['series_id'],'rep':rep,'method':'matched_MC',
                'matched_to':r['method'],'anchor':r['anchor'],'feasible':True,**control,
                'matching_capped':r['matching_capped'],'actual_cost_ratio_to_method':ratio,
                'within_25pct_actual_cost':not r['matching_capped'] and .8<=ratio<=1.25})
        for anchor in config['h2_budget_anchors']:
            rows.append({'window_id':collector.window['window_id'],'dataset_id':collector.window['dataset_id'],
                'series_id':collector.window['series_id'],'rep':rep,'method':'MC','anchor':anchor,
                'feasible':True,**mc_by_n[anchor]})

    # Reference draws are independent of all pilots, production streams and MC
    # controls, and cannot feed back into the plan above.
    references=[];reference_seconds=0.
    for block,n in enumerate(config['h2_reference_blocks']):
        m,a=collector.draw(f'independent_reference{block}',[],[],n,'h2_reference',0,block=block)
        references.append(_events(collector,a));reference_seconds+=m['metadata']['generation_seconds']
    ref=stratified_estimate([np.concatenate(references)],[1.])
    save_json(directory/'event_estimates.json',{'events':list(EVENT_NAMES),'rows':rows,
        'reference':jsonable(ref),'reference_N':sum(map(len,references)),
        'reference_block_counts':[a.sum(0).tolist() for a in references],
        'reference_block_N':[len(a) for a in references],'reference_seconds':reference_seconds,
        'reference_caveat':'finite independent N2000; interval uncertainty is not exact model truth',
        'production_plan_sha256':plan_hash})
    return {'h2_repetitions':repetitions,'h2_allocation_plan_sha256':plan_hash,
            'h2_collection_seconds':time.perf_counter()-start,'h2_reference_N':sum(map(len,references))}
