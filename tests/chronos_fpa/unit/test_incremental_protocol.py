import json
import importlib.util
from pathlib import Path

import numpy as np

from chronos_incremental import first_token_partition,first_deviation_partition
from chronos_incremental_h2 import allocation_plan,cost_key
from chronos_incremental_h2 import collect_h2
from chronos_incremental_collection import seed_for


def test_allocation_is_nested_exhaustive_and_pilot_cost_is_not_free():
    forks=[{'greedy':10,'probabilities':{10:.6,11:.25,12:.1,13:.05}}]*5
    partitions={'first_token':first_token_partition(forks),
                'first_deviation':first_deviation_partition(forks)}
    costs={cost_key(g):1. for gs in partitions.values() for g in gs};costs['natural']=1.
    pilot=[np.zeros((4,4)) for _ in partitions['first_deviation']]
    plans=allocation_plan(partitions,costs,pilot,65.,[60,120,240])
    by_method={}
    for p in plans['plans']:
        by_method.setdefault(p['method'],[]).append(p)
        if p['method'] in ('stratum_mixture_IS','first_deviation_neyman_cost'):
            assert p['pilot_seconds_charged']==65.
            assert p['feasible']==(p['anchor']!=60)
        else:assert p['pilot_seconds_charged']==0
        if p['feasible'] and 'counts' in p:
            assert min(p['counts'])>=2
            assert sum(p['counts'])+p['pilot_seconds_charged']<=p['anchor']
    for rows in by_method.values():
        counts=[np.array(p['counts']) for p in rows if p['feasible'] and 'counts' in p]
        assert all((b>=a).all() for a,b in zip(counts,counts[1:]))
    w=np.array([g['weight'] for g in partitions['first_deviation']])
    assert (np.array(plans['importance_proposal'])>=.5*w).all()


def test_durable_windows_publication_retries_same_candidate(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[3]
    spec=importlib.util.spec_from_file_location('campaign_driver',root/'scripts/runs/run_chronos_incremental.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original=module.os.replace;calls=[]
    def briefly_locked(source,destination):
        calls.append(Path(source).read_bytes())
        if len(calls)<3:raise PermissionError('simulated Windows share lock')
        return original(source,destination)
    monkeypatch.setattr(module.os,'replace',briefly_locked)
    monkeypatch.setattr(module.time,'sleep',lambda _:None)
    target=tmp_path/'heartbeat.json';target.write_text('{}')
    module.save(target,{'complete':True})
    assert json.loads(target.read_text())=={'complete':True}
    assert len(calls)==3 and calls[0]==calls[1]==calls[2]


def test_h2_mock_full_collection_resume_and_independent_reference(tmp_path):
    """Known iid categorical law, all production paths drawn anew by stream.

    The fake costs are bookkeeping fixtures, never real-model benchmarks.
    """
    class Collector:
        directory=tmp_path/'H2'/'fake_unique_id'
        window={'window_id':'fake_unique_id','dataset_id':'synthetic','series_id':'A','replicated10':True}
        forks=[{'greedy':10,'probabilities':{10:.6,11:.25,12:.1,13:.05}}]*5
        context=np.tile([0.,1.],256);greedy_values=np.ones(32);setup_seconds=.1
        config={'root_seed':20261126,'h2_allocation_pilot_per_stratum':4,
            'h2_budget_anchors':[60,120,240], 'h2_minimum_per_stratum':2,
            'h2_final_repetitions':2,'h2_matched_natural_cap':4000,'batch_size':8,
            'h2_reference_blocks':[1000,1000],
            'h2_methods':['MC','first_token_proportional','first_deviation_uniform',
                'first_deviation_proportional','first_deviation_neyman_cost','stratum_mixture_IS']}
        def __init__(self):
            self.directory.mkdir(parents=True)
            groups=first_token_partition(self.forks)+first_deviation_partition(self.forks)
            self.config['h2_cost_model']={cost_key(g):.01 for g in groups}
            self.config['h2_cost_model']['natural']=.01
            self.saved={};self.new_draws=0
        def draw(self,label,prefix,support,count,role,position,token=None,block=0):
            key=(label,tuple(prefix),tuple(support),count,role,position,token,block)
            if key in self.saved:return self.saved[key]
            self.new_draws+=1
            rng=np.random.default_rng(seed_for(20261126,str(key)))
            tokens=rng.choice([10,11,12,13],size=(count,32),p=[.6,.25,.1,.05])
            tokens[:,:len(prefix)]=np.tile(prefix,(count,1))
            if support:
                q=np.array([{10:.6,11:.25,12:.1,13:.05}[t] for t in support]);q/=q.sum()
                tokens[:,len(prefix)]=rng.choice(support,count,p=q)
            values=np.choose(tokens-10,[1.,-1.,3.,0.])
            m={'task_id':label,'metadata':{'generation_seconds':count*.01},
                'identity':{'label':label,'role':role,'prefix':list(prefix),
                    'first_token_support':list(support),'position':position,'sample_count':count}}
            self.saved[key]=(m,{'tokens':tokens,'values':values,
                'context':self.context,'greedy_values':self.greedy_values});return self.saved[key]
    collector=Collector();result=collect_h2(collector)
    assert result['h2_reference_N']==2000 and result['h2_repetitions']==2
    d=json.loads((collector.directory/'event_estimates.json').read_text())
    assert d['reference_block_N']==[1000,1000]
    assert all(np.isfinite(r['probability']).all() for r in d['rows'] if r['feasible'])
    assert {r['rep'] for r in d['rows']}=={0,1}
    assert all(len(r['counts']) in (4,11) and min(r['counts'])>=2
        for r in d['rows'] if r['feasible'] and r['method'].startswith('first_'))
    count=collector.new_draws
    collect_h2(collector)
    assert collector.new_draws==count  # exact raw draws reused, reference included
    (collector.directory/'forks.json').write_text(json.dumps(collector.forks))
    from audit_chronos_incremental import audit_h2
    checked=audit_h2(tmp_path,collector.window,{},
        {'records':list(collector.saved.values())},collector.config)
    assert checked>0  # reconstructed production counts, IS choices, costs, refs
