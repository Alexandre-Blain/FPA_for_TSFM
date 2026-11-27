"""Freeze resource allocation from completed technical timings, never targets."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'code/chronos_fpa'),str(ROOT/'scripts/runs')]
import bootstrap  # noqa: E402,F401
from run_chronos_incremental import load,save,verify_complete,charged_seconds,verify_sources
from chronos_incremental_features import FPA_FEATURES
from chronos_incremental_h2 import cost_key


def main(run):
    if (run/'allocation.json').exists():raise ValueError('Allocation is immutable once published')
    verify_sources(run,'pilot');cohort=load(run/'cohort.json');pilot=[];costs={}
    by_batch={b:[] for b in (8,16,32)};h1_costs=[];fpa_costs=[];startup=[]
    for w in cohort['windows']:
        if w['study']!='technical_pilot':continue
        marker,snapshot=verify_complete(run,'pilot',w['window_id']);directory=run/'pilot'/w['window_id']
        profile=load(directory/'technical_profile.json')
        if not all(p['logits_close'] and p['q50_close'] and p['same_support'] for x in profile for p in x['parity']):
            raise ValueError('Model-policy parity failed')
        if not all(p['logits_close'] and p['q50_close'] and p['same_support'] for p in marker['parity']):
            raise ValueError('Greedy parity failed')
        for b in by_batch:by_batch[b].append(sum(x['seconds'] for x in profile if x['batch_size']==b))
        base=0.;fpa=0.
        for m,a in snapshot['records']:
            role=m['identity']['role'];meta=m['metadata']
            if role in ('natural','conditional','residual','null'):
                base+=meta['generation_seconds']+meta.get('sga_replay_seconds',0)+meta.get('sga_graph_seconds',0)
            if role in ('conditional','residual','null'):fpa+=meta['generation_seconds']
        h1_costs.append(base+marker['setup_seconds']+2.);fpa_costs.append(fpa)
        for row in load(directory/'h2_timing.json'):
            costs.setdefault(cost_key(row['group']),[]).append(row['seconds']/row['N'])
        receipts=[load(p) for p in (run/'attempts').glob('*.json')]
        receipt=next(r for r in receipts if r.get('exit_code')==0 and r['windows']==[w['window_id']])
        startup.append(max(0.,receipt['elapsed_seconds']-marker['window_seconds']))
        pilot.append({'window_id':w['window_id'],'dataset_id':w['dataset_id'],
            'paths':marker['paths'],'ensembles':marker['ensembles'],
            'window_seconds':marker['window_seconds'],'subprocess_seconds':receipt['elapsed_seconds']})
    if len(pilot)!=5:raise ValueError('Five completed representative technical windows required')
    batch=min(by_batch,key=lambda b:statistics.median(by_batch[b]))
    natural_cost=statistics.median([x['seconds']/64 for w in cohort['windows'] if w['study']=='technical_pilot'
        for x in load(run/'pilot'/w['window_id']/'technical_profile.json')
        if x['batch_size']==batch and x['kind']=='natural'])
    cost_model={k:statistics.median(v) for k,v in costs.items()};cost_model['natural']=natural_cost
    extra=max(batch,int(round(statistics.median(fpa_costs)/natural_cost/batch))*batch)
    extra=min(extra,1600)
    h1=[w for w in cohort['windows'] if w['study']=='H1'];h2=[w for w in cohort['windows'] if w['study']=='H2']
    spent=charged_seconds(run);start=statistics.median(startup)
    h1_est=len(h1)*statistics.median(h1_costs)+len(h1)/8*start+sum(w['matched_cost_member'] for w in h1)*extra*natural_cost
    estimates=[]
    # Runtime safety margin accounts for small tail batches and heterogeneous
    # prefix costs. Reductions here depend only on timing, never event outcomes.
    for repetitions in range(10,0,-1):
        rep_total=sum(repetitions if w['replicated10'] else 1 for w in h2)
        h2_est=rep_total*(6*480*natural_cost+35.)+len(h2)*(2000*natural_cost+start+20.)
        total=spent+1.35*(h1_est+h2_est)
        estimates.append({'repetitions':repetitions,'H1_seconds':h1_est,'H2_seconds':h2_est,'conservative_total_seconds':total})
        if total<=.94*57600:break
    if total>57600:raise RuntimeError('Even minimal full-cohort plan does not fit; revise by timing only')
    allocation={'H1_target':320,'H2_target':36,'h1_windows':[w['window_id'] for w in h1],
        'h2_windows':[w['window_id'] for w in h2],'H1_matched_extra_N':extra,
        'H1_matched_windows':[w['window_id'] for w in h1 if w['matched_cost_member']],
        'H2_replicated_windows':[w['window_id'] for w in h2 if w['replicated10']],
        'H2_repetitions':repetitions,'H2_reference_N':2000,'H2_extra_rare_reference_N':0,
        'expected':estimates[-1],'cost_based_repetition_candidates':estimates,
        'balanced_reduction_order': [w['window_id'] for w in sorted(h1,key=lambda w:w['resource_reduction_rank'])],
        'reduction_policy':'No outcome-based selection. If hard safeguard stops execution, retain all durable cells, report coherent completed subset in frozen balanced rank order; no confirmatory claim below minima.',
        'targets_accessed':False,'batch_size':batch,'model_seconds_already_charged':spent}
    gate={'status':'passed','five_windows':pilot,'batch_median_seconds':{str(b):statistics.median(v) for b,v in by_batch.items()},
        'selected_batch':batch,'cost_model':cost_model,'median_H1_base_seconds':statistics.median(h1_costs),
        'median_FPA_incremental_generation_seconds':statistics.median(fpa_costs),'median_subprocess_startup_seconds':start,
        'policy_parity':'all cached vs full replay checks passed; full conditional residual sampled',
        'resume':'second supervisor invocation validated complete markers and launched zero model processes',
        'v1_interruption':'Windows heartbeat share lock, 73.8602037 seconds charged; original partial sources/raw archived; v2 bounded publication retry tested',
        'selection_adjustment':'Before any model call, context availability required pedestrian32/traffic96 instead of pedestrian48/traffic80; total320 unchanged',
        'allocation_uses':'technical timings, context/source availability only; no forecasts errors, FPA features, events or reference results'}
    feature_names=list(load(run/'pilot'/pilot[0]['window_id']/'features.json'))
    methodology={'version':'2026-11-26-v1','source_HEAD':'a5b6ef6743832f09bfa096078104b727dc84f373',
        'estimand':'Chronos-T5-mini effective valid-token q50, T1, topk50 including ties, topp1; not p_sel',
        'selection':'320 distinct H1 IDs +36 disjoint H2 IDs +5 disjoint technical IDs, context-only common-calendar chronological partitions; future values sealed',
        'pretraining_exposure':'in_domain designation is not proof of untouched TSFM targets; report potentially pretraining-exposed target coordinates using each original published source cutoff. Weather and traffic are designated zero-shot.',
        'H1':{'natural':[20,20,20],'conditional_per_selected_and_residual':[20,20],'null_N':20,
            'positions':[0,4,9],'selected_cap_including_greedy':5,'distance_coordinates':'b+1..b+22 inclusive, forced coordinate excluded',
            'feature_names':feature_names,'FPA_features':list(FPA_FEATURES),
            'F2':'sum_b prefix_mass_b sum_groups q_group distance(group,greedy) / sum_b prefix_mass_b; conditional sensitivity, not natural event probability',
            'F4':'coarse group variance minus finite MC bias; full between-token and within-token components via independent-block matching with residual inverse-probability correction; no clipping negative estimates',
            'F3_noise_controls':'candidate_count/local support/numeric jumps in M0; independent same-token W1 in FPA feature family; fixed N40 for every candidate',
            'SGA':'pinned author algorithm 03d8133912c4e5c813cae084ca5f5358d7e5a206; three independent K20; top20-renormalized replay entropies; fixed original conventions; H32 q50 adaptation',
            'point_forecast':'N60 natural mean, identical for ALL methods including extra-natural controls; median/greedy secondary only',
            'learning':'Separate log1p(MASE) and log1p(MAE/IQR) ridge models; alpha grid .1,1,10,100; unpenalized intercept; training-only mean/populationSD; validation-only log-MSE; no refit on validation; raw log prediction for ranking',
            'models':{'M0':'all conventional feature_names except sga and FPA_features, plus train-defined dataset/frequency/domain/exposure metadata',
                'M1':'M0+sga','M2':'M0+14 fixed FPA features','M3':'M1+14 fixed FPA features'},
            'scaling_controls':'individually seasonalscale, contextIQR, seasonal/IQR, inverse ratio; same-supervision scale+dataset/frequency metadata baseline',
            'matched_cost':'160 prospectively selected IDs; extra natural uncertainty replaces original natural summaries for M1_extra_MC; original SGA and N60 point forecast fixed; retrain/calibrate all compared models on SAME matched subset partitions; actual cost ratios reported',
            'metrics':'MASE primary lag48 London,24 electricity/pedestrian/traffic,1 dailyweather; MAE/IQR separate supervised target; raw MAE within datasets; expected-tie trapezoid AURC/NEAURC; Spearman; risk at ceil(.25,.5,.75,1)*N; log-MSE and nonnegative expm1 squared error',
            'primary':'M3-M1 NEAURC on within-test and separately entire weather OOD; negative delta favors FPA',
            'secondary':'M2-M0; matched-cost M3 vs M1_extra_MC; scale controls; median/greedy point forecast descriptive',
            'uncertainty':'999 hierarchical dataset/source bootstrap; fixed fitted models; single OOD dataset source-only CI, physical station/channel clustering unknown; no horizon/path pseudoreplication',
            'formal_tests':'one-sided paired block method-swap randomization for AURC: entire dataset blocks within-test; source-ID swaps in weather conditional on ID independence, unresolved physical-station dependence; Holm across these two and H2 primary; report tiny dataset count/coarse p-values',
            'missing_targets':'if any held-out future nonfinite, preserve features/prediction and declare target unavailable without reselection; never filter by error magnitude; no test-based imputation'},
        'H2':{'events':{'E1':'min(Y[8:32]) <= lastcontext-IQR','E2':'max(Y[8:32]) >= lastcontext+IQR',
                'E3':'mean(Y[24:32]) <= lastcontext-.5IQR','E4':'sign3((Y31-last)/IQR) differs from frozen greedy; sign3 neutral inclusive[-.05,.05]'},
            'partitions':'first token greedy+two probable alternatives+full residual; first deviation b0..4 top alternative+all other nongreedy tokens per prefix+all-five-greedy',
            'pilot':'N4 independent per first-deviation stratum, all four events; Jeffreys-smoothed mean p(1-p) for allocation; excluded from production estimates',
            'costs':'global technical per-path cost by singleton/mixed/prefix and position; frozen before outcomes; full actual local pilot cost charged at every Neyman or IS estimate, even across repetitions; fixed allocations do not need local outcome pilot',
            'allocation':'nested counts at N60/120/240/480-equivalent technical time; all positive strata >=2 or whole combination infeasible; uniform/proportional/estimated Neyman variance per cost',
            'IS':'choose stratum iid a=.5w+.5 normalized[w sqrt(v/c)], all a>=.5w; exact likelihood w_j/a_j; unnormalized estimator may exceed1; no approximate full-path likelihoods',
            'intervals':'pointwise bounded Hoeffding conditional on independent pilot; sample-variance estimates separately; zero events never imply exact zero probability',
            'matched_MC':'ordinary natural pool per independent replicate, shared across method comparisons/budget prefixes; N determined before MC draws from independent stratum actual generation time / frozen technical natural path cost, rounded to batch, cap4000; report actual time ratio and mark .8..1.25 matching; no selection using MC outcomes or MC runtime',
            'reference':'two independent N1000 blocks/window, never used in allocation; report binomial uncertainty and block discrepancies, zeros with positive upper bound; no extra N10000',
            'primary':'four-event mean MSE to independent reference at anchor480, equal weight per original source, repetitions averaged within original; Neyman first-deviation vs matched ordinary MC. Report paired absolute MSE difference, dataset-block exact sign randomization, uncertainty by dataset/source.',
            'cost_claim_gate':'report ALL source pairs. If less than80% of primary pairs have actual MC/method time ratio in [.8,1.25], do not claim exact equal-cost superiority; show full measured cost/error tradeoff instead.',
            'reference_error':'reference is approximate. Report MSE vs reference, reference-variance corrected MSE (can be negative), and estimator variance on truly replicated windows. Interval agreement with reference is not true probability coverage.',
            'prevalence_regimes':'reference<.05, .05..25, .25..75, >=.75 descriptive reporting only; no policy selection',
            'TaskB':'actual-future events and Brier/reliability exploratory36 sources; clip IS probability ONLY for TaskB with count disclosed; no clipping TaskA estimate',
            'dependence':'H2 disjoint source IDs from H1, regional/weather channels may correlate; budgets share nested draws, methods share matched MC pool, reference shared per source; independent repetitions have distinct RNG streams'},
        'safeguards':{'max_model_subprocess_seconds':57600,'max_new_bytes':21474836480,
            'source_freeze':'code archives and SHA256; raw immutable ensemble manifests; no historical outputs changed',
            'halt':'parity/integrity failure, freeRAM<128MiB sustained, freeDisk<1GiB, artifact ceiling or cumulative model time; preserve partial cells',
            'seeds':'root2026112609 + SHA256 full scoped raw task identity; independent IS choice stream; source selection2026112601',
            'scientific_stop':'analysis, integrity checks, handout; no automatic new campaign'},
        'budget':allocation['expected']}
    save(run/'gate_B.json',gate);save(run/'methodology.json',methodology);save(run/'allocation.json',allocation)
    path=ROOT/'configs/chronos_incremental/campaign_v1.json';cfg=load(path)
    cfg.update(stage='frozen primary protocol; full collection authorized',batch_size=batch,
        h1_matched_extra_N=extra,h2_cost_model=cost_model,h2_final_repetitions=repetitions,
        h2_matched_natural_cap=4000,final_allocation='allocation.json and methodology.json under campaign run')
    save(path,cfg)
    print(json.dumps({'batch':batch,'extra_N':extra,'repetitions':repetitions,'estimated':allocation['expected']},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True,type=Path)
    main(parser.parse_args().run.resolve())
