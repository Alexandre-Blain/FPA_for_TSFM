"""Independent, hand-calculated oracles for the two Paper 1 estimands."""
import numpy as np
import pytest

from chronos_distances import compare_fork_samples, empirical_w1_by_horizon, energy_distance_v


def test_empirical_w1_constant_shift_and_per_horizon_sorting():
    a = np.array([[0., 12.], [2., 10.], [4., 11.]])
    b = np.array([[7., 14.], [3., 15.], [5., 13.]])
    np.testing.assert_allclose(empirical_w1_by_horizon(a, b), [3., 3.])


def test_w1_unequal_counts_integrates_empirical_cdfs_exactly():
    # Three nonzero common-grid intervals each contribute 1/6, 1/6, 1/3.
    assert empirical_w1_by_horizon([[0.], [2.]], [[0.], [1.], [3.]])[0] == pytest.approx(2 / 3)
    assert empirical_w1_by_horizon([[0.], [2.]], [[1.]])[0] == pytest.approx(1.)


def test_energy_identical_sets_including_permutations_are_zero():
    a = np.array([[1., 3.], [-1., 2.], [4., 0.]])
    assert energy_distance_v(a, a[::-1]) == pytest.approx(0., abs=1e-14)


def test_same_marginals_different_temporal_pairings():
    a = [[-1., -1.], [1., 1.]]
    b = [[-1., 1.], [1., -1.]]
    np.testing.assert_array_equal(empirical_w1_by_horizon(a, b), [0., 0.])
    assert energy_distance_v(a, b) == pytest.approx(2 * np.sqrt(2) - 2)


def test_deterministic_energy_is_twice_rms_path_distance_no_square_root():
    assert energy_distance_v([[0., 0.]], [[3., 4.]]) == pytest.approx(10 / np.sqrt(2))


def test_energy_supports_unequal_counts_and_includes_diagonal_pairs():
    assert energy_distance_v([[0.], [0.]], [[0.], [1.], [2.]]) == pytest.approx(10 / 9)


def test_independent_equal_law_realizations_are_not_assumed_zero():
    # Both are possible independent samples from Bernoulli(1/2).
    assert energy_distance_v([[0.], [0.]], [[0.], [1.]]) == pytest.approx(.5)
    assert empirical_w1_by_horizon([[0.], [0.]], [[0.], [1.]])[0] == pytest.approx(.5)


@pytest.mark.parametrize("position", [0, 1, 2])
def test_forced_coordinate_and_prefix_are_excluded(position):
    a = np.zeros((2, 4))
    a[:, position + 1:] = np.arange(2)[:, None]
    b = a.copy()
    b[:, position] = 100.
    values, profile = compare_fork_samples(a, b, position, [0., 1., 2., 3.])
    assert values['direct_token_jump'] == 100.
    assert values['post_fork_length'] == 3 - position
    assert values['w1_post'] == 0.
    assert values['ed_post'] == pytest.approx(0.)
    np.testing.assert_array_equal(profile, np.zeros(3 - position))


def test_last_token_has_direct_effect_but_undefined_downstream():
    values, profile = compare_fork_samples([[7., 1.]], [[7., 5.]], 1, [0., 2.])
    assert values['direct_token_jump'] == 4.
    assert values['direct_token_jump_over_context_iqr'] == 4.
    assert values['post_fork_length'] == 0
    assert not values['post_fork_defined']
    assert np.isnan(values['w1_post']) and np.isnan(values['ed_post'])
    assert np.isnan(values['w1_post_over_context_iqr'])
    assert profile.shape == (0,)


@pytest.mark.parametrize("context,reason", [
    ([2., 2., 2.], 'near_zero_context_iqr'),
    ([0., 1e-15], 'near_zero_context_iqr'),
    ([np.nan, np.inf], 'nonfinite_context_iqr'),
])
def test_invalid_iqr_retains_raw_outputs_without_fallback(context, reason):
    values, _ = compare_fork_samples([[0., 0.]], [[3., 2.]], 0, context)
    assert values['w1_post'] == 2.
    assert values['ed_post'] == 4.
    assert values['direct_token_jump'] == 3.
    assert not values['distance_context_iqr_valid']
    assert values['distance_scale_invalid_reason'] == reason
    for name in ['w1_post', 'ed_post', 'direct_token_jump']:
        assert np.isnan(values[name + '_over_context_iqr'])


def test_known_context_iqr_and_positive_unit_invariance():
    a, b, context = np.array([[0., 1., 2.]]), np.array([[2., 4., 6.]]), np.arange(5.)
    raw, _ = compare_fork_samples(a, b, 0, context)
    scaled, _ = compare_fork_samples(7 * a, 7 * b, 0, 7 * context)
    assert raw['distance_context_iqr'] == 2.
    for name in ['w1_post', 'ed_post', 'direct_token_jump']:
        assert scaled[name] == pytest.approx(7 * raw[name])
        assert scaled[name + '_over_context_iqr'] == pytest.approx(raw[name + '_over_context_iqr'])


@pytest.mark.parametrize("function", [empirical_w1_by_horizon, energy_distance_v])
@pytest.mark.parametrize("a,b", [([], [[1.]]), ([[np.nan]], [[1.]]), ([[1., 2.]], [[1.]])])
def test_invalid_sample_arrays_fail_explicitly(function, a, b):
    with pytest.raises(ValueError):
        function(a, b)


def test_samples_must_share_prefix_and_forced_token():
    with pytest.raises(ValueError, match='prefix'):
        compare_fork_samples([[0., 2.]], [[1., 2.]], 1, [0., 1.])
    with pytest.raises(ValueError, match='constant'):
        compare_fork_samples([[0., 2.], [1., 2.]], [[1., 2.]], 0, [0., 1.])
