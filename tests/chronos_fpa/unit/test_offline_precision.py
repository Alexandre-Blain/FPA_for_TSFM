import copy

import numpy as np
import pytest

from chronos_distances import energy_distance_v, empirical_w1_by_horizon
from chronos_offline_precision import (
    assert_pool_compatible, bootstrap_distances, counts, distances,
    event_contributions, holm, pool_designs, supports, transform,
    variance_partition, weighted_w1, permutation_distances,
)


def test_fast_energy_and_whole_path_bootstrap_match_protocol():
    rng = np.random.default_rng(12)
    a, b = rng.normal(size=(7, 4)), rng.normal(size=(7, 4))
    ia, ib = rng.integers(7, size=(9, 7)), rng.integers(7, size=(9, 7))
    fast = bootstrap_distances(a, b, ia, ib)
    for i in range(9):
        assert fast['ed'][i] == pytest.approx(energy_distance_v(a[ia[i]], b[ib[i]]), abs=1e-12)
        assert fast['w1'][i] == pytest.approx(empirical_w1_by_horizon(a[ia[i]], b[ib[i]]).mean())
    assert distances([[0], [2]], [[0], [2]])['ed_u'] == pytest.approx(-2)


def test_supports_exclude_forced_coordinate_and_transform_before_comparison():
    for b in range(10):
        s = supports(b)
        assert min(s['full']) == b+1 and max(s['full']) == 31
        assert len(s['relative22']) == len(s['absolute22']) == 22
        assert np.all(s['absolute22'] > b)
    a = np.array([[1, 2, 4], [5, 6, 8]])
    np.testing.assert_allclose(transform(a, 'centered').mean(axis=1), 0, atol=1e-15)
    np.testing.assert_array_equal(transform(a, 'differenced'), [[1, 2], [1, 2]])


def test_weighted_w1_includes_residual_mass_and_batch_resampling():
    assert weighted_w1([0, 10], [.9, .1], [0], [1]) == pytest.approx(1)
    np.testing.assert_allclose(weighted_w1([0, 10], [[.9, .1], [.1, .9]], [0], [[1], [1]]), [1, 9])
    np.testing.assert_allclose(weighted_w1([0, 10], [[.9, .1], [.1, .9]], [0], [1]), [1, 9])
    with pytest.raises(ValueError):
        weighted_w1([0], [.9], [1], [1])


def test_pool_designs_use_distinct_draw_identities_and_independent_n30_pair():
    d = pool_designs()
    for name, indices in d.items():
        assert len(indices) == int(name[1:3]) and len(set(indices)) == len(indices)
    assert not set(d['N30_s0_s1first10']) & set(d['N30_disjointB'])
    assert set(d['N40_s0_s1']) & set(d['N40_s0_s2'])
    m = {'identity': {'sampling_seed': 1, 'prefix': [2]}, 'metadata': {'rng': {'seed': 1, 'stream_id': 'a'}}}
    n = copy.deepcopy(m); n['identity']['sampling_seed'] = 2; n['metadata']['rng'] = {'seed': 2, 'stream_id': 'b'}
    assert_pool_compatible([m, n])
    n['identity']['prefix'] = [3]
    with pytest.raises(ValueError):
        assert_pool_compatible([m, n])


def test_event_identity_reuses_reference_and_residual_has_signed_contribution():
    lhs, c = event_contributions([np.array([[0], [1]]), np.ones((2, 1)), np.zeros((2, 1))], [.5, .25, .25])
    np.testing.assert_allclose(c[:, 0], [.125, -.125])
    np.testing.assert_allclose(lhs, c.sum(axis=0), atol=1e-15)


def test_between_variance_bias_formula_removes_noise_in_known_law():
    # Gaussian means have variance sigma_i^2/n_i; expectation over many experiments.
    rng = np.random.default_rng(15)
    a = rng.normal(size=(16000, 10)); b = rng.normal(size=(16000, 20)) * 2 + 3
    means = np.c_[a.mean(axis=1), b.mean(axis=1)]
    plugin = .25*.75*(means[:, 0]-means[:, 1])**2
    estimated_bias = .25*.75*(a.var(axis=1, ddof=1)/10 + b.var(axis=1, ddof=1)/20)
    assert np.mean(plugin-estimated_bias) == pytest.approx(.25*.75*9, rel=.015)
    g = [np.array([[-1.], [1.]]), np.array([[-1.], [1.]])]
    v = variance_partition(g, [.5, .5])
    assert v['within'][0] == 2 and v['between_plugin'][0] == 0
    assert v['between_corrected'][0] == -.5  # never clip away this diagnostic


def test_holm_and_frequency_counts_known_answers():
    np.testing.assert_allclose(holm([.01, .04, .03]), [.03, .06, .06])
    np.testing.assert_allclose(counts([[0, 0, 2]], 3), [[2/3, 0, 1/3]])


def test_whole_path_permutations_have_plus_one_and_tie_conventions():
    zeros = np.zeros((8, 3))
    p = permutation_distances(zeros, zeros, 39, np.random.default_rng(2))
    assert p == {'p_w1': 1, 'p_ed': 1}
    p = permutation_distances(zeros, zeros+10, 39, np.random.default_rng(2))
    assert p == {'p_w1': .025, 'p_ed': .025}
