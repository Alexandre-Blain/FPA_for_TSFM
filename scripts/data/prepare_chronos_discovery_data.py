"""Download only the authorized London/Australia pair, pin and select contexts.

No model loading. Full source files are retained; the selector never reads
future values when computing eligibility, strata or selection scores.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code/chronos_fpa'))
import bootstrap  # noqa: E402,F401
from chronos_pilot_selection import context_features,rank_features
from ensemble_store import task_id
import numpy as np

DATASETS={'monash_london_smart_meters':{'status':'in_domain','holdout':48,'frequency':'30min','seasonality':48,'aggregation':'household'},
          'monash_australian_electricity':{'status':'zero_shot','holdout':48,'frequency':'30min','seasonality':48,'aggregation':'state demand'}}


def prepare(out):
    import requests
    import pyarrow.parquet as pq
    started=time.perf_counter();out=Path(out);directory=ROOT/'data/raw/chronos_discovery_20261124';directory.mkdir(parents=True,exist_ok=True)
    metadata=json.loads((out/'hf_dataset_metadata.json').read_text());revision=metadata['sha'];downloads=[];populations={};arrays={};rejections=[]
    for ds,info in DATASETS.items():
        rows=[];files=sorted(x['rfilename'] for x in metadata['siblings'] if x['rfilename'].startswith(ds+'/') and x['rfilename'].endswith('.parquet'))
        for name in files:
            dest=directory/name;dest.parent.mkdir(parents=True,exist_ok=True)
            url=f'https://huggingface.co/datasets/autogluon/chronos_datasets/resolve/{revision}/{name}'
            if not dest.exists():
                part=dest.with_suffix('.part');h=hashlib.sha256();size=0
                with requests.get(url,stream=True,timeout=(30,60)) as r:
                    r.raise_for_status()
                    with part.open('wb') as f:
                        for chunk in r.iter_content(1024*1024):f.write(chunk);h.update(chunk);size+=len(chunk)
                        f.flush();os.fsync(f.fileno())
                os.replace(part,dest);print('downloaded',name,size,flush=True)
            h=hashlib.sha256()
            with dest.open('rb') as f:
                for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
            source_sha=h.hexdigest();downloads.append({'dataset':ds,'url':url,'path':dest.relative_to(ROOT).as_posix(),'sha256':source_sha,'bytes':dest.stat().st_size})
            parquet=pq.ParquetFile(dest)
            for batch in parquet.iter_batches(batch_size=1,columns=['id','target','timestamp']):
                row=batch.to_pylist()[0];series=str(row['id']);target=row['target'];length=len(target)
                offsets=[80,64,32] if info['status']=='in_domain' else [64]
                for offset in offsets:
                    origin=length-offset
                    if origin<512:continue
                    c=np.asarray(target[origin-512:origin],dtype=np.float32)
                    try:features=context_features(c)
                    except ValueError as e:rejections.append({'dataset':ds,'series':series,'offset':offset,'reason':str(e)});continue
                    item={'dataset_id':ds,'series_id':series,'forecast_origin':origin,'source_length':length,
                          'context_start':origin-512,'context_end_exclusive':origin,'context_sha256':hashlib.sha256(c.tobytes()).hexdigest(),
                          'source_repo':'autogluon/chronos_datasets','source_split':'train','source_revision':revision,
                          'source_file':dest.relative_to(ROOT).as_posix(),'source_sha256':source_sha,'offset_from_end':offset,
                          'documented_pretraining_status':info['status'],'documented_temporal_boundary':length-info['holdout'],
                          'training_overlap':'potential exposure only; no record of actually sampled training segments',
                          'prior_FPA_exposure':'new dataset identity in this workspace',
                          'start_timestamp':str(row['timestamp'][0]),'origin_timestamp':str(row['timestamp'][origin]),**info,**features}
                    rows.append(item)
                    # Futures are stored for later evaluation but never inspected by the selector.
                    arrays[(ds,series,offset)]=(c,np.asarray(target[origin:origin+64],dtype=np.float32))
        populations[ds]=rows
    selected=[];contexts={};targets={};rng=np.random.default_rng(2026112407)
    for ds,info in DATASETS.items():
        used=set();first=None
        for slot,(offset,label) in enumerate(zip([80,64,32] if info['status']=='in_domain' else [64]*3,['representative_potential','diversity_mixed','representative_heldout'])):
            eligible=sorted([r for r in populations[ds] if r['offset_from_end']==offset and r['series_id'] not in used],key=lambda r:r['series_id'])
            if not eligible:raise ValueError(f'No eligible distinct series for {ds}/{slot}; do not replace silently')
            if slot==1:
                ranked=rank_features([first]+eligible);radius=((ranked-np.median(ranked,axis=0))**2).mean(1)
                distance=((ranked[1:]-ranked[0])**2).mean(1);allowed=[i for i in range(len(eligible)) if radius[i+1]<=np.quantile(radius,.9)]
                chosen=min(allowed,key=lambda i:(-distance[i],eligible[i]['series_id']))
            else:chosen=int(rng.integers(len(eligible)))
            r={**eligible[chosen],'stratum':label,'selection_slot':slot,'eligible_candidates':len(eligible),'selection_seed':2026112407}
            used.add(r['series_id']);first=r if first is None else first;r['window_id']=task_id({k:r[k] for k in ['dataset_id','series_id','forecast_origin','context_sha256','source_sha256']})
            c,y=arrays[(ds,r['series_id'],offset)];contexts[r['window_id']]=c;targets[r['window_id']]=y;selected.append(r)
    # Interleave domains so the first two integrity-gate windows are different datasets.
    selected=sorted(selected,key=lambda r:(r['selection_slot'],r['dataset_id']))
    for name,data in [('selected_contexts.npz',contexts),('evaluation_targets.npz',targets)]:
        path=out/name
        if path.exists():
            with np.load(path) as a:
                assert set(a.files)==set(data)
                for k in data:np.testing.assert_array_equal(a[k],data[k])
        else:
            with path.open('xb') as f:np.savez_compressed(f,**data);f.flush();os.fsync(f.fileno())
    manifest={'datasets':DATASETS,'source_revision':revision,'downloads':downloads,'windows':selected,
              'eligible_populations':populations,'rejections':rejections,'selection_uses_targets':False,
              'boundary_basis':'Chronos original paper section5.1/Table2: final48 held out; current export version pinned, actual segment membership unobservable',
              'elapsed_seconds':time.perf_counter()-started}
    (out/'dataset_provenance.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'windows':[(r['dataset_id'],r['series_id'],r['forecast_origin'],r['offset_from_end']) for r in selected],
                      'download_bytes':sum(d['bytes'] for d in downloads),'seconds':manifest['elapsed_seconds']}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);prepare(parser.parse_args().output)
