import numpy as np
import pytest
from chronos_discovery import scenario_events,behaviour_codes,risk_ranking,dtw_distance,sga_author_code,choose_validation


def test_target_free_events_have_known_thresholds():
    c=np.tile([-1.,1.],256);g=np.zeros(32);a=np.vstack([np.ones(32)*3,np.ones(32)*-3,np.zeros(32)])
    e=scenario_events(a,c,g)
    assert e[:,:2].tolist()==[[False,False],[False,True],[False,False]]
    assert e[:,4:6].tolist()==[[True,False],[False,True],[False,False]]
    assert len(set(behaviour_codes(a,c)))==3


def test_risk_ranking_oracle_random_ties_and_wrong_order():
    y=[1,2,4,8]
    assert risk_ranking(y,y)['neaurc']==pytest.approx(0)
    assert risk_ranking([1,1,1,1],y)['neaurc']==pytest.approx(1)
    assert risk_ranking([-1,-2,-4,-8],y)['neaurc']>1
    assert np.isnan(risk_ranking(y,[1,1,1,1])['neaurc'])


def test_sga_known_chain_merge_and_entropy_weights():
    # identical paths merge into two slices. Root=1, then3+.1, then3+.31.
    a=np.zeros((3,8));e=np.ones_like(a)*2
    d=sga_author_code(a,e,1)
    assert d['graph_nodes']==3 and d['graph_edges']==2
    assert d['sga_author_code']==pytest.approx(7.41)
    assert dtw_distance([0,1],[0,2])==pytest.approx(1)
    b=np.vstack([np.zeros(8),np.ones(8)*10])
    assert sga_author_code(b,np.zeros_like(b),1)['graph_nodes']==5


def test_validation_allocation_is_bounded_and_controls_are_distinct():
    rows=[dict(window_id=f'{d}{w}',dataset=d,b=b,token=100+b,event=0,event_gap=b,
               persistent_score=b,transient_score=4-b,sparse_miss_score=b) for d in ['a','b'] for w in range(3) for b in range(5)]
    x=choose_validation(rows)
    assert x==choose_validation(list(reversed(rows)))
    assert len(x)==8 and sum(r['selection']=='random_control' for r in x)==2
    assert len({(r['window_id'],r['b'],r['token']) for r in x})==8


def test_first_deviation_partition_has_known_disjoint_masses():
    from analyze_chronos_discovery import first_deviation_groups
    lookup={};forks=[]
    for b in range(10):
        forks.append(dict(b=b,greedy_token=10,selected_tokens=[10,11],selected_weights=[.8,.1],residual_mass=.1))
        for role,t in [('reference',10),('alternative',11),('residual',None)]:lookup[(b,role,t)]=({}, {'values':np.zeros((20,32))})
    cell={'result':{'forks':forks,'greedy_tokens':[10]*32},'validation':{'lookup':lookup}}
    gs=first_deviation_groups(cell)
    assert len(gs)==21
    assert gs[0][0]==pytest.approx(.1) and gs[2][0]==pytest.approx(.08)
    assert gs[-1][0]==pytest.approx(.8**10)
    assert sum(w for w,_ in gs)==pytest.approx(1)


def test_validation_ceiling_and_required_controls():
    from run_chronos_discovery import validate_allocation
    rows=[dict(window_id=str(i//2),b=i,token=100+i,selection='random_control' if i<2 else 'scientific') for i in range(8)]
    validate_allocation(rows)
    with pytest.raises(ValueError):validate_allocation(rows+[dict(rows[0],token=999)])
    with pytest.raises(ValueError):validate_allocation([dict(r,selection='scientific') for r in rows])
    with pytest.raises(ValueError):validate_allocation([dict(r,window_id='same') for r in rows])
