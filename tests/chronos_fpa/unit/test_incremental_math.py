import itertools
import numpy as np
import pytest

from chronos_incremental import (future_events, checked_probabilities,
    first_token_partition, first_deviation_partition, validate_partition,
    stratified_estimate, importance_estimate, budget_allocation, decision_variance)


def test_first_deviation_exact_enumeration_covers_once_with_correct_masses():
    q = {10: .6, 11: .3, 12: .1}
    forks = [{'greedy': 10, 'probabilities': q} for _ in range(5)]
    groups = first_deviation_partition(forks)
    observed = np.zeros(len(groups))
    for path in itertools.product(q, repeat=5):
        matches = [i for i, g in enumerate(groups)
            if list(path[:len(g['prefix'])]) == g['prefix']
            and (not g['support'] or path[g['position']] in g['support'])]
        assert len(matches) == 1
        observed[matches[0]] += np.prod([q[t] for t in path])
    np.testing.assert_allclose(observed, [g['weight'] for g in groups], rtol=1e-13)
    assert len(groups) == 11
    first = first_token_partition(forks)
    assert sum(g['weight'] for g in first) == pytest.approx(1)
    with pytest.raises(ValueError):
        validate_partition(groups + [dict(groups[0], weight=0.)])
    with pytest.raises(ValueError):
        checked_probabilities({10: 1., 11: float('nan')})


def test_float32_softmax_roundoff_preserves_complete_relative_probability_law():
    # Real preflight diagnostic: sum=.999999780440703 (2.20e-7 error).
    relative={10:.6*(1-2.3e-7),11:.3*(1-2.3e-7),12:.1*(1-2.3e-7)}
    q=checked_probabilities(relative)
    assert sum(q.values())==pytest.approx(1.,abs=1e-15)
    assert q[10]/q[11]==pytest.approx(relative[10]/relative[11],abs=1e-15)
    assert set(q)==set(relative)
    with pytest.raises(ValueError):checked_probabilities({10:.6001,11:.3,12:.1})


def test_stratified_known_probability_variance_and_unobserved_stratum_rejected():
    a = np.array([[0], [1]])
    b = np.ones((2, 1))
    r = stratified_estimate([a, b], [.8, .2])
    assert r['probability'][0] == pytest.approx(.6)
    assert r['variance'][0] == pytest.approx(.8**2*.5/2)
    assert r['lo'][0] <= .6 <= r['hi'][0]
    with pytest.raises(ValueError):
        stratified_estimate([a, np.empty((0, 1))], [.8, .2])


def test_importance_stratum_mixture_exact_expectation_and_variance():
    # Proposal draws each of two strata equally. E occurs only in stratum1;
    # contributions are0 or .2/.5=.4. An exact balanced sample has mean .2.
    r = importance_estimate([0, 1], [[0], [1]], [.8, .2], [.5, .5])
    assert r['probability'][0] == pytest.approx(.2)
    assert r['variance'][0] == pytest.approx(.04)
    with pytest.raises(ValueError):
        importance_estimate([0, 0], [[0], [0]], [.8, .2], [1., 0.])


def test_allocation_budget_minimum_and_cost_adjusted_neyman():
    assert budget_allocation([.5, .5], [1., 3.], 7., 'uniform') is None
    n = budget_allocation([.5, .5], [1., 1.], 100., 'neyman_cost', [.01, .25])
    assert sum(n) == 100 and n[1] > 4*n[0]
    for method in ['uniform', 'proportional', 'neyman_cost']:
        n = budget_allocation([.99, .01], [1., 3.], 100., method, [.2, .2])
        assert min(n) >= 2 and n @ np.array([1., 3.]) <= 100.


def test_absolute_event_thresholds_and_near_zero_direction():
    context = np.tile([-1., 1.], 256)  # last1, IQR2
    paths = np.ones((3, 32)); paths[0, 8] = -1; paths[1, 31] = 3
    greedy = np.ones(32)
    e = future_events(paths, context, greedy)
    assert e[0, 0] and e[1, 1] and not e[2].any()
    paths[0, :8] = -10
    assert not future_events(paths[2:], context, greedy)[0, 0]
    paths[2, 31] = 1.09
    assert not future_events(paths[2:], context, greedy)[0, 3]
    paths[2, 31] = 1.11
    assert future_events(paths[2:], context, greedy)[0, 3]


def test_law_of_total_variance_retains_residual_between_token_variation():
    context = np.tile([-1., 1.], 256)
    q = {10: .5, 11: .2, 12: .3}
    def group(tokens):
        z = np.array([{10: 0., 11: -1., 12: 2.}[t] for t in tokens])
        return {'tokens': np.repeat(np.array(tokens)[:, None], 32, 1),
                'values': np.repeat((1+2*z)[:, None], 32, 1)}
    # Each residual block has exact token frequencies .4/.6.
    groups = [group([10]*40), group(([11]*8+[12]*12)*2)]
    r = decision_variance(groups, [.5, .5], q, 0, context)
    # E[z]=.4; E[z²]=1.4 => between-token=1.24, within-token=0.
    assert r['between_token_crossblock'] == pytest.approx(1.24)
    assert r['within_token_crossblock'] == pytest.approx(0., abs=1e-12)
    assert r['between_group_corrected'] < r['between_token_crossblock']


def test_estimators_unbiased_in_exact_nontrivial_bernoulli_sample_spaces():
    # q=(.8,.2), conditional event probabilities (.1,.8), p=.24.
    # Exactly enumerate independent samples, no random tolerance or simulation.
    expected_strat=expected_strat_variance=0.
    for outcomes in itertools.product([0,1],repeat=4):
        probability=np.prod([(.1 if x else .9) for x in outcomes[:2]])*np.prod([(.8 if x else .2) for x in outcomes[2:]])
        r=stratified_estimate([np.array(outcomes[:2])[:,None],np.array(outcomes[2:])[:,None]],[.8,.2])
        expected_strat+=probability*r['probability'][0]
        expected_strat_variance+=probability*r['variance'][0]
    assert expected_strat==pytest.approx(.24)
    assert expected_strat_variance==pytest.approx(.032)
    expected_IS=expected_IS_variance=0.
    states=[(0,0,.5*.9),(0,1,.5*.1),(1,0,.5*.2),(1,1,.5*.8)]
    for first,second in itertools.product(states,repeat=2):
        probability=first[2]*second[2]
        r=importance_estimate([first[0],second[0]],[[first[1]],[second[1]]],[.8,.2],[.5,.5])
        expected_IS+=probability*r['probability'][0]
        expected_IS_variance+=probability*r['variance'][0]
    assert expected_IS==pytest.approx(.24)
    assert expected_IS_variance==pytest.approx(.0672)
    r=importance_estimate([0]*100,[[1]]*100,[.8,.2],[.5,.5])
    assert r['probability'][0]==pytest.approx(1.6)  # do not bias TaskA by clipping
    assert 0<=r['lo'][0]<=r['hi'][0]<=1


def test_residual_token_variance_separates_nonzero_within_component():
    context=np.tile([-1.,1.],256)
    tokens=([10]*10+[11]*10)*2
    z=np.tile([-1.,1.]*5+[1.,3.]*5,2)
    group={'tokens':np.repeat(np.array(tokens)[:,None],32,axis=1),
        'values':np.repeat((1+2*z)[:,None],32,axis=1)}
    result=decision_variance([group],[1.],{10:.5,11:.5},0,context)
    assert result['between_group_corrected']==pytest.approx(0.)
    assert result['between_token_crossblock']==pytest.approx(1.)
    assert result['within_token_crossblock']==pytest.approx(1.)
