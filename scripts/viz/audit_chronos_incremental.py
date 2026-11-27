"""Read-only audit of campaign raw evidence, math, costs and preservation.

Does not read sealed target values, load model weights, or launch inference.
Reconstructs event estimates from raw independent paths, including IS labels.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'code/chronos_fpa'),str(ROOT/'scripts/runs')]
import bootstrap  # noqa: E402,F401
import numpy as np
from ensemble_store import read_snapshot,task_id
from chronos_incremental import (future_events,first_token_partition,first_deviation_partition,
    validate_partition,stratified_estimate,importance_estimate)
from chronos_incremental_features import h1_features
from run_chronos_incremental import load,save,digest,verify_complete,verify_sources,charged_seconds,new_bytes


def stream_digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while block:=f.read(8*2**20):h.update(block)
    return h.hexdigest()


def stream_seed(root,label):
    value=hashlib.sha256(f'{root}:{label}'.encode()).hexdigest()
    return int(value[:16],16),value


def literal_events(a,context,greedy):
    """Separate literal oracle for the four fixed absolute H32 events."""
    a=np.asarray(a,float);last=float(context[-1]);iqr=float(np.percentile(context,75)-np.percentile(context,25))
    z=(a-last)/iqr;g=(float(greedy[31])-last)/iqr
    def direction(v):return (v>.05).astype(int)-(v<-.05).astype(int)
    gd=int(g>.05)-int(g<-.05)
    return np.array([np.any(z[:,8:32]<=-1,axis=1),np.any(z[:,8:32]>=1,axis=1),
        np.mean(z[:,24:32],axis=1)<=-.5,direction(z[:,31])!=gd]).T


def assert_estimate(row,estimate):
    for key in ('probability','variance','lo','hi'):
        np.testing.assert_allclose(row[key],estimate[key],atol=2e-12,rtol=2e-12)


def audit_h1(run,w,marker,snapshot,config):
    directory=run/'H1'/w['window_id'];forks=load(directory/'forks.json');records=snapshot['records']
    expected=[]
    for block in range(3):expected.append(('natural',0,None,block,20))
    for f in [x for x in forks if x['b'] in (0,4,9)]:
        for t in f['selected_tokens']:
            for block in range(2):expected.append(('conditional',f['b'],t,block,20))
        if f['residual_mass']>0:
            for block in range(2):expected.append(('residual',f['b'],None,block,20))
        expected.append(('null',f['b'],f['greedy'],0,20))
    if w['matched_cost_member']:expected.append(('matched_natural',0,None,0,config['h1_matched_extra_N']))
    actual=[tuple(m['identity'][k] for k in ('role','position','token','block','sample_count')) for m,a in records]
    if sorted(expected,key=str)!=sorted(actual,key=str):raise ValueError('H1 protocol roles/counts mismatch')
    first=records[0][1];context=first['context'];greedy=first['greedy_values'];greedy_tokens=first['greedy_tokens']
    for m,a in records:
        role=m['identity']['role'];b=m['identity']['position'];identity=m['identity']
        if role in ('conditional','residual','null'):
            np.testing.assert_array_equal(identity['prefix'],greedy_tokens[:b])
            f=forks[b]
            support=f['residual_support'] if role=='residual' else [identity['token']]
            if support!=identity['first_token_support']:raise ValueError('Selected/residual law changed')
        if role=='natural' and a['top20_entropy'].shape!=(20,32):raise ValueError('Missing full SGA entropy replay')
    rebuilt=h1_features(context,greedy,forks,records,w['lag']);stored=load(directory/'features.json')
    if set(rebuilt)!=set(stored):raise ValueError('Feature catalogue changed')
    for key in rebuilt:np.testing.assert_allclose(rebuilt[key],stored[key],atol=1e-10,rtol=1e-10)


def audit_h2(run,w,marker,snapshot,config,frequency_rows=None):
    # Importing the allocation helper imports Torch utilities but no weights.
    from chronos_incremental_h2 import allocation_plan
    directory=run/'H2'/w['window_id'];plan=load(directory/'allocation_plan.json');d=load(directory/'event_estimates.json')
    forks=load(directory/'forks.json')
    if plan['partitions']!={'first_token':first_token_partition(forks),'first_deviation':first_deviation_partition(forks)}:
        raise ValueError('Allocation partition differs from actual greedy-prefix q50 laws')
    unhashed={k:v for k,v in plan.items() if k!='plan_sha256'}
    expected_hash=hashlib.sha256(json.dumps(unhashed,sort_keys=True,allow_nan=False).encode()).hexdigest()
    if expected_hash!=plan['plan_sha256'] or expected_hash!=d['production_plan_sha256']:raise ValueError('H2 allocation not immutable')
    records=snapshot['records'];by_label={m['identity']['label']:(m,a) for m,a in records}
    if len(by_label)!=len(records):raise ValueError('Duplicate H2 stream label')
    arrays=records[0][1];context=arrays['context'];greedy=arrays['greedy_values']
    events={label:literal_events(a['values'],context,greedy) for label,(m,a) in by_label.items()}
    for label,(m,a) in by_label.items():np.testing.assert_array_equal(events[label],future_events(a['values'],context,greedy))
    pilot=[];pilot_seconds=0.
    for g in plan['partitions']['first_deviation']:
        m,a=by_label['allocation_pilot_'+g['name']]
        if len(a['values'])!=4:raise ValueError('Allocation pilot count changed')
        pilot.append(events[m['identity']['label']]);pilot_seconds+=m['metadata']['generation_seconds']
    rebuilt=allocation_plan(plan['partitions'],config['h2_cost_model'],pilot,pilot_seconds,
        config['h2_budget_anchors'],config['h2_minimum_per_stratum'])
    if rebuilt['plans']!=plan['plans']:raise ValueError('Final counts do not follow independent pilot')
    if rebuilt['importance_proposal']!=plan['importance_proposal']:raise ValueError('IS proposal changed')
    rows=d['rows'];declared=plan['plans'];new_counts=0
    for row in rows:
        method=row['method'];rep=row['rep'];anchor=row['anchor']
        if not row['feasible']:continue
        if method in ('MC','matched_MC'):
            chosen=[];seconds=0.;n=row['N']
            for label,(m,a) in by_label.items():
                prefix=f'MC_rep{rep}_throughN'
                if label.startswith(prefix) and int(label[len(prefix):])<=n:
                    chosen.append((int(label[len(prefix):]),events[label]));seconds+=m['metadata']['generation_seconds']
            all_events=np.concatenate([e for _,e in sorted(chosen,key=lambda t:t[0])])
            if len(all_events)!=n:raise ValueError('MC pool is not a complete measured boundary')
            assert_estimate(row,stratified_estimate([all_events],[1.]))
            np.testing.assert_allclose(seconds,row['production_seconds'],atol=1e-9,rtol=0)
            continue
        spec=next(p for p in declared if p['method']==method and p['anchor']==anchor)
        if not spec['feasible']:raise ValueError('Infeasible allocation sampled')
        groups=plan['partitions'][spec['partition']];samples=[];seconds=0.
        for g in groups:
            pieces=[]
            for label,(m,a) in by_label.items():
                prefix=f'{method}_rep{rep}_anchor'
                if not label.startswith(prefix) or not label.endswith('_'+g['name']):continue
                sampled_anchor=int(label[len(prefix):].split('_')[0])
                if sampled_anchor<=anchor:
                    pieces.append((sampled_anchor,events[label]));seconds+=m['metadata']['generation_seconds']
                    if m['identity']['prefix']!=g['prefix'] or m['identity']['first_token_support']!=g['support']:
                        raise ValueError('H2 stratum not conditioned on declared exhaustive group')
            samples.append(np.concatenate([a for _,a in sorted(pieces,key=lambda t:t[0])]) if pieces else np.empty((0,4),bool))
        counts=np.array([len(a) for a in samples]);weights=np.array([g['weight'] for g in groups])
        np.testing.assert_array_equal(counts,row['counts'])
        if method=='stratum_mixture_IS':
            maximum=max(p['N'] for p in declared if p['method']==method and p['feasible'])
            choice_seed,_=stream_seed(config['root_seed'],w['window_id']+f':H2:IS_choices:{rep}:{expected_hash}')
            choices=np.random.default_rng(choice_seed).choice(len(groups),maximum,p=plan['importance_proposal'])[:row['N']]
            np.testing.assert_array_equal(counts,np.bincount(choices,minlength=len(groups)))
            assert_estimate(row,importance_estimate(np.repeat(np.arange(len(groups)),counts),
                np.concatenate(samples),weights,spec['proposal']))
        else:
            np.testing.assert_array_equal(counts,spec['counts'])
            assert_estimate(row,stratified_estimate(samples,weights))
            # Independent literal estimator and conditional sample variance.
            literal=sum(weight*e.mean(0) for weight,e in zip(weights,samples))
            variance=sum(weight**2*e.var(0,ddof=1)/len(e) for weight,e in zip(weights,samples))
            np.testing.assert_allclose(row['probability'],literal,atol=1e-12,rtol=0)
            np.testing.assert_allclose(row['variance'],variance,atol=1e-12,rtol=0)
        np.testing.assert_allclose(seconds,row['production_seconds'],atol=1e-9,rtol=0)
        np.testing.assert_allclose(seconds+spec['pilot_seconds_charged'],row['variable_seconds'],atol=1e-9,rtol=0)
        match=next(r for r in rows if r['rep']==rep and r['anchor']==anchor and r['method']=='matched_MC' and r['matched_to']==method)
        n=int(np.ceil(row['variable_seconds']/config['h2_cost_model']['natural']/config['batch_size']))*config['batch_size']
        if match['N']!=min(config['h2_matched_natural_cap'],max(2,n)):raise ValueError('Matched MC count used an undeclared rule')
        new_counts+=1
    references=[events[f'independent_reference{b}'] for b in range(2)]
    if [len(e) for e in references]!=[1000,1000]:raise ValueError('Reference sample count changed')
    assert_estimate(d['reference'],stratified_estimate([np.concatenate(references)],[1.]))
    np.testing.assert_array_equal([e.sum(0) for e in references],d['reference_block_counts'])
    natural_tokens=np.concatenate([by_label[f'independent_reference{b}'][1]['tokens'] for b in range(2)])
    for name,groups in plan['partitions'].items():
        membership=[]
        for group in groups:
            prefix=group['prefix'];support=group['support']
            match=np.all(natural_tokens[:,:len(prefix)]==np.tile(prefix,(len(natural_tokens),1)),axis=1)
            if support:match &= np.isin(natural_tokens[:,len(prefix)],support)
            membership.append(match)
            if frequency_rows is not None:frequency_rows.append({'window_id':w['window_id'],'dataset_id':w['dataset_id'],
                'partition':name,'stratum':group['name'],'q50_weight':group['weight'],
                'independent_natural_count':int(match.sum()),'N':len(natural_tokens),
                'empirical_natural_frequency':float(match.mean()),
                'interpretation':'finite independent natural-frequency sanity check; no forced frequencies used as weights'})
        np.testing.assert_array_equal(np.sum(membership,axis=0),np.ones(len(natural_tokens),int))
    return new_counts


def archives(run):
    versions=[('pilot_freeze.json','source_at_pilot',{}),
        ('pilot_freeze_v1_interrupted.json','source_at_pilot_v1_interrupted',
            {'pilot_config.json':'pilot_config_v1_interrupted.json','gate_A_tests.json':'gate_A_v1_tests.json'}),
        ('frozen_v1_interrupted.json','source_at_collection_v1_interrupted',
            {'frozen_config.json':'frozen_config_v1_interrupted.json','gate_C_tests.json':'gate_C_v1_tests.json'}),
        ('frozen.json','source_at_collection',{})]
    counts={}
    for marker,folder,aliases in versions:
        if not (run/marker).exists():continue
        doc=load(run/marker)
        for name,h in doc['source_hashes'].items():
            if digest(run/folder/name)!=h:raise ValueError('Historical source archive changed: '+folder+'/'+name)
        for name,h in doc['files'].items():
            if digest(run/aliases.get(name,name))!=h:raise ValueError('Historical frozen input changed: '+marker+'/'+name)
        counts[marker]=len(doc['source_hashes'])
    return counts


def preservation(run):
    before=load(run/'preservation_before.json');checked=0;failures=[]
    for name,info in before['files'].items():
        path=ROOT/name
        if not path.exists():failures.append({'path':name,'reason':'missing'});continue
        stat=path.stat()
        if stat.st_size!=info['bytes'] or stat.st_mtime_ns!=info['mtime_ns'] or stream_digest(path)!=info['sha256']:
            failures.append({'path':name,'reason':'size,mtime or SHA256 changed'})
        checked+=1
        if checked%2000==0:print('PRESERVATION',checked,flush=True)
    # Inventory metadata keys are read explicitly; no Git writes are performed.
    for key in ('index_sha256','gitignore_sha256'):
        if key in before:
            path=ROOT/('.git/index' if key=='index_sha256' else '.gitignore')
            if stream_digest(path)!=before[key]:failures.append({'path':str(path),'reason':key+' changed'})
    result={'checked_preexisting_files':checked,'failures':failures,'status':'passed' if not failures else 'failed'}
    save(run/'preservation_after.json',result)
    if failures:raise ValueError('Historical artifact preservation failed')
    return result


def resource_compliance(run, config):
    """Keep operational violations visible without suppressing the raw audit."""
    seconds = charged_seconds(run)
    size = new_bytes(run)
    time_limit = config['maximum_model_seconds']
    size_limit = config['maximum_new_bytes']
    return {'passed': seconds <= time_limit and size <= size_limit,
            'model_seconds': seconds, 'maximum_model_seconds': time_limit,
            'model_seconds_over_limit': max(0., seconds-time_limit),
            'new_bytes': size, 'maximum_new_bytes': size_limit,
            'new_bytes_over_limit': max(0, size-size_limit)}


def main(run,check_preservation=False,allow_partial=False):
    start=time.perf_counter();config=load(run/'frozen_config.json');verify_sources(run,'H1');archive_counts=archives(run)
    cohort=load(run/'cohort.json');windows=cohort['windows'];ids=[(w['dataset_id'],w['series_id']) for w in windows]
    if len(ids)!=len(set(ids)):raise ValueError('Original identity leakage across studies/splits')
    for dataset in sorted({w['dataset_id'] for w in windows}):
        sets={split:[w for w in windows if w['study']=='H1' and w['dataset_id']==dataset and w['split']==split]
            for split in ('train','validation','test')}
        for left,right in [('train','validation'),('validation','test')]:
            if sets[left] and sets[right] and max(w['target_end_ns'] for w in sets[left])>=min(w['target_start_ns'] for w in sets[right]):
                raise ValueError('Target calendar intervals overlap development partitions')
    counts={};streams=set();seeds=set();rows=[];recomputed=0;max_mass_error=0.;frequency_rows=[]
    for phase in ('pilot','H1','H2'):
        selected=[w for w in windows if w['study']=={'pilot':'technical_pilot','H1':'H1','H2':'H2'}[phase]]
        planned_count=len(selected)
        if allow_partial and phase!='pilot':selected=[w for w in selected if (run/phase/w['window_id']/'complete.json').exists()]
        phase_paths=0;phase_ensembles=0
        for wi,w in enumerate(selected):
            marker,snapshot=verify_complete(run,phase,w['window_id']);forks=load(run/phase/w['window_id']/'forks.json')
            prefix_mass=1.
            for f in forks:
                q={int(t):p for t,p in f['probabilities'].items()};selected_tokens=set(f['selected_tokens']);residual=set(f['residual_support'])
                if selected_tokens&residual or selected_tokens|residual!=set(q) or len(selected_tokens)>5:raise ValueError('Selected/residual support not exhaustive')
                np.testing.assert_allclose(sum(q.values()),1.,atol=1e-12,rtol=0)
                np.testing.assert_allclose(sum(q[t] for t in residual),f['residual_mass'],atol=1e-12,rtol=0)
                np.testing.assert_allclose(f['greedy_prefix_mass'],prefix_mass,atol=1e-14,rtol=1e-12);prefix_mass*=q[f['greedy']]
                max_mass_error=max(max_mass_error,abs(f.get('raw_float32_q50_mass',1)-1))
            validate_partition(first_token_partition(forks));validate_partition(first_deviation_partition(forks))
            for m,a in snapshot['records']:
                identity=m['identity'];rng=m['metadata']['rng'];expected_seed,expected_stream=stream_seed(config['root_seed'],task_id(identity))
                if rng['seed']!=expected_seed or rng['stream_id']!=expected_stream:raise ValueError('RNG provenance mismatch')
                if expected_seed in seeds or expected_stream in streams:raise ValueError('Repeated RNG stream across final experiment objects')
                seeds.add(expected_seed);streams.add(expected_stream)
                if any(identity[k]!=w[k] for k in ('dataset_id','series_id','window_id','forecast_origin','context_sha256')):raise ValueError('Foreign source/window scope')
                if identity['model_revision']!=config['model_revision'] or identity['phase']!=phase or identity['policy']!='q50_valid_mask_T1_topk50_ties_topp1':
                    raise ValueError('Model/policy/phase scope mismatch')
                if a['tokens'].shape!=(identity['sample_count'],32) or a['values'].shape!=a['tokens'].shape or not np.isfinite(a['values']).all():raise ValueError('Incomplete or nonfinite path')
                if (a['tokens']<2).any():raise ValueError('Special token sampled')
                prefix=identity['prefix'];support=identity['first_token_support']
                np.testing.assert_array_equal(a['tokens'][:,:len(prefix)],np.tile(prefix,(len(a['tokens']),1)))
                if support and not np.isin(a['tokens'][:,len(prefix)],support).all():raise ValueError('Conditional support violated')
                if hashlib.sha256(a['context'].tobytes()).hexdigest()!=w['context_sha256']:raise ValueError('Raw context mismatch')
            if phase=='H1':audit_h1(run,w,marker,snapshot,config)
            if phase=='H2':recomputed+=audit_h2(run,w,marker,snapshot,config,frequency_rows)
            phase_paths+=marker['paths'];phase_ensembles+=marker['ensembles']
            rows.append({'phase':phase,'dataset_id':w['dataset_id'],'series_id':w['series_id'],
                'window_id':w['window_id'],'paths':marker['paths'],'ensembles':marker['ensembles'],
                'source_id':marker['scope']['source_freeze_id'],'complete_sha256':digest(run/phase/w['window_id']/'complete.json')})
            if wi%25==0:print('AUDIT',phase,wi+1,'/',len(selected),flush=True)
        counts[phase]={'planned_windows':planned_count,'windows':len(selected),'paths':phase_paths,'ensembles':phase_ensembles}
    # Partial first pilot remains useful technical evidence, never primary N.
    partial=[]
    for directory in (run/'pilot_v1_interrupted').glob('*/ensembles'):
        snapshot=read_snapshot(directory);partial.append({'directory':str(directory.relative_to(run)),
            'ensembles':len(snapshot['records']),'paths':sum(len(a['tokens']) for m,a in snapshot['records'])})
    resources=resource_compliance(run,config)
    for name,info in load(run/'model_cache.json')['files'].items():
        if stream_digest(Path(load(run/'model_cache.json')['snapshot'])/name)!=info['sha256']:raise ValueError('Model cache changed')
    preserved=preservation(run) if check_preservation else {'status':'not requested'}
    summary={'status':'passed' if resources['passed'] else 'raw integrity passed; resource ceiling FAILED',
        'mathematical_and_raw_integrity':'passed','resource_compliance':resources,
        'utc':datetime.now(timezone.utc).isoformat(),'phase_counts':counts,
        'source_archives_verified':archive_counts,'independent_torch_streams':len(streams),
        'H2_recomputed_stratified_or_IS_cells':recomputed,'maximum_raw_float32_mass_error':max_mass_error,
        'historical_partial_pilot':partial,'model_subprocess_seconds':charged_seconds(run),
        'new_data_artifacts_bytes':new_bytes(run),'preservation':preserved,
        'sealed_target_values_read':False,'seconds':time.perf_counter()-start,'windows':rows,
        'limits':'Mathematical and raw integrity checks do not prove physical independence, TSFM calibration, or scientific benefit'}
    save(run/'natural_partition_frequency_audit.json',frequency_rows)
    save(run/'integrity_audit.json',summary);print('RAW AUDIT PASSED',json.dumps(counts),flush=True)
    if not resources['passed']:
        raise ValueError('Resource ceiling exceeded; raw/preservation audit retained in integrity_audit.json; violation is NOT waived')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True,type=Path);p.add_argument('--preservation',action='store_true')
    p.add_argument('--partial',action='store_true',help='Validate completed cells after a resource stop, without inflating counts')
    a=p.parse_args();main(a.run.resolve(),a.preservation,a.partial)
