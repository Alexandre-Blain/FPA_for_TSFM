"""Bounded H32 discovery, N120 validation and direct-prefix H64 collection.

Reuses the historical dense worker unchanged. No broad campaign entry point.
All extra ensembles have predeclared RNG namespaces and immutable publication.
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

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'code/chronos_fpa'),str(ROOT/'scripts/viz')]
import bootstrap  # noqa: E402,F401
from run_chronos_local_pilot import digest,git,utc,load,verify_freeze,compare_policy,worker as dense_worker
from run_chronos_microbenchmark import write_json,memory_usage
from run_chronos_extended_batch import read_block,verify_window
from chronos_extended_selection import planned_streams,stream_identity
from ensemble_store import task_id


def prepare(out,config_path):
    import numpy as np
    if (out/'frozen.json').exists():verify_freeze(out);return
    cfg=load(config_path);provenance=load(out/'dataset_provenance.json')
    if load(out/'offline_existing/offline_complete.json')['new_model_draws']!=0:raise ValueError('Offline exploration must precede inference')
    tests=load(out/'tests_precollection.json')
    if tests['exit_code']!=0:raise ValueError('Precollection tests failed')
    if len(provenance['windows'])!=6 or len({w['dataset_id'] for w in provenance['windows']})!=2:raise ValueError('Authorized six-window/two-dataset ceiling')
    panel={'schema':'chronos_discovery_20261124','windows':provenance['windows'],'config':cfg,
           'source_hashes':{d['path']:d['sha256'] for d in provenance['downloads']},'dataset_provenance_sha256':digest(out/'dataset_provenance.json')}
    panel['grid_revision']=task_id(panel);write_json(out/'selection_manifest.json',panel)
    cells=[];rng={};reserved=[]
    for w in panel['windows']:
        for block,seed in enumerate(cfg['block_seeds']):
            scope={k:w[k] for k in ('dataset_id','series_id','forecast_origin','context_sha256')}
            scope.update(model_revision=cfg['model_revision'],grid_revision=panel['grid_revision'],policy='q50_mass90_cap8_greedy_first_v1',sampling_seed=seed)
            namespace,streams=planned_streams(scope,w['window_id'],cfg['validation_seed']);cid=task_id(scope)
            cells.append({'scope':scope,'cell_id':cid,'window_id':w['window_id'],'primary':block==0,'stratum':w['stratum'],'block_index':block,'rng_namespace':namespace})
            rng[cid]=streams;reserved.extend(v['stream_id'] for v in streams.values())
        labels=[f'fresh_b{b:02d}_{role}' for b in range(10) for role in ('reference','null')]+[f'fresh_slot{s}_alternative' for s in range(2)]
        extra={label:stream_identity(cfg['validation_seed'],namespace,label) for label in labels}
        extra['natural_reference']=stream_identity(cfg['natural_seed'],namespace,'natural_reference')
        for block in range(3):
            for t in range(31):
                label=f'cpd_block{block}_P{t:02d}';extra[label]=stream_identity(cfg['cpd_seed']+block,namespace,label)
        for t in range(31):
            label=f'cpd_fresh_P{t:02d}';extra[label]=stream_identity(cfg['cpd_validation_seed'],namespace,label)
        rng['extra_'+w['window_id']]=extra;reserved.extend(v['stream_id'] for v in extra.values())
    if len(cells)!=18 or len(reserved)!=len(set(reserved)):raise ValueError('Duplicate/expanded prospective plan')
    write_json(out/'cell_plan.json',cells);write_json(out/'rng_plan.json',rng)
    london=next(w for w in panel['windows'] if w['documented_pretraining_status']=='in_domain' and w['offset_from_end']==64)
    aus=[w for w in panel['windows'] if w['documented_pretraining_status']=='zero_shot'][:2]
    write_json(out/'cpd_windows.json',{'windows':[london['window_id']]+[w['window_id'] for w in aus],
        'selection':'context-only cohort strata: London mixed boundary, first two Australian strata; no FPA outcomes'})
    cache=load(ROOT/'result/extended_batch_20261122T115422Z/model_cache.json')
    for name,meta in cache['files'].items():
        if digest(Path(cache['snapshot'])/name)!=meta['sha256']:raise ValueError('Pinned local model changed')
    write_json(out/'model_cache.json',cache)
    sources=sorted((ROOT/'code/chronos_fpa').rglob('*.py'))+[Path(__file__).resolve(),ROOT/'scripts/runs/run_chronos_local_pilot.py',ROOT/'scripts/runs/run_chronos_extended_batch.py',ROOT/'scripts/runs/run_chronos_microbenchmark.py',ROOT/'scripts/data/prepare_chronos_discovery_data.py',ROOT/'scripts/viz/analyze_chronos_discovery.py',config_path.resolve()]
    hashes={}
    for p in sources:
        name=p.relative_to(ROOT).as_posix();hashes[name]=digest(p);dest=out/'source_at_collection'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    write_json(out/'source_manifest.json',{'hashes':hashes,'source_digest':task_id(hashes)})
    write_json(out/'hardware_profile.json',{'device':'cpu','chosen_threads':4,'basis':'reuse validated profile; no stochastic profiling'})
    write_json(out/'environment.json',{'utc':utc(),'git_head':git('rev-parse','HEAD').strip(),'branch':git('branch','--show-current').strip(),
        'working_tree':git('status','--short'),'python':sys.version,'platform':platform.platform(),
        'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'gitignore_sha256':digest(ROOT/'.gitignore'),
        'git_index_sha256':digest(ROOT/'.git/index'),'memory':memory_usage(),'disk_free_bytes':shutil.disk_usage(out).free})
    files=['selection_manifest.json','selected_contexts.npz','evaluation_targets.npz','cell_plan.json','rng_plan.json','cpd_windows.json','dataset_provenance.json',
           'source_manifest.json','model_cache.json','hardware_profile.json','environment.json','tests_precollection.json','offline_existing/offline_complete.json',
           'cohort_dependence.json','sga_reproduction_gate.json']
    write_json(out/'frozen.json',{'schema':'chronos_discovery_freeze_v1','utc':utc(),'files':{n:digest(out/n) for n in files},'reserved_streams':len(reserved)})
    print('FROZEN',len(cells),'blocks;',len(reserved),'reserved streams',flush=True)


def extra_scope(out,wid,phase,horizon):
    cfg=load(out/'selection_manifest.json')['config'];base=next(c for c in load(out/'cell_plan.json') if c['window_id']==wid)
    seed=cfg['natural_seed'] if phase=='natural_reference' else cfg['cpd_seed'] if phase=='cpd' else cfg['cpd_validation_seed'] if phase=='cpd_fresh' else cfg['validation_seed']
    return {**base['scope'],'sampling_seed':seed,'phase':phase,'horizon':horizon},base


def verify_extra(out,wid,phase,horizon):
    import numpy as np
    from ensemble_store import read_snapshot
    scope,base=extra_scope(out,wid,phase,horizon);directory=out/phase/wid;marker=load(directory/'complete.json')
    for n,h in marker['files'].items():
        if digest(directory/n)!=h:raise ValueError('Additional ensemble file changed')
    if marker['selection_file'] and digest(out/marker['selection_file'])!=marker['selection_sha256']:raise ValueError('Postselection identity changed')
    snapshot=read_snapshot(directory/'ensembles',expected_scope=scope)
    if marker['snapshot_id']!=snapshot['snapshot_id'] or marker['manifest_sha256']!=snapshot['manifest_sha256']:raise ValueError('Additional snapshot changed')
    planned=load(out/'rng_plan.json')['extra_'+wid];streams=[];actual=set()
    for m,a in snapshot['records']:
        i=m['identity'];r=m['metadata']['rng'];expected=planned[r['role']]
        if any(r[k]!=v for k,v in expected.items()):raise ValueError('Foreign RNG stream')
        if len(a['tokens'])!=i['sample_count'] or a['tokens'].shape[1]!=horizon:raise ValueError('Bad extra path count/horizon')
        np.testing.assert_array_equal(a['tokens'][:,:len(i['prefix'])],np.repeat([i['prefix']],len(a['tokens']),axis=0))
        if hashlib.sha256(a['context'].tobytes()).hexdigest()!=i['context_sha256']:raise ValueError('Wrong context')
        p=i['position'];expected_prefix=a['greedy_tokens'][:p].tolist()+([i['token']] if i['token'] is not None else [])
        if i['prefix']!=expected_prefix:raise ValueError('Wrong greedy conditioning')
        actual.add((p,i['role'],i['token'],i['block'],i['sample_count']))
        streams.append(r['stream_id'])
    if len(streams)!=len(set(streams)) or marker['paths']!=sum(len(a['tokens']) for _,a in snapshot['records']):raise ValueError('Wrong extra accounting')
    if len(snapshot['records'])!=marker['ensembles']:raise ValueError('Wrong extra ensemble count')
    if actual!=expected_extra_keys(out,wid,phase):raise ValueError('Missing/expanded additional ensemble roles')
    return marker,snapshot


def expected_extra_keys(out,wid,phase):
    if phase=='natural_reference':return {(0,'natural_reference',None,0,120)}
    if phase=='cpd':return {(p,'direct_cpd',None,b,20) for b in range(3) for p in range(31)}
    if phase=='cpd_fresh':
        rows=load(out/'cpd_selections'/(wid+'.json'))['transitions'];positions={r[k] for r in rows for k in ('left','right')}
        if len(rows)>3 or len(positions)>6:raise ValueError('CPD ceiling exceeded')
        return {(p,'direct_cpd',None,0,120) for p in positions}
    rows=load(out/'validation_plan.json')['contrasts'];validate_allocation(rows)
    base=next(c for c in load(out/'cell_plan.json') if c['window_id']==wid and c['block_index']==0)
    greedy=load(out/'cells'/base['cell_id']/'results.json')['greedy_tokens'];keys=set()
    for r in rows:
        if r['window_id']==wid:keys|={(r['b'],role,t,0,120) for role,t in [('reference',greedy[r['b']]),('null',greedy[r['b']]),('alternative',r['token'])]}
    return keys


def validate_allocation(rows):
    counts={}
    for r in rows:counts[r['window_id']]=counts.get(r['window_id'],0)+1
    controls=sum(r['selection']=='random_control' for r in rows)
    if len(rows)>8 or len(rows)-controls>6 or controls<2 or max(counts.values(),default=0)>2:raise ValueError('N120 validation allocation exceeds scope or lacks controls')
    if len({(r['window_id'],r['b'],r['token']) for r in rows})!=len(rows):raise ValueError('Duplicate validation contrasts')


def engine_for(out,wid,horizon):
    import numpy as np
    import torch
    from chronos_io import load_chronos_t5_raw
    from chronos_exploratory import CachedDecoder
    cfg=verify_freeze(out)['config'];torch.set_num_interop_threads(1);torch.set_num_threads(cfg['cpu_threads'])
    with np.load(out/'selected_contexts.npz') as f:context=f[wid].copy()
    model,tokenizer,mc=load_chronos_t5_raw(cfg['model_id'],device='cpu',dtype='float32',revision=cfg['model_revision'],local_files_only=True,attn_implementation='eager')
    ids,mask,scale=tokenizer.context_input_transform(torch.from_numpy(context)[None]);engine=CachedDecoder(model,mc,ids,mask);greedy=engine.greedy(horizon)
    base=next(c for c in load(out/'cell_plan.json') if c['window_id']==wid and c['block_index']==0)
    np.testing.assert_array_equal(greedy[:32].numpy(),load(out/'cells'/base['cell_id']/'results.json')['greedy_tokens'])
    plain,_=engine.replay(greedy[None]);parity=[compare_policy(engine.prefix_state(greedy[:t].tolist()).logits,plain[:,t],mc,f'greedy_{t}') for t in (0,9,horizon-1)]
    return engine,tokenizer,scale,context,greedy,parity


def transition_selection(out,wid,store,greedy_values,context):
    import numpy as np
    from chronos_discovery import scenario_events
    path=out/'cpd_selections'/(wid+'.json');path.parent.mkdir(exist_ok=True)
    records={m['identity']['position']:a for m,a in store_records(store) if m['identity']['block']==0}
    if len(records)!=31:raise ValueError('Need all31 block0 prefixes before transition selection')
    probabilities={p:scenario_events(a['values'],context,greedy_values).mean(0) for p,a in records.items()};choices=[]
    for p in range(30):
        gap=probabilities[p+1]-probabilities[p];event=max(range(2,7),key=lambda i:abs(gap[i]));choices.append({'left':p,'right':p+1,'event':event,'block0_gap':float(gap[event])})
    candidates=sorted(choices,key=lambda r:(-abs(r['block0_gap']),r['left']))[:2]
    remaining=[r for r in choices if r['left'] not in {x['left'] for x in candidates}]
    seed=int(hashlib.sha256((wid+'CPD_control').encode()).hexdigest()[:16],16);control=remaining[int(np.random.default_rng(seed).integers(len(remaining)))]
    doc={'window_id':wid,'selected_from_block':0,'transitions':[{**r,'selection':'scientific'} for r in candidates]+[{**control,'selection':'random_control'}],
         'block0_object_ids':sorted(m['task_id'] for m,a in store_records(store) if m['identity']['block']==0)}
    if path.exists():
        if load(path)!=doc:raise ValueError('CPD exploratory selection changed')
    else:write_json(path,doc)


def store_records(store):
    from ensemble_store import read_snapshot
    return read_snapshot(store.directory,expected_scope=store.scope)['records']


def extra_worker(out,wid,phase):
    import numpy as np
    import torch
    from ensemble_store import EnsembleStore,read_snapshot
    from chronos_decoding import _ensemble_generator,decode_token_samples_to_values
    cfg=verify_freeze(out)['config'];horizon=64 if phase in ('cpd','cpd_fresh') else 32
    if phase.startswith('cpd') and wid not in load(out/'cpd_windows.json')['windows']:raise ValueError('Unapproved H64 window')
    directory=out/phase/wid;directory.mkdir(parents=True,exist_ok=True)
    if (directory/'complete.json').exists():verify_extra(out,wid,phase,horizon);print('Extra reused without model load',phase,wid,flush=True);return
    scope,base=extra_scope(out,wid,phase,horizon);start=time.perf_counter();engine,tokenizer,scale,context,greedy,parity=engine_for(out,wid,horizon)
    gv=decode_token_samples_to_values(tokenizer,greedy[None],scale).numpy()[0];store=EnsembleStore(directory/'ensembles',scope=scope);selection_file=None
    if phase=='fresh_validation':
        selection_file='validation_plan.json';all_rows=load(out/selection_file)['contrasts'];validate_allocation(all_rows)
        rows=[r for r in all_rows if r['window_id']==wid];tasks=[]
        for slot,r in enumerate(rows):
            b,t=r['b'],r['token'];g=int(greedy[b])
            for role,token,label in [('reference',g,f'fresh_b{b:02d}_reference'),('null',g,f'fresh_b{b:02d}_null'),('alternative',t,f'fresh_slot{slot}_alternative')]:
                task=(b,role,token,greedy[:b].tolist()+[token],120,label,0)
                if not any(x[:3]==task[:3] for x in tasks):tasks.append(task)
    elif phase=='natural_reference':
        selection_file='validation_plan.json'
        if not (out/selection_file).exists():raise ValueError('Natural evaluation reference must remain sealed before candidate/method freeze')
        tasks=[(0,'natural_reference',None,[],120,'natural_reference',0)]
    elif phase=='cpd':tasks=[(p,'direct_cpd',None,greedy[:p].tolist(),20,f'cpd_block{block}_P{p:02d}',block) for block in range(3) for p in range(31)]
    else:
        selection_file=f'cpd_selections/{wid}.json';transitions=load(out/selection_file)['transitions'];positions=sorted({r[k] for r in transitions for k in ('left','right')})
        if len(positions)>6 or len(transitions)>3:raise ValueError('CPD validation ceiling')
        tasks=[(p,'direct_cpd',None,greedy[:p].tolist(),120,f'cpd_fresh_P{p:02d}',0) for p in positions]
    planned=load(out/'rng_plan.json')['extra_'+wid];new_paths=0
    for position,role,token,prefix,count,label,block in tasks:
        identity={**scope,'window_id':wid,'model_id':cfg['model_id'],'role':role,'position':position,'token':token,'prefix':prefix,'sample_count':count,'block':block,
                  'source_digest':load(out/'source_manifest.json')['source_digest'],'batch_size':8,'dtype':'float32','attention_backend':'eager','cpu_threads':4,
                  'tokenizer_scale':float(scale.reshape(-1)[0]),'rng_namespace':base['rng_namespace']}
        record=store.get(identity)
        if record is None:
            if (out/'STOP_REQUESTED').exists():raise InterruptedError('STOP_REQUESTED; completed ensembles preserved')
            generator,rng=_ensemble_generator(engine.model,planned[label]['root_seed'],base['rng_namespace'],label)
            if any(rng[k]!=v for k,v in planned[label].items()):raise ValueError('Predeclared RNG mismatch')
            begin=time.perf_counter();tokens=engine.sample(prefix,horizon,count,generator,batch_size=8);values=decode_token_samples_to_values(tokenizer,tokens,scale).numpy()
            record=store.put(identity,{'tokens':tokens.numpy(),'values':values,'context':context,'greedy_tokens':greedy.numpy(),'greedy_values':gv},
                {'rng':rng,'generation_seconds':time.perf_counter()-begin,'selection_sha256':digest(out/selection_file) if selection_file else None,
                 'captured_fields':['full_tokens','numeric_values','context','greedy_tokens','greedy_values'],'replayable':['logits','hidden_states','attentions']})
            new_paths+=count
        m,a=record
        np.testing.assert_array_equal(a['values'],decode_token_samples_to_values(tokenizer,torch.from_numpy(a['tokens']),scale).numpy())
        if phase!='cpd' or position in (0,15,30):
            sample=a['tokens'][0];plain,_=engine.replay(sample[None])
            for t in sorted({position,min(position+1,horizon-1),horizon-1}):parity.append(compare_policy(engine.prefix_state(sample[:t].tolist()).logits,plain[:,t],engine.config,label+f'_{t}'))
            engine.states.clear()
        write_json(out/'progress_extra.json',{'utc':utc(),'phase':phase,'window_id':wid,'role':label,'new_paths':new_paths})
        if phase=='cpd' and block==0 and position==30:transition_selection(out,wid,store,gv,context)
    snapshot=read_snapshot(store.directory,expected_scope=scope)
    write_json(directory/'parity.json',parity);write_json(directory/'timing.json',{'worker_seconds':time.perf_counter()-start,'new_paths':new_paths,'encoder_calls':engine.encoder_calls,'decoder_calls':engine.decoder_calls})
    write_json(directory/'complete.json',{'status':'complete','utc':utc(),'scope':scope,'snapshot_id':snapshot['snapshot_id'],'manifest_sha256':snapshot['manifest_sha256'],
        'ensembles':len(snapshot['records']),'paths':sum(len(a['tokens']) for m,a in snapshot['records']),
        'selection_file':selection_file,'selection_sha256':digest(out/selection_file) if selection_file else None,
        'files':{n:digest(directory/n) for n in ['parity.json','timing.json']}})
    verify_extra(out,wid,phase,horizon);print('EXTRA COMPLETE',phase,wid,new_paths,flush=True)


def supervised(out,label,args):
    from windows_job import WindowsJobProcess
    directory=out/'attempts';directory.mkdir(exist_ok=True);stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');stem=label+'_'+stamp
    env=dict(os.environ,HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false',PYTHONUNBUFFERED='1',GIT_OPTIONAL_LOCKS='0')
    command=[sys.executable,str(Path(__file__).resolve()),'--output',str(out),*args];samples=[];start=time.perf_counter()
    if shutil.disk_usage(out).free<2*1024**3:raise RuntimeError('Need2GiB headroom')
    with (directory/(stem+'.log')).open('wb') as log:
        process=WindowsJobProcess(command,ROOT,env,log,memory_limit=None)
        try:
            low=0
            while process.poll() is None:
                row={'utc':utc(),'elapsed_seconds':time.perf_counter()-start,'peak_job_committed_bytes':process.peak_job_memory(),**memory_usage(),'disk_free_bytes':shutil.disk_usage(out).free};samples.append(row)
                write_json(out/'resources_live.json',{'phase':label,**row});low=low+1 if row['system_free_bytes']<64*1024**2 else 0
                if low>=5 or row['disk_free_bytes']<1024**3:raise RuntimeError('Critical RAM/disk floor; durable objects preserved')
                time.sleep(1)
            code=process.wait()
        finally:
            if process.poll() is None:process.kill();process.wait()
            write_json(directory/(stem+'.json'),{'label':label,'exit_code':process.returncode,'elapsed_seconds':time.perf_counter()-start,'peak_job_committed_bytes':process.peak_job_memory(),'samples':samples});process.close()
    if code:raise RuntimeError(f'{label} failed; stop affected collection, see {stem}.log')


def execute_dense(out):
    verify_freeze(out);cells=load(out/'cell_plan.json');completed=[]
    for index,c in enumerate(cells):
        if (out/'cells'/c['cell_id']/'complete.json').exists():read_block(out,c)
        else:supervised(out,f'dense{index:02d}',['--dense-worker',str(index)])
        if c['block_index']==2:
            v=verify_window(out,c['window_id']);completed.append(v)
            if len(completed)==2:
                write_json(out/'first_two_gate.json',{'status':'passed','utc':utc(),'windows':completed,'different_datasets':len({x['scope']['dataset_id'] for x in cells[:6]})==2})
    write_json(out/'dense_complete.json',{'status':'complete','utc':utc(),'windows':completed,'dense_blocks':18})


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--config',type=Path,default=ROOT/'configs/chronos_discovery/iteration_20261124.json')
    p.add_argument('--prepare',action='store_true');p.add_argument('--dense',action='store_true');p.add_argument('--dense-worker',type=int);p.add_argument('--extra-worker',nargs=2,metavar=('PHASE','WINDOW'));p.add_argument('--extras',choices=['fresh_validation','natural_reference','cpd','cpd_fresh']);p.add_argument('--aux-worker',nargs='+');args=p.parse_args();out=args.output.resolve()
    if args.prepare:prepare(out,args.config)
    elif args.dense_worker is not None:dense_worker(out,args.dense_worker,extended_block=True)
    elif args.extra_worker:extra_worker(out,args.extra_worker[1],args.extra_worker[0])
    elif args.aux_worker:
        from replay_chronos_discovery import replay_worker
        replay_worker(out,*args.aux_worker)
    elif args.dense:execute_dense(out)
    elif args.extras:
        panel=verify_freeze(out);windows=load(out/'cpd_windows.json')['windows'] if args.extras.startswith('cpd') else [w['window_id'] for w in panel['windows']]
        if args.extras=='fresh_validation':windows=sorted({r['window_id'] for r in load(out/'validation_plan.json')['contrasts']})
        for i,wid in enumerate(windows):
            directory=out/args.extras/wid
            if (directory/'complete.json').exists():verify_extra(out,wid,args.extras,64 if args.extras.startswith('cpd') else 32)
            else:supervised(out,f'{args.extras}{i}',['--extra-worker',args.extras,wid])
        write_json(out/(args.extras+'_complete.json'),{'status':'complete','utc':utc(),'windows':windows,'complete_sha256':{w:digest(out/args.extras/w/'complete.json') for w in windows}})
    else:p.error('Select a bounded phase')


if __name__=='__main__':main()
