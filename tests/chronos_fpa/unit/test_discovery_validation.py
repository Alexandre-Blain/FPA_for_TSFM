import numpy as np
import pytest
from review_chronos_discovery import wilson,event_permutation,holm,bootstrap_gap


def test_binary_path_permutation_agrees_with_small_exact_case():
    # Four whole paths, two successes: 2 of the 6 assignments are as extreme.
    p=event_permutation([1,1],[0,0],seed=41,reps=49999)
    assert p==pytest.approx(1/3,abs=.015)
    assert event_permutation([0,0],[0,0],seed=2)==1


def test_holm_and_zero_event_uncertainty():
    np.testing.assert_allclose(holm([.01,.04,.03]),[.03,.06,.06])
    lo,hi=wilson(0,120)
    assert lo==pytest.approx(0,abs=1e-12)
    assert .025<hi<.035


def test_bootstrap_keeps_an_identically_reused_path_sample_identical():
    x=np.tile([0.,1.],60)
    lo,hi=bootstrap_gap(x,x,'same-prefix','same-prefix')
    assert lo==hi==0


def test_fresh_consequence_analysis_distinguishes_shift_from_decay(tmp_path,monkeypatch):
    import json
    import review_chronos_discovery as review
    context=np.tile([-1.,1.],256).astype(np.float32)
    records=[];windows=[];plans=[];contrasts=[]
    for wid in ['a','b']:
        windows.append({'window_id':wid,'dataset_id':'synthetic','series_id':wid,'context_iqr':2.,'lag1':.5})
        contrasts.append({'window_id':wid,'dataset':'synthetic','series':wid,'b':0,'token':101,'selection':'random_control',
            'validation_outcome':2,'signed_event_gap':1.,'q50':.2})
        plans.extend({'window_id':wid,'cell_id':wid+str(block),'block_index':block} for block in range(3))
    (tmp_path/'validation_plan.json').write_text(json.dumps({'contrasts':contrasts}))
    (tmp_path/'cell_plan.json').write_text(json.dumps(plans))
    def snapshot(out,wid,phase,horizon):
        objects=[]
        for role,token,value in [('reference',100,1.),('null',100,1.),('alternative',101,3.)]:
            objects.append(({'task_id':wid+role,'identity':{'position':0,'role':role,'token':token}},
                {'context':context,'greedy_values':np.ones(32),'values':np.full((120,32),value)}))
        return {},{'records':objects}
    def block(out,plan):
        lookup={}
        for role,token,value in [('reference',100,1.),('alternative',101,3.)]:lookup[(0,role,token)]=({}, {'values':np.full((20,32),value)})
        result={'greedy_tokens':[100]*32,'forks':[]}
        return {},result,{'lookup':lookup}
    monkeypatch.setattr(review,'verify_freeze',lambda out:{'windows':windows})
    monkeypatch.setattr(review,'verify_extra',snapshot);monkeypatch.setattr(review,'read_block',block)
    rows=review.fresh_results(tmp_path,tmp_path)
    assert len(rows)==2
    for row in rows:
        assert row['fresh_gap']==1 and row['holdout40_gap']==1
        assert row['persistent_event_residual']==0
        assert row['ar1_event_residual']==1
        assert row['W1_relative22_iqr']==pytest.approx(1)
        assert row['reference_wilson_hi']>0 and row['holm']<.01
