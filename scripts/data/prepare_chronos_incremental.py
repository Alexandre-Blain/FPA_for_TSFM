"""Context-only prospective H1/H2 cohort; no inference or target-value QC."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'code/chronos_fpa'), str(ROOT/'scripts/runs')]
import bootstrap  # noqa: E402,F401
from chronos_pilot_selection import context_features
from ensemble_store import task_id
from run_chronos_local_pilot import digest, load
from run_chronos_microbenchmark import write_json

REVISION = 'eeecad0b82a8c237e212ce6f8d1abecb513e2cec'
DATASETS = {
    'monash_london_smart_meters': {'count':64, 'lag':48, 'frequency':'30min', 'domain':'energy', 'exposure':'in_domain', 'published_H':48},
    'monash_electricity_hourly': {'count':64, 'lag':24, 'frequency':'1h', 'domain':'energy', 'exposure':'in_domain', 'published_H':24},
    'monash_weather': {'count':64, 'lag':1, 'frequency':'1D', 'domain':'nature', 'exposure':'zero_shot', 'published_H':30},
    'monash_pedestrian_counts': {'count':32, 'lag':24, 'frequency':'1h', 'domain':'transport', 'exposure':'in_domain', 'published_H':48},
    'monash_traffic': {'count':96, 'lag':24, 'frequency':'1h', 'domain':'transport', 'exposure':'zero_shot', 'published_H':24},
}
DEEP = ['monash_london_smart_meters', 'monash_electricity_hourly', 'monash_weather', 'monash_traffic']
PILOT = list(DATASETS)


def stable_order(rows, label):
    return sorted(rows, key=lambda r: hashlib.sha256((label+':'+r['series_id']+':2026112601').encode()).hexdigest())


def source_files(run):
    old = load(ROOT/'result/exploratory_benchmark_20261124T095906Z/dataset_provenance.json')
    return ([r for r in old['downloads'] if r['dataset']=='monash_london_smart_meters']
            + load(run/'downloads.json')['downloads'])


def row_batches(sources):
    for s in sources:
        for batch in pq.ParquetFile(ROOT/s['path']).iter_batches(batch_size=1, columns=['id','target','timestamp']):
            yield s, batch.column(0)[0].as_py(), batch.column(1)[0].values, batch.column(2)[0].values


def prepare(run):
    if (run/'cohort.json').exists():
        raise ValueError('Cohort already exists; verify it, never silently reselect')
    sources = source_files(run)
    for s in sources:
        assert digest(ROOT/s['path'])==s['sha256']
    excluded = set()
    for p in (ROOT/'result').glob('*/selection_manifest.json'):
        if p.parent == run:
            continue
        for w in load(p).get('windows', []):
            excluded.add((w['dataset_id'], str(w['series_id'])))
    metadata = {ds:[] for ds in DATASETS}
    for source, series, values, times in row_batches(sources):
        n = len(values); ds = source['dataset']
        if n < 544 or (ds, series) in excluded:
            continue
        ts = times.to_numpy(zero_copy_only=False).astype('datetime64[ns]').astype(np.int64)
        step = int(ts[1]-ts[0])
        metadata[ds].append({'series_id':str(series), 'n':n, 'start':int(ts[0]),
                             'end':int(ts[-1]), 'step':step})
    anchors = {ds:int(sorted(row['end'] for row in rows)[len(rows)//2])-31*rows[0]['step']
               for ds, rows in metadata.items()}
    byid = {(ds,r['series_id']):r for ds,rows in metadata.items() for r in rows}
    candidates = {ds:{s:[] for s in ['train','validation','test','ood_test']} for ds in DATASETS}
    arrays = {}; rejection_counts = {}
    for source, series, values, times in row_batches(sources):
        ds = source['dataset']; series = str(series)
        if (ds,series) not in byid:
            continue
        m = byid[(ds,series)]; y = values.to_numpy(zero_copy_only=False)
        for split, offset in [('train',128),('validation',64),('test',0),('ood_test',0)]:
            if (ds=='monash_weather') != (split=='ood_test'):
                continue
            delta = anchors[ds]-offset*m['step']-m['start']
            if delta % m['step']:
                raise ValueError('Misaligned source timestamps')
            origin = delta//m['step']
            if origin<512 or origin+32>m['n']:
                continue
            context = np.array(y[origin-512:origin], dtype=np.float32, copy=True)
            try:
                features = context_features(context)
                lag = DATASETS[ds]['lag']
                seasonal_scale = float(np.mean(abs(context[lag:].astype(float)-context[:-lag])))
                if seasonal_scale<=1e-12:
                    raise ValueError('zero_context_seasonal_scale')
            except ValueError as e:
                key = ds+':'+str(e); rejection_counts[key] = rejection_counts.get(key,0)+1
                continue
            context_times = times.slice(origin-512,512).to_numpy(zero_copy_only=False).astype('datetime64[ns]').astype(np.int64)
            if not np.all(np.diff(context_times)==m['step']):
                raise ValueError('Selected candidate context has irregular timestamps')
            row = {'dataset_id':ds,'series_id':series,'split':split,'forecast_origin':int(origin),
                'source_length':m['n'],'context_start':int(origin-512),'context_end_exclusive':int(origin),
                'context_sha256':hashlib.sha256(context.tobytes()).hexdigest(),
                'target_start_ns':m['start']+int(origin)*m['step'],
                'target_end_ns':m['start']+int(origin+31)*m['step'],
                'source_file':source['path'],'source_sha256':source['sha256'],
                'source_revision':REVISION,'source_split':'train','seasonal_scale':seasonal_scale,
                'documented_temporal_boundary':m['n']-DATASETS[ds]['published_H'],
                **{k:v for k,v in DATASETS[ds].items() if k!='count'}, **features}
            row['window_id'] = task_id({k:row[k] for k in ['dataset_id','series_id','forecast_origin','context_sha256','source_sha256']})
            candidates[ds][split].append(row)
            # Store futures without inspecting them or using their finiteness
            # as an eligibility criterion. They stay sealed until Gate E.
            arrays[row['window_id']] = (context, np.array(y[origin:origin+32],dtype=np.float32,copy=True))
    used = set(); chosen = []
    def take(ds, split, n, study):
        rows = stable_order([r for r in candidates[ds][split] if (ds,r['series_id']) not in used], study+':'+ds+':'+split)
        if len(rows)<n:
            raise ValueError(f'Context-only availability {ds}/{study}/{split}: need{n}, available{len(rows)}; adjust offline before inference')
        for r in rows[:n]:
            used.add((ds,r['series_id'])); chosen.append({**r,'study':study})
        return chosen[-n:]
    for ds in DEEP:
        rows = take(ds,'ood_test' if ds=='monash_weather' else 'test',9,'H2')
        for i,r in enumerate(rows):
            r['replicated10'] = i<3
            r['rare_reference_candidate'] = i==0
    for ds in PILOT:
        take(ds,'ood_test' if ds=='monash_weather' else 'test',1,'technical_pilot')
    for ds, info in DATASETS.items():
        n=info['count']
        if ds=='monash_weather':
            take(ds,'ood_test',n,'H1')
        else:
            train=int(round(.6*n)); validation=int(round(.2*n)); test=n-train-validation
            take(ds,'test',test,'H1');take(ds,'validation',validation,'H1');take(ds,'train',train,'H1')
        h1=[r for r in chosen if r['study']=='H1' and r['dataset_id']==ds]
        for i,r in enumerate(stable_order(h1,'matched_cost_subset')):
            r['matched_cost_member'] = i%2==0
    # Stable balanced prefix order supports an outcome-blind resource reduction.
    ordered=[]
    groups={ds:stable_order([r for r in chosen if r['study']=='H1' and r['dataset_id']==ds],'reduction') for ds in DATASETS}
    while any(groups.values()):
        for ds in DATASETS:
            if groups[ds]:ordered.append(groups[ds].pop(0))
    for i,r in enumerate(ordered):r['resource_reduction_rank']=i
    chosen=[r for r in chosen if r['study']!='H1']+ordered
    assert len({(r['dataset_id'],r['series_id']) for r in chosen})==len(chosen)
    for ds in DATASETS:
        rows=[r for r in chosen if r['study']=='H1' and r['dataset_id']==ds]
        if ds=='monash_weather':continue
        for a,b in [('train','validation'),('validation','test')]:
            assert max(r['target_end_ns'] for r in rows if r['split']==a)<min(r['target_start_ns'] for r in rows if r['split']==b)
    for name,index in [('contexts.npz',0),('sealed_targets.npz',1)]:
        with (run/name).open('xb') as f:
            np.savez_compressed(f,**{r['window_id']:arrays[r['window_id']][index] for r in chosen})
    write_json(run/'cohort.json',{'windows':chosen,'source_hashes':{s['path']:s['sha256'] for s in sources},
        'source_revision':REVISION,'selection_seed':2026112601,'calendar_test_anchors_ns':anchors,
        'excluded_prior_identities':sorted([list(k) for k in excluded]),'context_only_rejections':rejection_counts,
        'population_by_dataset':{ds:{'metadata_eligible':len(metadata[ds]),'context_eligible_by_split':{k:len(v) for k,v in pools.items()}} for ds,pools in candidates.items()},
        'dependence':'meters/sensors/weather channels may be correlated; unknown station mapping retained, whole weather dataset is held out',
        'chronology':'common within-dataset train/validation/test target periods, strictly separated; one source ID per study/split',
        'sealed_targets_used_for_selection':False})
    import pandas as pd
    pd.DataFrame(chosen).to_csv(run/'cohort_and_splits.csv',index=False)
    print('COHORT',len(chosen),'H1',sum(r['study']=='H1' for r in chosen),'H2',sum(r['study']=='H2' for r in chosen),'pilot',sum(r['study']=='technical_pilot' for r in chosen),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);prepare(p.parse_args().run.resolve())
