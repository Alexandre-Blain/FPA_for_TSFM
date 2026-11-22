"""Authorized first extended batch: <=8 series, 3 independent N20 blocks each.

Reuses the validated pilot worker with explicit direct-N20 block mode. Fresh
N60 validation is restricted to frozen first-block selections, <=2/window.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code/chronos_fpa'))
import bootstrap  # noqa: E402,F401
from run_chronos_microbenchmark import write_json,jsonable,memory_usage
from run_chronos_local_pilot import digest,git,utc,load,verify_freeze,worker as pilot_worker,compare_policy


def prepare(output,config_path):
    import numpy as np
    import torch
    from huggingface_hub import snapshot_download
    from chronos_extended_selection import select_extended,planned_streams,stream_identity
    from ensemble_store import task_id
    if (output/'frozen.json').exists():verify_freeze(output);return
    gate=load(output/'stage_a/stage_a_results.json');tests=load(output/'tests_precollection.json')
    if not gate['historical_metrics_reproduced'] or gate['correctness_problem_invalidating_sampling'] or tests['exit_code']!=0:
        raise ValueError('Stage A correctness/test gate failed')
    config=load(config_path)
    if config['max_original_series']!=8 or config['max_dense_blocks']!=24 or config['block_seeds']!=[2026112211,2026112212,2026112213]:
        raise ValueError('Unapproved batch ceiling or block seeds')
    panel,contexts=select_extended(ROOT,config)
    if not panel['windows']:raise ValueError('No new eligible original-series identities')
    # First two windows are different series (M4 then ERCOT when available).
    first=[]
    for ds in ('m4_daily','ercot'):
        found=next((w for w in panel['windows'] if w['dataset_id']==ds and w['stratum']=='representative'),None)
        if found:first.append(found)
    ordered=first+[w for w in panel['windows'] if w not in first]
    cells=[];rng_plan={};reserved=[]
    for w in ordered:
        for block,seed in enumerate(config['block_seeds']):
            scope={k:w[k] for k in ('dataset_id','series_id','forecast_origin','context_sha256')}
            scope.update(model_revision=config['model_revision'],grid_revision=panel['grid_revision'],
                         policy='q50_mass90_cap8_greedy_first_v1',sampling_seed=seed)
            namespace,streams=planned_streams(scope,w['window_id'],config['validation_seed'])
            cell={'scope':scope,'cell_id':task_id(scope),'window_id':w['window_id'],'primary':block==0,
                  'stratum':w['stratum'],'block_index':block,'rng_namespace':namespace}
            cells.append(cell);rng_plan[cell['cell_id']]=streams;reserved.extend(v['stream_id'] for v in streams.values())
        fresh_labels=[f'validation_b{b:02d}_{role}' for b in range(10) for role in ('reference','null')]+[f'validation_slot{s}_alternative' for s in range(2)]
        fresh={label:stream_identity(config['validation_seed'],namespace,label) for label in fresh_labels}
        rng_plan['validation_'+w['window_id']]=fresh;reserved.extend(v['stream_id'] for v in fresh.values())
    assert len(reserved)==len(set(reserved)) and len(cells)<=24
    write_json(output/'selection_manifest.json',{**panel,'frozen_utc':utc(),'model_draws_before_freeze':0})
    cp=output/'selected_contexts.npz'
    if cp.exists():
        with np.load(cp,allow_pickle=False) as a:
            assert set(a.files)==set(contexts)
            for k in contexts:np.testing.assert_array_equal(a[k],contexts[k])
    else:
        with cp.open('xb') as f:np.savez_compressed(f,**contexts);f.flush();os.fsync(f.fileno())
    write_json(output/'cell_plan.json',cells);write_json(output/'rng_plan.json',rng_plan)
    correlations=[]
    for i,a in enumerate(ordered):
        for b in ordered[i+1:]:
            if a['dataset_id']==b['dataset_id']:
                correlations.append({'dataset':a['dataset_id'],'series_a':a['series_id'],'series_b':b['series_id'],
                    'context_correlation':float(np.corrcoef(contexts[a['window_id']],contexts[b['window_id']])[0,1]),
                    'same_export_origin':a['forecast_origin']==b['forecast_origin'],
                    'interpretation':'source identities are distinct; shared ERCOT/load or currency processes remain dependent'})
    write_json(output/'cohort_dependence.json',correlations)
    cached=Path(snapshot_download(config['model_id'],revision=config['model_revision'],local_files_only=True))
    write_json(output/'model_cache.json',{'snapshot':str(cached),'files':{p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in cached.iterdir() if p.is_file()}})
    sources=sorted((ROOT/'code/chronos_fpa').rglob('*.py'))+[Path(__file__).resolve(),ROOT/'scripts/runs/run_chronos_local_pilot.py',ROOT/'scripts/runs/run_chronos_microbenchmark.py',ROOT/'scripts/viz/analyze_chronos_direct_baselines.py',config_path.resolve()]
    hashes={}
    for p in sources:
        name=p.relative_to(ROOT).as_posix();hashes[name]=digest(p);dest=output/'source_at_collection'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    write_json(output/'source_manifest.json',{'hashes':hashes,'source_digest':task_id(hashes)})
    device='cuda' if torch.cuda.is_available() else 'xpu' if hasattr(torch,'xpu') and torch.xpu.is_available() else 'cpu'
    write_json(output/'hardware_profile.json',{'device':device,'chosen_threads':4,'basis':'existing validated local pilot profile; no new stochastic profiling paths'})
    write_json(output/'environment.json',{'observed_utc':utc(),'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
        'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'device':device,
        'git_head':git('rev-parse','HEAD').strip(),'git_branch':git('branch','--show-current').strip(),'git_status_before_collection':git('status','--short'),
        'gitignore_sha256':digest(ROOT/'.gitignore'),'git_index_sha256':digest(ROOT/'.git/index'),
        'memory':memory_usage(),'disk_free_bytes':shutil.disk_usage(output).free,
        'network':'all HF offline flags and local_files_only=True; no downloads'})
    write_json(output/'stage_a_gate.json',{'status':'passed','utc':utc(),'historical_reproduction':True,'direct_comparison_tests_passed':True,
        'independence_and_indexing_checked':True,'no_sampling_law_inconsistency':True,
        'stage_a_results_sha256':digest(output/'stage_a/stage_a_results.json'),'tests_sha256':digest(output/'tests_precollection.json'),
        'provenance_note':'legacy CSV scans reveal prior exposure of some pilot identities; excluded now, not a sampling-law failure'})
    frozen=['selection_manifest.json','selected_contexts.npz','cell_plan.json','rng_plan.json','cohort_dependence.json',
            'source_manifest.json','environment.json','model_cache.json','hardware_profile.json','stage_a_gate.json']
    write_json(output/'frozen.json',{'schema':'extended_batch_freeze_v1','frozen_utc':utc(),'files':{n:digest(output/n) for n in frozen}})
    print(json.dumps({'frozen':True,'windows':[(w['dataset_id'],w['series_id'],w['stratum']) for w in ordered],
        'blocks':len(cells),'reserved_rng_streams':len(reserved),'shortfalls':panel['shortfalls']}),flush=True)


def read_block(output,cell):
    from chronos_pilot_validation import read_complete_cell
    marker,result,validation=read_complete_cell(output/'cells'/cell['cell_id'],cell['scope'],direct_samples=20)
    plan=load(output/'rng_plan.json')[cell['cell_id']]
    for m,a in validation['records']:
        actual=m['metadata']['rng'];expected=plan[actual['role']]
        if any(actual[k]!=v for k,v in expected.items()):raise ValueError('A sampled RNG differs from prospective plan')
    return marker,result,validation


def publish_selection(output,cell,result):
    from chronos_propagation_baselines import choose_contrasts
    chosen=choose_contrasts(result['distances'],load(output/'selection_manifest.json')['config']['control_selection_seed'],cell['window_id'])
    document={**chosen,'window_id':cell['window_id'],'block0_cell_id':cell['cell_id'],
        'block0_complete_sha256':digest(output/'cells'/cell['cell_id']/'complete.json'),'selected_from_block_index':0}
    path=output/'selections'/(cell['window_id']+'.json');path.parent.mkdir(exist_ok=True)
    if path.exists():
        if load(path)!=document:raise ValueError('Attempted adaptive change to frozen first-block selection')
    else:write_json(path,document)


def verify_window(output,wid):
    from chronos_offline_precision import assert_pool_compatible
    cells=[c for c in load(output/'cell_plan.json') if c['window_id']==wid]
    if len(cells)!=3:raise ValueError('Exactly three N20 blocks required')
    results=[read_block(output,c) for c in cells];streams=[]
    for _,_,v in results:streams.extend(m['metadata']['rng']['stream_id'] for m,_ in v['records'])
    if len(streams)!=len(set(streams)):raise ValueError('RNG stream reuse')
    if any(r[1]['forks']!=results[0][1]['forks'] for r in results[1:]):raise ValueError('Deterministic fork policy changed across blocks')
    for key in results[0][2]['lookup']:assert_pool_compatible([r[2]['lookup'][key][0] for r in results])
    return {'window_id':wid,'blocks':3,'paths':sum(r[2]['paths'] for r in results),
            'ensembles':sum(r[2]['ensembles'] for r in results),'unique_rng_streams':len(streams),
            'complete_sha256':{c['cell_id']:digest(output/'cells'/c['cell_id']/'complete.json') for c in cells}}


def validation_worker(output,wid):
    import numpy as np
    import torch
    from chronos_decoding import _ensemble_generator,decode_token_samples_to_values
    from chronos_exploratory import CachedDecoder
    from chronos_io import load_chronos_t5_raw
    from ensemble_store import EnsembleStore,read_snapshot,task_id
    verify_freeze(output);panel=load(output/'selection_manifest.json');config=panel['config']
    cell=next(c for c in load(output/'cell_plan.json') if c['window_id']==wid and c['block_index']==0)
    selection=load(output/'selections'/(wid+'.json'));directory=output/'validation'/wid;directory.mkdir(parents=True,exist_ok=True)
    if (directory/'complete.json').exists():read_validation(output,wid);print('Validation reused without model load',flush=True);return
    _,result,_=read_block(output,cell)
    with np.load(output/'selected_contexts.npz',allow_pickle=False) as a:context=a[wid].copy()
    torch.set_num_interop_threads(1);torch.set_num_threads(4);start=time.perf_counter()
    device=load(output/'hardware_profile.json')['device']
    model,tokenizer,mc=load_chronos_t5_raw(config['model_id'],device=device,dtype='float32',revision=config['model_revision'],local_files_only=True,attn_implementation='eager')
    ids,mask,scale=tokenizer.context_input_transform(torch.from_numpy(context)[None].to(device));engine=CachedDecoder(model,mc,ids,mask)
    greedy=engine.greedy(32);np.testing.assert_array_equal(greedy.numpy(),result['greedy_tokens'])
    replay,_=engine.replay(greedy[None]);parity=[compare_policy(engine.prefix_state(greedy[:t].tolist()).logits,replay[:,t],mc,f'validation_greedy_{t}') for t in range(32)]
    scope={**cell['scope'],'sampling_seed':config['validation_seed']};store=EnsembleStore(directory/'ensembles',scope=scope)
    shared={**scope,'window_id':wid,'experiment':output.name,'model_id':config['model_id'],
        'source_digest':load(output/'source_manifest.json')['source_digest'],'environment_sha256':digest(output/'environment.json'),
        'git_head':load(output/'environment.json')['git_head'],'device':device,'dtype':'float32','attention_backend':'eager',
        'cpu_threads':4,'tokenizer_scale':float(scale.reshape(-1)[0]),'horizon':32,'batch_size':8,'phase':'independent_validation'}
    plan=load(output/'rng_plan.json')['validation_'+wid];new_paths=0
    for slot,(b,token) in enumerate(selection['selected']):
        g=result['greedy_tokens'][b]
        for role,t,label in [('reference',g,f'validation_b{b:02d}_reference'),('null',g,f'validation_b{b:02d}_null'),('alternative',token,f'validation_slot{slot}_alternative')]:
            identity={**shared,'role':role,'position':b,'token':t,'prefix':greedy[:b].tolist()+[t],'sample_count':60}
            existing=store.get(identity)
            if existing is None:
                if (output/'STOP_REQUESTED').exists():raise InterruptedError('STOP_REQUESTED')
                generator,rng=_ensemble_generator(model,config['validation_seed'],cell['rng_namespace'],label)
                if any(rng[k]!=v for k,v in plan[label].items()):raise ValueError('Fresh RNG plan mismatch')
                begin=time.perf_counter();tokens=engine.sample(identity['prefix'],32,60,generator,batch_size=8)
                arrays={'tokens':tokens.numpy(),'values':decode_token_samples_to_values(tokenizer,tokens,scale).numpy(),
                    'context':context,'greedy_tokens':greedy.numpy(),'greedy_values':np.asarray(result['greedy_values'],dtype=np.float32)}
                existing=store.put(identity,arrays,{'rng':rng,'generation_seconds':time.perf_counter()-begin,
                    'captured_fields':['full_tokens','numeric_values','context','full_greedy_tokens','full_greedy_values'],
                    'omitted_replayable_fields':['logits','hidden_states','attentions'],'selection_sha256':digest(output/'selections'/(wid+'.json'))})
                new_paths+=60
            manifest,arrays=existing
            np.testing.assert_array_equal(arrays['values'],decode_token_samples_to_values(tokenizer,torch.from_numpy(arrays['tokens']),scale).numpy())
            sample=arrays['tokens'][0];plain,_=engine.replay(sample[None])
            for t_ in range(32):parity.append(compare_policy(engine.prefix_state(sample[:t_].tolist()).logits,plain[:,t_],mc,f'{label}_path0_{t_}'))
            engine.states.clear()
    snapshot=read_snapshot(store.directory,expected_scope=scope)
    write_json(directory/'parity.json',parity);write_json(directory/'timing.json',{'worker_seconds':time.perf_counter()-start,'new_paths':new_paths})
    write_json(directory/'complete.json',{'status':'complete','scope':scope,'selection_sha256':digest(output/'selections'/(wid+'.json')),
        'snapshot_id':snapshot['snapshot_id'],'manifest_sha256':snapshot['manifest_sha256'],
        'ensembles':len(snapshot['records']),'paths':sum(len(a['tokens']) for _,a in snapshot['records']),
        'files':{name:digest(directory/name) for name in ('parity.json','timing.json')}})
    read_validation(output,wid);print('Independent validation complete',wid,new_paths,flush=True)


def read_validation(output,wid):
    import numpy as np
    from ensemble_store import read_snapshot
    directory=output/'validation'/wid;marker=load(directory/'complete.json')
    selection=load(output/'selections'/(wid+'.json'))
    if marker['selection_sha256']!=digest(output/'selections'/(wid+'.json')):raise ValueError('Selection changed after validation')
    for n,d in marker['files'].items():
        if digest(directory/n)!=d:raise ValueError('Validation completion file changed')
    cell=next(c for c in load(output/'cell_plan.json') if c['window_id']==wid and c['block_index']==0)
    expected_scope={**cell['scope'],'sampling_seed':load(output/'selection_manifest.json')['config']['validation_seed']}
    if marker['scope']!=expected_scope:raise ValueError('Foreign validation scope')
    snapshot=read_snapshot(directory/'ensembles',expected_scope=expected_scope)
    if snapshot['snapshot_id']!=marker['snapshot_id'] or snapshot['manifest_sha256']!=marker['manifest_sha256']:raise ValueError('Validation snapshot changed')
    result=load(output/'cells'/cell['cell_id']/'results.json');expected=set();plan=load(output/'rng_plan.json')['validation_'+wid]
    for b,t in selection['selected']:
        expected|={(b,'reference',result['greedy_tokens'][b]),(b,'null',result['greedy_tokens'][b]),(b,'alternative',t)}
    actual=set()
    for m,a in snapshot['records']:
        i=m['identity'];actual.add((i['position'],i['role'],i['token']));rng=m['metadata']['rng']
        if any(rng[k]!=v for k,v in plan[rng['role']].items()):raise ValueError('Unexpected fresh validation RNG')
        if a['tokens'].shape!=(60,32) or i['sample_count']!=60:raise ValueError('Fresh validation requires N60')
        if i['prefix']!=result['greedy_tokens'][:i['position']]+[i['token']]:raise ValueError('Validation has wrong conditioning')
        np.testing.assert_array_equal(a['tokens'][:,:len(i['prefix'])],np.repeat([i['prefix']],60,axis=0))
        np.testing.assert_array_equal(a['greedy_tokens'],result['greedy_tokens'])
        if hashlib.sha256(a['context'].tobytes()).hexdigest()!=i['context_sha256']:raise ValueError('Validation context mismatch')
    streams=[m['metadata']['rng']['stream_id'] for m,_ in snapshot['records']]
    if expected!=actual or len(actual)!=len(snapshot['records']) or len(streams)!=len(set(streams)):raise ValueError('Missing, duplicated or expanded validation contrasts')
    if marker['ensembles']!=len(snapshot['records']) or marker['paths']!=60*len(snapshot['records']):raise ValueError('Validation accounting mismatch')
    return marker,snapshot


def supervised(output,label,worker_args):
    from windows_job import WindowsJobProcess
    attempts=output/'attempts';attempts.mkdir(exist_ok=True);stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');stem=label+'_'+stamp
    env=dict(os.environ,HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false',PYTHONUNBUFFERED='1',GIT_OPTIONAL_LOCKS='0')
    command=[sys.executable,str(Path(__file__).resolve()),'--output',str(output),*worker_args];samples=[];start=time.perf_counter()
    if shutil.disk_usage(output).free<2*1024**3:raise RuntimeError('Need 2 GiB disk headroom for bounded capture and atomic temporaries')
    with (attempts/(stem+'.log')).open('wb') as log:
        process=WindowsJobProcess(command,ROOT,env,log,memory_limit=None)
        try:
            critically_low=0
            while process.poll() is None:
                row={'utc':utc(),'elapsed_seconds':time.perf_counter()-start,'peak_job_committed_bytes':process.peak_job_memory(),**memory_usage(),'disk_free_bytes':shutil.disk_usage(output).free}
                samples.append(row);write_json(output/'resources_live.json',{'phase':label,**row})
                critically_low=critically_low+1 if row['system_free_bytes']<64*1024**2 else 0
                if critically_low>=5 or row['disk_free_bytes']<1024**3:raise RuntimeError('Critical physical-memory/disk safety floor; durable data preserved')
                if (output/'STOP_REQUESTED').exists():print('Stop requested; worker pauses at a durable ensemble',flush=True)
                time.sleep(1)
            code=process.wait()
        finally:
            if process.poll() is None:process.kill();process.wait()
            write_json(attempts/(stem+'.json'),{'label':label,'exit_code':process.returncode,'elapsed_seconds':time.perf_counter()-start,
                'peak_job_committed_bytes':process.peak_job_memory(),'samples':samples,'arbitrary_time_or_job_memory_cap':None})
            process.close()
    if code!=0:raise RuntimeError(f'Batch stopped at {label}, worker exit {code}; inspect {stem}.log')


def execute(output):
    panel=verify_freeze(output);cells=load(output/'cell_plan.json')
    if len(cells)>24 or len(panel['windows'])>8:raise ValueError('Authorized ceiling exceeded')
    for index,cell in enumerate(cells):
        if (output/'STOP_REQUESTED').exists():raise InterruptedError('STOP_REQUESTED')
        directory=output/'cells'/cell['cell_id']
        if not (directory/'complete.json').exists():supervised(output,f'block{index:02d}',['--worker',str(index)])
        _,result,_=read_block(output,cell)
        if cell['block_index']==0:publish_selection(output,cell,result)
        if cell['block_index']==2:
            checked=verify_window(output,cell['window_id']);print('Window complete',cell['scope']['series_id'],checked['paths'],flush=True)
            if index==5:
                first_ids=list(dict.fromkeys(c['window_id'] for c in cells[:6]));assert len(first_ids)==2
                if not (output/'first_two_gate.json').exists():
                    write_json(output/'first_two_gate.json',{'status':'passed','utc':utc(),'windows':[verify_window(output,wid) for wid in first_ids],
                        'checks':'decoder/conditioning parity; q50/residual; exact tokens/values; raw W1/ED; complete hashes; independent frozen RNG; monitored resources'})
                print('First two different-series windows passed; proceeding within authorized ceiling',flush=True)
    windows=list(dict.fromkeys(c['window_id'] for c in cells))
    for wid in windows:
        if (output/'STOP_REQUESTED').exists():raise InterruptedError('STOP_REQUESTED')
        if not (output/'validation'/wid/'complete.json').exists():supervised(output,'validation_'+wid[:12],['--validation-worker',wid])
        read_validation(output,wid)
    if not (output/'batch_complete.json').exists():
        write_json(output/'batch_complete.json',{'status':'complete','completed_utc':utc(),'original_series':len(windows),'dense_blocks':len(cells),
            'windows':[verify_window(output,wid) for wid in windows],
            'validation_complete_sha256':{wid:digest(output/'validation'/wid/'complete.json') for wid in windows},
            'stopping_gate':'STOP after this batch scientific analysis; no second batch authorized'})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,default=ROOT/'configs/chronos_extended_batch/batch_v1.json')
    p.add_argument('--prepare',action='store_true');p.add_argument('--execute',action='store_true')
    p.add_argument('--worker',type=int);p.add_argument('--validation-worker')
    args=p.parse_args();out=args.output.resolve()
    if not out.is_relative_to((ROOT/'result').resolve()):raise ValueError('Output must remain under result/')
    try:
        if args.worker is not None:
            if not 0<=args.worker<len(load(out/'cell_plan.json')):raise ValueError('Unknown block')
            pilot_worker(out,args.worker,extended_block=True)
        elif args.validation_worker:validation_worker(out,args.validation_worker)
        elif args.prepare:prepare(out,args.config)
        elif args.execute:execute(out)
        else:p.error('Choose prepare or execute')
    except BaseException:
        write_json(out/'last_failure.json',{'utc':utc(),'traceback':traceback.format_exc(),'new_inference_halted':True});raise


if __name__=='__main__':main()
