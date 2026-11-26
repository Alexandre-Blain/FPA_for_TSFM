"""Bounded deterministic replay only: SGA inputs and targeted white-box checks.

Never calls a sampling method. Original online hidden tensors were not saved;
retrospective equivalence refers to saved teacher-forced captures, explicitly.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import time
import numpy as np
import pandas as pd

from run_chronos_discovery import engine_for
from run_chronos_local_pilot import load,digest,verify_freeze
from run_chronos_extended_batch import read_block
from run_chronos_microbenchmark import write_json
from chronos_discovery import sga_author_code,uncertainty_features
from ensemble_store import read_object,EnsembleStore


def save_or_check_npz(path,arrays):
    if path.exists():
        with np.load(path) as previous:
            if set(previous.files)!=set(arrays):raise ValueError('Replay field set changed on resume')
            for k,a in arrays.items():np.testing.assert_array_equal(a,previous[k])
        return
    pending=path.with_suffix('.pending')
    with pending.open('wb') as f:np.savez_compressed(f,**arrays);f.flush();os.fsync(f.fileno())
    os.replace(pending,path)


def replay_engine(out,wid,bundle=None):
    if bundle is None:return engine_for(out,wid,32)
    import torch
    from chronos_exploratory import CachedDecoder
    model,tokenizer,mc=bundle
    with np.load(out/'selected_contexts.npz') as f:context=f[wid].copy()
    ids,mask,scale=tokenizer.context_input_transform(torch.from_numpy(context)[None]);engine=CachedDecoder(model,mc,ids,mask);greedy=engine.greedy(32)
    return engine,tokenizer,scale,context,greedy,[]


def sga_replay(out,wid):
    import torch
    from chronos_exploratory import policy_probabilities
    directory=out/'sga_replay'/wid;directory.mkdir(parents=True,exist_ok=True)
    if (directory/'complete.json').exists():
        marker=load(directory/'complete.json')
        if marker['replay_source_sha256']!=digest(Path(__file__)):raise ValueError('SGA replay source changed')
        for name,h in marker['files'].items():
            if digest(directory/name)!=h:raise ValueError('SGA replay outputs changed')
        return
    start=time.perf_counter();engine,tokenizer,scale,context,greedy,parity=engine_for(out,wid,32);scores=[];objects=[]
    seasonal=float(np.mean(abs(context[48:]-context[:-48])))
    for c in sorted([c for c in load(out/'cell_plan.json') if c['window_id']==wid],key=lambda c:c['block_index']):
        _,result,validation=read_block(out,c);manifest,arrays=validation['lookup'][(0,'overlap_direct',None)]
        entropies=[];full_entropy=[]
        for begin in range(0,20,8):
            logits,_=engine.replay(arrays['tokens'][begin:begin+8]);q=policy_probabilities(logits,engine.config).double()
            top=torch.topk(q,20,dim=-1).values.clamp(1e-12,1);top=top/top.sum(-1,keepdim=True)
            entropies.append((-(top*top.log()).sum(-1)).numpy())
            full_entropy.append((-(q*q.clamp_min(1e-300).log()).sum(-1)).numpy())
        e=np.concatenate(entropies);qent=np.concatenate(full_entropy)
        save_or_check_npz(directory/f'block{c["block_index"]}.npz',dict(tokens=arrays['tokens'],values=arrays['values'],top20_entropy=e,q50_entropy=qent))
        scores.append({'window_id':wid,'block':c['block_index'],'source_task_id':manifest['task_id'],
                       **sga_author_code(arrays['values'],e,seasonal),**uncertainty_features(arrays['values'],context)})
        objects.append(manifest['task_id'])
    pd.DataFrame(scores).to_csv(directory/'scores.csv',index=False)
    write_json(directory/'complete.json',{'status':'complete','sampling_calls':0,'new_trajectories':0,'model_reloaded':True,
        'source_objects':objects,'process_id':os.getpid(),'seconds':time.perf_counter()-start,'author_commit':'03d8133912c4e5c813cae084ca5f5358d7e5a206',
        'implementation':'author-code-convention port, H32 numeric q50 policy; not original paper performance reproduction',
        'replay_source_sha256':digest(Path(__file__)),'parity':parity,
        'files':{p.name:digest(p) for p in directory.iterdir() if p.is_file()}})


def tensor_comparison(actual,expected,atol=3e-5,rtol=3e-5):
    if actual.shape!=expected.shape:raise ValueError('Replay tensor shape mismatch')
    error=float(np.max(abs(actual.astype(float)-expected.astype(float))))
    np.testing.assert_allclose(actual,expected,atol=atol,rtol=rtol)
    return {'shape':list(actual.shape),'max_absolute_error':error,'exact':bool(np.array_equal(actual,expected)),'atol':atol,'rtol':rtol}


def whitebox_replay(out,pass_number):
    import torch
    from chronos_decoding import decode_token_samples_to_values
    plan=load(out/'whitebox_plan.json');directory=out/'whitebox';directory.mkdir(exist_ok=True);receipt=directory/f'pass{pass_number}.json'
    if receipt.exists():
        marker=load(receipt)
        if marker['plan_sha256']!=digest(out/'whitebox_plan.json'):raise ValueError('White-box plan changed')
        if marker['replay_source_sha256']!=digest(Path(__file__)):raise ValueError('White-box replay source changed')
        return
    start=time.perf_counter();checks=[];profiles=[];bundle=None
    for case in plan['cases']:
        wid=case['window_id'];engine,tokenizer,scale,context,greedy,parity=replay_engine(out,wid,bundle)
        bundle=(engine.model,tokenizer,engine.config)
        rows=[];source=[]
        for record in case['paths']:
            m,a=read_object(out/record['object_directory']);rows.append(a['tokens'][record['row']]);source.append((m,a,record['row']))
        tokens=np.stack(rows);plain,_=engine.replay(tokens);logits,captured=engine.replay(tokens,capture=True)
        capture_check=tensor_comparison(logits.numpy(),plain.numpy())
        numeric=decode_token_samples_to_values(tokenizer,torch.from_numpy(tokens),scale).numpy()
        for i,(_,a,row) in enumerate(source):np.testing.assert_array_equal(numeric[i],a['values'][row])
        arrays={**captured,'tokens':tokens,'values':numeric,'logits':logits.numpy()};path=directory/(case['name']+'_pass1.npz')
        comparisons={}
        if pass_number==1:
            save_or_check_npz(path,arrays)
        else:
            with np.load(path) as previous:
                if set(previous.files)!=set(arrays):raise ValueError('Reload omitted captured fields')
                for name,value in arrays.items():comparisons[name]=tensor_comparison(value,previous[name])
        # Original captured teacher-forced tensors exist for the sentinel only.
        historical={}
        if case.get('historical_capture_directory'):
            _,old=read_object(out/case['historical_capture_directory'])
            for name,value in old.items():
                if name in arrays:historical[name]=tensor_comparison(arrays[name],value)
            _,static=read_object(out/case['historical_encoder_directory'])
            for name,value in static.items():
                if name.startswith('encoder_') and name in arrays:historical[name]=tensor_comparison(arrays[name],value)
        checks.append({'case':case['name'],'capture_vs_plain_logits':capture_check,'reload_tensor_checks':comparisons,
                       'historical_teacher_forced_checks':historical,'numeric_values_exact':True,'token_paths_exact':True,
                       'online_original_sampling_hidden_equivalence':'unverifiable: original online tensors were not saved',
                       'greedy_parity':parity})
        if case['name']!='historical_sentinel':
            b=case['b'];ref=0;alt=1
            for name,value in captured.items():
                if name.startswith('decoder_hidden_'):
                    distances=np.linalg.norm(value[alt]-value[ref],axis=-1)/np.sqrt(value.shape[-1])
                    family='hidden_RMS';layer=int(name.rsplit('_',1)[1])
                elif name.startswith(('decoder_attention_','cross_attention_')):
                    distances=np.mean(np.sum(abs(value[alt]-value[ref]),axis=-1),axis=0)
                    family='self_attention_L1' if name.startswith('decoder_attention') else 'cross_attention_L1';layer=int(name.rsplit('_',1)[1])
                else:continue
                for t,d in enumerate(distances):profiles.append({'case':case['name'],'window_id':wid,'b':b,'query':t,
                    'relative_query':t-b,'after_forced_token_in_decoder':t>b,'family':family,'layer':layer,'distance':float(d),
                    'absolute_output_difference':float(abs(numeric[alt,t]-numeric[ref,t])),'inference':'descriptive paired paths, not a causal or population test'})
        del engine,captured,arrays,plain,logits
    if pass_number==1:pd.DataFrame(profiles).to_csv(directory/'representation_profiles.csv',index=False)
    write_json(receipt,{'status':'passed','fresh_process_pass':pass_number,'process_id':os.getpid(),'plan_sha256':digest(out/'whitebox_plan.json'),
        'replay_source_sha256':digest(Path(__file__)),'new_trajectories':0,'sampling_calls':0,'seconds':time.perf_counter()-start,
        'checks':checks,'query_alignment':'query b predicts forced token before seeing it; b+1 first post-intervention query',
        'activation_files':{p.name:digest(p) for p in directory.glob('*_pass1.npz')}})
    print('WHITEBOX RELOAD PASS',pass_number,flush=True)


def replay_worker(out,mode,wid=None):
    verify_freeze(out)
    if mode=='sga':sga_replay(out,wid)
    elif mode in ('whitebox1','whitebox2'):whitebox_replay(out,int(mode[-1]))
    else:raise ValueError('Only targeted replay modes are authorized')
