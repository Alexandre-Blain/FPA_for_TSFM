import numpy as np
import pytest

from chronos_pilot_uncertainty import event_uncertainty, independent_difference, reused_component_covariance


def test_zero_plugin_error_has_nonzero_finite_sample_bound():
    result = event_uncertainty([np.zeros((20, 2, 5)), np.zeros((20, 2, 5))], [.7, .3])
    assert np.all(result["conditional_mc_se"] == 0)
    assert result["hoeffding_radius"] > .2
    difference = independent_difference(result, event_uncertainty([np.zeros((60, 2, 5))], [1.]))
    assert np.all(difference["pointwise_lower"] < 0)
    assert np.all(difference["pointwise_upper"] > 0)


def test_reused_component_covariance_matches_independent_draw_experiment():
    rng = np.random.default_rng(11)
    a = rng.binomial(1, .4, (20000, 20))
    b = rng.binomial(1, .7, (20000, 20))
    mixture = .8 * a.mean(axis=1) + .2 * b.mean(axis=1)
    reuse = a.mean(axis=1)
    covariance = np.cov(mixture, reuse, ddof=1)[0, 1]
    assert covariance == pytest.approx(.8 * .4 * .6 / 20, rel=.04)
    estimated = np.mean([reused_component_covariance(row[:, None, None], .8) for row in a])
    assert estimated == pytest.approx(covariance, rel=.04)
    corrected = mixture.var(ddof=1) + reuse.var(ddof=1) - 2 * covariance
    assert corrected == pytest.approx((mixture - reuse).var(ddof=1))
