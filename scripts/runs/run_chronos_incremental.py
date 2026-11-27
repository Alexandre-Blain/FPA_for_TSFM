"""Local bounded H1/H2 campaign with durable model-time and artifact ceilings."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'code/chronos_fpa'),str(ROOT/'scripts/viz')]
import bootstrap  # noqa: E402,F401


def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def save(path,doc):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_name(path.name+'.pending')
    with pending.open('w',encoding='utf-8') as f:
        json.dump(doc,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    # Windows readers/antivirus may briefly open the destination without
    # FILE_SHARE_DELETE. Retry the SAME durable candidate, never discard it.
    for attempt in range(51):
        try:
            os.replace(pending,path);break
        except PermissionError:
            if attempt==50:raise
            time.sleep(.1)


def memory_free():
    import ctypes
    class Status(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ['total','free','page','pagefree','vtotal','vfree','extended']]
    s=Status();s.length=ctypes.sizeof(s)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)):raise ctypes.WinError()
    return int(s.free)


def stage_config(run,phase):return load(run/('pilot_config.json' if phase=='pilot' else 'frozen_config.json'))


def verify_sources(run,phase):
    doc=load(run/('pilot_freeze.json' if phase=='pilot' else 'frozen.json'))
    for n,h in doc['files'].items():
        if digest(run/n)!=h:raise ValueError('Frozen input changed: '+n)
    archive=run/('source_at_pilot' if phase=='pilot' else 'source_at_collection')
    for n,h in doc['source_hashes'].items():
        if digest(archive/n)!=h:raise ValueError('Archived source changed: '+n)
        if n.endswith('.py') and digest(ROOT/n)!=h:raise ValueError('Collection source changed: '+n)
    return doc


def freeze_sources(run,pilot):
    config_path=ROOT/'configs/chronos_incremental/campaign_v1.json'
    if not load(run/'gate_A_tests.json')['exit_code']==0:raise ValueError('Gate A tests required')
    if not pilot and not load(run/'gate_C_tests.json')['exit_code']==0:raise ValueError('Final source tests required')
    config=load(config_path);name='pilot_config.json' if pilot else 'frozen_config.json'
    if not pilot and config['final_allocation'] is None:raise ValueError('Final allocation must be chosen from timing before full freeze')
    marker=run/('pilot_freeze.json' if pilot else 'frozen.json')
    if marker.exists():raise ValueError('Existing freeze is immutable')
    save(run/name,config)
    paths=sorted((ROOT/'code/chronos_fpa').rglob('*.py'))+[Path(__file__).resolve(),ROOT/'scripts/data/prepare_chronos_incremental.py',config_path]
    if pilot:paths=[p for p in paths if p.name!='chronos_incremental_h2.py']
    else:paths+=sorted((ROOT/'scripts/runs').glob('freeze_chronos_incremental*.py'))
    archive=run/('source_at_pilot' if pilot else 'source_at_collection');hashes={}
    for p in paths:
        n=p.relative_to(ROOT).as_posix();target=archive/n;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target);hashes[n]=digest(p)
    names=['cohort.json','cohort_and_splits.csv','contexts.npz','sealed_targets.npz',name,'model_cache.json','gate_A_tests.json']
    if not pilot:names+=['allocation.json','gate_B.json','methodology.json','gate_C_tests.json']
    if not pilot and (run/'compatible_checkpoints.json').exists():names+=['compatible_checkpoints.json']
    save(marker,{'utc':utc(),'stage':'technical pilot' if pilot else 'full frozen campaign',
        'files':{n:digest(run/n) for n in names},'source_hashes':hashes,
        'source_id':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()})
    cache=load(run/'model_cache.json')
    for n,m in cache['files'].items():
        if digest(Path(cache['snapshot'])/n)!=m['sha256']:raise ValueError('Pinned model changed')
    print('FROZEN',marker.name,flush=True)


def verify_complete(run,phase,wid):
    from ensemble_store import read_snapshot
    directory=run/phase/wid;marker=load(directory/'complete.json')
    freeze=load(run/('pilot_freeze.json' if phase=='pilot' else 'frozen.json'))
    if marker['scope']['source_freeze_id']!=freeze['source_id']:
        compatibility=load(run/'compatible_checkpoints.json') if (run/'compatible_checkpoints.json').exists() else {}
        allowed=compatibility.get(phase+'/'+wid)
        if not allowed or allowed['source_freeze_id']!=marker['scope']['source_freeze_id'] or allowed['complete_sha256']!=digest(directory/'complete.json'):
            raise ValueError('Checkpoint source not explicitly compatible with current frozen implementation')
    snapshot=read_snapshot(directory/'ensembles',expected_scope=marker['scope'])
    if snapshot['snapshot_id']!=marker['snapshot_id'] or snapshot['manifest_sha256']!=marker['manifest_sha256']:
        raise ValueError('Complete snapshot changed')
    for n,h in marker['files'].items():
        if digest(directory/n)!=h:raise ValueError('Complete derived file changed: '+n)
    if marker['paths']!=sum(len(a['tokens']) for m,a in snapshot['records']):raise ValueError('Path count mismatch')
    return marker,snapshot


def worker(run,phase,window_ids):
    freeze=verify_sources(run,phase);config=stage_config(run,phase)
    windows={w['window_id']:w for w in load(run/'cohort.json')['windows']}
    pending=[]
    for wid in window_ids:
        if (run/phase/wid/'complete.json').exists():verify_complete(run,phase,wid)
        else:pending.append(wid)
    if not pending:
        print('All requested cells reused without model loading',flush=True);return
    import torch
    from chronos_io import load_chronos_t5_raw
    from chronos_incremental_collection import WindowCollector
    from chronos_incremental import first_token_partition,first_deviation_partition
    torch.set_num_interop_threads(1);torch.set_num_threads(config['cpu_threads'])
    started=time.perf_counter();bundle=load_chronos_t5_raw(config['model_id'],device='cpu',dtype='float32',revision=config['model_revision'],local_files_only=True,attn_implementation='eager')
    loading=time.perf_counter()-started
    for wid in pending:
        w=windows[wid]
        if (phase=='H1' and w['study']!='H1') or (phase=='H2' and w['study']!='H2') or (phase=='pilot' and w['study']!='technical_pilot'):
            raise ValueError('Study identity not authorized in phase')
        start=time.perf_counter();collector=WindowCollector(run,w,bundle,dict(config),phase,freeze['source_id'])
        if phase=='pilot':
            profiles=collector.technical_profile()
            totals={b:sum(p['seconds'] for p in profiles if p['batch_size']==b) for b in (8,16,32)}
            best=min(totals,key=totals.get);collector.config['batch_size']=best
            collector.collect_h1();timings=[]
            for method,groups in [('first_token',first_token_partition(collector.forks)),('first_deviation',first_deviation_partition(collector.forks))]:
                for g in groups:
                    m,a=collector.draw('technical_'+method+'_'+g['name'],g['prefix'],g['support'],20,'technical_stratum',g['position'])
                    timings.append({'method':method,'group':g,'seconds':m['metadata']['generation_seconds'],'N':20})
            save(collector.directory/'h2_timing.json',timings)
            extra={'pilot_selected_batch':best}
        elif phase=='H1':collector.collect_h1();extra={}
        else:
            from chronos_incremental_h2 import collect_h2
            extra=collect_h2(collector)
        paths=collector.finish({'worker_model_loading_seconds':loading/len(pending),
            'window_seconds':time.perf_counter()-start,**extra})
        print('COMPLETE',phase,w['dataset_id'],w['series_id'],'paths',paths,flush=True)
        del collector
        import gc
        gc.collect()


def charged_seconds(run):
    total=0.
    for p in (run/'attempts').glob('*.json'):
        d=load(p);total+=d['elapsed_seconds']+(2. if d.get('running') else 0.)
    return total


def new_bytes(run):
    total=0
    for directory in [run,ROOT/'data/raw/chronos_incremental_20261126']:
        for p in directory.rglob('*'):
            try:
                if p.is_file():total+=p.stat().st_size
            except FileNotFoundError:pass  # atomic publication between traversal/stat
    return total


def supervised(run,phase,window_ids):
    from windows_job import WindowsJobProcess
    config=stage_config(run,phase);spent=charged_seconds(run)
    if spent>=config['maximum_model_seconds']-5:raise RuntimeError('Cumulative model-time ceiling reached')
    if new_bytes(run)>=config['maximum_new_bytes']-512*2**20:raise RuntimeError('Artifact ceiling headroom exhausted')
    if memory_free()<1400*2**20:raise RuntimeError('Insufficient free RAM before model launch')
    attempts=run/'attempts';attempts.mkdir(exist_ok=True);label=phase+'_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    receipt=attempts/(label+'.json');log_path=attempts/(label+'.log')
    env=dict(os.environ,HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false',PYTHONUNBUFFERED='1',OMP_NUM_THREADS=str(config['cpu_threads']),GIT_OPTIONAL_LOCKS='0')
    command=[sys.executable,str(Path(__file__).resolve()),'--run',str(run),'--worker',phase,*window_ids]
    start=time.perf_counter();doc={'phase':phase,'windows':window_ids,'utc':utc(),'running':True,'elapsed_seconds':0.,'peak_job_committed_bytes':0,'min_system_free_bytes':memory_free()}
    save(receipt,doc);code=None
    with log_path.open('wb') as log:
        process=WindowsJobProcess(command,ROOT,env,log,memory_limit=None)
        try:
            low=0;last_disk=0;size=new_bytes(run)
            while process.poll() is None:
                elapsed=time.perf_counter()-start;free=memory_free();peak=process.peak_job_memory()
                if elapsed-last_disk>=10:size=new_bytes(run);last_disk=elapsed
                doc.update(elapsed_seconds=elapsed,peak_job_committed_bytes=max(doc['peak_job_committed_bytes'],peak),min_system_free_bytes=min(doc['min_system_free_bytes'],free),new_bytes=size,heartbeat_utc=utc())
                save(receipt,doc);save(run/'resources_live.json',{'phase':phase,'model_seconds_cumulative':spent+elapsed,**doc})
                low=low+1 if free<128*2**20 else 0
                if spent+elapsed>=config['maximum_model_seconds']-3:raise RuntimeError('Cumulative 16h model ceiling')
                if size>=config['maximum_new_bytes']-256*2**20 or shutil.disk_usage(run).free<2**30 or low>=5:raise RuntimeError('Memory/disk/artifact safeguard; durable partial cells preserved')
                time.sleep(.5)
            code=process.wait()
        except BaseException as e:
            doc['stop_reason']=str(e);raise
        finally:
            if process.poll() is None:process.kill();process.wait()
            doc.update(running=False,elapsed_seconds=time.perf_counter()-start,exit_code=process.returncode,completed_utc=utc())
            save(receipt,doc)
            save(run/'resources_live.json',{'model_seconds_cumulative':spent+doc['elapsed_seconds'],**doc})
            process.close()
    if code:raise RuntimeError('Model worker failed; see '+str(log_path))
    return doc


def execute(run,phase):
    verify_sources(run,phase)
    if phase=='pilot':ids=[w['window_id'] for w in load(run/'cohort.json')['windows'] if w['study']=='technical_pilot']
    else:ids=load(run/'allocation.json')[phase.lower()+'_windows']
    chunk=1 if phase in ('pilot','H2') else 8
    for i in range(0,len(ids),chunk):
        pending=[]
        for wid in ids[i:i+chunk]:
            if (run/phase/wid/'complete.json').exists():verify_complete(run,phase,wid)
            else:pending.append(wid)
        if pending:supervised(run,phase,pending)
    save(run/(phase+'_complete.json'),{'status':'complete','utc':utc(),'windows':ids,
        'complete_sha256':{wid:digest(run/phase/wid/'complete.json') for wid in ids}})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True,type=Path)
    p.add_argument('--freeze-pilot',action='store_true');p.add_argument('--freeze',action='store_true')
    p.add_argument('--execute',choices=['pilot','H1','H2']);p.add_argument('--worker',nargs='+')
    args=p.parse_args();run=args.run.resolve()
    if args.freeze_pilot:freeze_sources(run,True)
    elif args.freeze:freeze_sources(run,False)
    elif args.worker:worker(run,args.worker[0],args.worker[1:])
    elif args.execute:execute(run,args.execute)
    else:p.error('Choose a frozen stage')
