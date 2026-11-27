import copy
import numpy as np
import pytest
import torch

from test_exploratory import tiny_decoder  # reuse the existing tiny random T5 fixture
from chronos_exploratory import policy_probabilities
from chronos_incremental_collection import sample_group


def test_mixed_conditional_batch_uses_every_rows_full_history(tiny_decoder, monkeypatch):
    _, config, _, _, engine = tiny_decoder
    prefix=[4]; support=[3,5]; state=engine.prefix_state(prefix)
    original_cache=copy.deepcopy(state.cache)
    original=torch.multinomial;probabilities=[]
    def capture(q,*args,**kwargs):
        probabilities.append(q.detach().clone())
        return original(q,*args,**kwargs)
    monkeypatch.setattr(torch,'multinomial',capture)
    paths=sample_group(engine,prefix,support,8,16,torch.Generator().manual_seed(99),16)
    assert np.isin(paths[:,1].numpy(),support).all()
    assert torch.equal(paths[:,0],torch.full((16,),4))
    logits,_=engine.replay(paths)
    assert len(probabilities)==7
    for t,actual in enumerate(probabilities,start=1):
        expected=policy_probabilities(logits[:,t],config)
        if t==1:
            mask=torch.zeros(16,dtype=torch.bool);mask[support]=True
            expected=torch.where(mask,expected,0.)
        torch.testing.assert_close(actual/actual.sum(-1,keepdim=True),
            expected/expected.sum(-1,keepdim=True),atol=1e-6,rtol=1e-4)
    for before,after in zip(original_cache.self_attention_cache.layers,state.cache.self_attention_cache.layers):
        torch.testing.assert_close(before.keys,after.keys,atol=0,rtol=0)


def test_conditional_first_draw_matches_exact_restricted_probability(tiny_decoder):
    _,config,_,_,engine=tiny_decoder
    q=policy_probabilities(engine.prefix_state([4]).logits,config)[0]
    expected=float(q[3]/(q[3]+q[5]))
    paths=sample_group(engine,[4],[3,5],2,4000,torch.Generator().manual_seed(20261126),64)
    actual=float((paths[:,1]==3).float().mean())
    assert abs(actual-expected)<5*np.sqrt(expected*(1-expected)/4000)+.002
    with pytest.raises(ValueError):
        sample_group(engine,[4],[1,3],8,20,torch.Generator().manual_seed(4),8)
