"""Additive campaign collection using the existing decoder and immutable store."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import torch

from chronos_exploratory import CachedDecoder, fork_cache, policy_probabilities
from chronos_decoding import decode_token_samples_to_values, _mask_to_chronos_value_tokens
from chronos_discovery import sga_author_code
from chronos_incremental import checked_probabilities, sparse_tokens, first_token_partition, first_deviation_partition
from chronos_incremental_features import h1_features
from ensemble_store import EnsembleStore, read_snapshot, task_id
from results_io import save_json


def seed_for(root, label):
    return int(hashlib.sha256(f'{root}:{label}'.encode()).hexdigest()[:16],16)


@torch.no_grad()
def sample_group(engine, prefix, support, horizon, count, generator, batch_size):
    """Condition only the first draw on an exhaustive declared token subset.

    Mixed first tokens remain in the same batch; subsequent logits condition on
    each row's complete history. This is the existing CachedDecoder.sample loop
    with one first-step support mask, not an importance proposal or new policy.
    """
    prefix=tuple(map(int,prefix));support=tuple(map(int,support))
    if not support:
        return engine.sample(prefix,horizon,count,generator,batch_size=batch_size)
    if len(support)==1:
        return engine.sample(prefix+(support[0],),horizon,count,generator,batch_size=batch_size)
    if len(set(support))!=len(support) or len(prefix)>=horizon or count<=0 or batch_size<=0:
        raise ValueError('Invalid conditional support/count')
    state=engine.prefix_state(prefix);support_mask=torch.zeros(engine.config.n_tokens,dtype=torch.bool,device=engine.device)
    support_mask[list(support)]=True
    root_q=policy_probabilities(state.logits,engine.config)
    if not bool((root_q[:,list(support)]>0).all()):
        raise ValueError('Conditional subset must lie inside q50 support')
    batches=[]
    for begin in range(0,count,batch_size):
        n=min(batch_size,count-begin);cache=fork_cache(state.cache,n)
        logits=state.logits.expand(n,-1)
        paths=torch.tensor(prefix,dtype=torch.long,device=engine.device).repeat(n,1)
        for step in range(len(prefix),horizon):
            q=policy_probabilities(logits,engine.config)
            if step==len(prefix):
                q=torch.where(support_mask,q,0.)
                # torch.multinomial accepts relative weights. No floating-point
                # renormalization or truncation is applied to later steps.
            token=torch.multinomial(q,1,generator=generator)
            paths=torch.cat((paths,token),dim=1)
            if step+1<horizon:
                result=engine.model(encoder_outputs=engine._encoder_batch(n),
                    attention_mask=engine.attention_mask.expand(n,-1),decoder_input_ids=token,
                    past_key_values=cache,use_cache=True,return_dict=True)
                cache,logits=result.past_key_values,result.logits[:,-1]
                engine.decoder_calls+=1
        batches.append(paths.cpu())
    return torch.cat(batches)


def fork_descriptors(engine, tokenizer, scale, greedy):
    rows=[];prefix_mass=1.
    for b in range(10):
        logits=engine.prefix_state(greedy[:b].tolist()).logits
        q_raw=policy_probabilities(logits,engine.config)[0].double().numpy()
        q=checked_probabilities({int(t):q_raw[t] for t in np.where(q_raw>0)[0]})
        p=torch.softmax(_mask_to_chronos_value_tokens(logits,engine.config),dim=-1)[0].double().numpy()
        g=int(greedy[b]);selected=sparse_tokens(q,g)
        residual=sorted(set(q)-set(selected));sorted_q=sorted(q.values(),reverse=True)
        token_values=decode_token_samples_to_values(tokenizer,torch.tensor(selected)[:,None],scale).numpy()[:,0]
        rows.append({'b':b,'greedy':g,'probabilities':{str(t):q[t] for t in q},
            'raw_float32_q50_mass':float(q_raw.sum()),
            'p_sel_selected':{str(t):float(p[t]) for t in selected},
            'selected_tokens':selected,'residual_support':residual,'residual_mass':sum(q[t] for t in residual),
            'entropy_q50':float(-sum(v*np.log(v) for v in q.values())),
            'entropy_p_sel':float(-sum(p[p>0]*np.log(p[p>0]))),
            'margin':float(sorted_q[0]-(sorted_q[1] if len(sorted_q)>1 else 0)),
            'greedy_prefix_mass':prefix_mass,'candidate_values':{str(t):float(v) for t,v in zip(selected,token_values)}})
        prefix_mass*=q[g]
    return rows


class WindowCollector:
    def __init__(self, run, window, model_bundle, config, phase, source_id):
        model,tokenizer,mc=model_bundle
        self.run,self.window,self.config=Path(run),window,config
        self.phase,self.tokenizer=phase,tokenizer
        self.directory=self.run/phase/window['window_id'];self.directory.mkdir(parents=True,exist_ok=True)
        with np.load(self.run/'contexts.npz') as f:self.context=f[window['window_id']].copy()
        if hashlib.sha256(self.context.tobytes()).hexdigest()!=window['context_sha256']:
            raise ValueError('Context identity changed')
        start=time.perf_counter();ids,mask,self.scale=tokenizer.context_input_transform(torch.from_numpy(self.context)[None])
        self.engine=CachedDecoder(model,mc,ids,mask);self.greedy=self.engine.greedy(32)
        self.greedy_values=decode_token_samples_to_values(tokenizer,self.greedy[None],self.scale).numpy()[0]
        self.setup_seconds=time.perf_counter()-start
        from run_chronos_local_pilot import compare_policy
        logits,_=self.engine.replay(self.greedy[None])
        self.parity=[compare_policy(self.engine.prefix_state(self.greedy[:t].tolist()).logits,logits[:,t],mc,f'greedy{t}') for t in (0,4,9,31)]
        self.forks=fork_descriptors(self.engine,tokenizer,self.scale,self.greedy)
        self.setup_seconds=time.perf_counter()-start  # includes replay/parity and descriptors
        self.scope={'dataset_id':window['dataset_id'],'series_id':window['series_id'],
            'window_id':window['window_id'],'forecast_origin':window['forecast_origin'],
            'context_sha256':window['context_sha256'],'model_revision':config['model_revision'],
            'source_freeze_id':source_id,'phase':phase,'policy':'q50_valid_mask_T1_topk50_ties_topp1'}
        self.store=EnsembleStore(self.directory/'ensembles',scope=self.scope)

    def draw(self, label, prefix, support, count, role, position, token=None, block=0, sga=False):
        identity={**self.scope,'label':label,'prefix':list(prefix),'first_token_support':list(support),
            'sample_count':int(count),'role':role,'position':int(position),'token':token,'block':int(block)}
        old=self.store.get(identity)
        if old is not None:return old
        seed=seed_for(self.config['root_seed'],task_id(identity));generator=torch.Generator(device=self.engine.device).manual_seed(seed)
        started=time.perf_counter()
        tokens=sample_group(self.engine,prefix,support,32,count,generator,self.config['batch_size'])
        values=decode_token_samples_to_values(self.tokenizer,tokens,self.scale).numpy()
        generation_seconds=time.perf_counter()-started
        arrays={'tokens':tokens.numpy().astype(np.int64),'values':values,'context':self.context,
                'greedy_tokens':self.greedy.numpy(),'greedy_values':self.greedy_values}
        metadata={'generation_seconds':generation_seconds,'rng':{'root_seed':self.config['root_seed'],
            'seed':seed,'stream_id':hashlib.sha256(f'{self.config["root_seed"]}:{task_id(identity)}'.encode()).hexdigest()},
            'sampling_policy':self.scope['policy'],'first_token_law':'q50 restricted to declared support; subsequent draws unmodified q50',
            'batch_size':self.config['batch_size'],'tokenizer_scale':self.scale.numpy().tolist()}
        if sga:
            start=time.perf_counter();entropies=[]
            for begin in range(0,count,8):
                logits,_=self.engine.replay(tokens[begin:begin+8]);q=policy_probabilities(logits,self.engine.config).double()
                top=torch.topk(q,20,dim=-1).values.clamp(1e-12,1);top/=top.sum(-1,keepdim=True)
                entropies.append((-(top*top.log()).sum(-1)).numpy())
            e=np.concatenate(entropies);metadata['sga_replay_seconds']=time.perf_counter()-start
            arrays['top20_entropy']=e;start=time.perf_counter()
            graph=sga_author_code(values,e,self.window['seasonal_scale'])
            metadata['sga_graph_seconds']=time.perf_counter()-start;metadata['sga_score']=graph['sga_author_code']
            metadata['sga_graph']=graph
        self.validate(identity,arrays)
        self.store.put(identity,arrays,metadata)
        return self.store.get(identity)

    def validate(self,identity,a):
        prefix=identity['prefix'];tokens=a['tokens']
        if len(tokens)!=identity['sample_count'] or tokens.shape[1]!=32:
            raise ValueError('Incomplete path shape')
        np.testing.assert_array_equal(tokens[:,:len(prefix)],np.tile(prefix,(len(tokens),1)))
        if identity['first_token_support'] and not np.isin(tokens[:,len(prefix)],identity['first_token_support']).all():
            raise ValueError('Conditional residual support violated')
        np.testing.assert_array_equal(decode_token_samples_to_values(self.tokenizer,torch.from_numpy(tokens),self.scale).numpy(),a['values'])

    def collect_h1(self):
        for block in range(3):self.draw(f'natural{block}',[],[],20,'natural',0,block=block,sga=True)
        for f in (f for f in self.forks if f['b'] in (0,4,9)):
            b=f['b'];prefix=self.greedy[:b].tolist()
            for token in f['selected_tokens']:
                for block in range(2):self.draw(f'b{b}_token{token}_block{block}',prefix,[token],20,'conditional',b,token,block)
            if f['residual_mass']>0:
                for block in range(2):self.draw(f'b{b}_residual_block{block}',prefix,f['residual_support'],20,'residual',b,block=block)
            self.draw(f'b{b}_null',prefix,[f['greedy']],20,'null',b,f['greedy'])
        if self.phase!='pilot' and self.window.get('matched_cost_member') and self.config.get('h1_matched_extra_N'):
            self.draw('matched_extra_natural',[],[],self.config['h1_matched_extra_N'],'matched_natural',0)
        snapshot=read_snapshot(self.store.directory,expected_scope=self.scope)
        feature_start=time.perf_counter()
        features=h1_features(self.context,self.greedy_values,self.forks,snapshot['records'],self.window['lag'])
        save_json(self.directory/'feature_cost.json',{'all_feature_seconds':time.perf_counter()-feature_start,
            'accounting':'conservatively charge full feature extraction to FPA increment; natural/context summaries also computed here'})
        save_json(self.directory/'features.json',features)
        return features

    def technical_profile(self):
        profiles=[]
        for batch in (8,16,32):
            old=self.config['batch_size'];self.config['batch_size']=batch
            for kind,prefix,support in [('natural',[],[]),
                ('residual',[],first_token_partition(self.forks)[-1]['support'])]:
                manifest,arrays=self.draw(f'timing_batch{batch}_{kind}',prefix,support,64,'timing',0)
                from run_chronos_local_pilot import compare_policy
                logits,_=self.engine.replay(arrays['tokens'][:2])
                parity=[]
                for row in range(2):
                    for t in (0,4,9,31):
                        parity.append(compare_policy(self.engine.prefix_state(arrays['tokens'][row,:t].tolist()).logits,logits[row:row+1,t],self.engine.config,f'{kind}_batch{batch}_row{row}_t{t}'))
                profiles.append({'batch_size':batch,'kind':kind,'count':64,
                    'seconds':manifest['metadata']['generation_seconds'],'parity':parity})
            self.config['batch_size']=old
        save_json(self.directory/'technical_profile.json',profiles)
        return profiles

    def finish(self, extra=None):
        snapshot=read_snapshot(self.store.directory,expected_scope=self.scope)
        save_json(self.directory/'forks.json',self.forks)
        paths=sum(len(a['tokens']) for _,a in snapshot['records'])
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.directory.iterdir()
               if p.is_file() and p.name!='complete.json'}
        save_json(self.directory/'complete.json',{'status':'complete','scope':self.scope,
            'snapshot_id':snapshot['snapshot_id'],'manifest_sha256':snapshot['manifest_sha256'],
            'object_ids':snapshot['object_ids'],'ensembles':len(snapshot['records']),'paths':paths,
            'setup_seconds':self.setup_seconds,'parity':self.parity,'files':files,**(extra or {})})
        return paths
