import numpy as np
import pytest

from chronos_outcomes import weighted_events


def test_known_mixture_and_direct_sampling_have_expected_distinct_monte_carlo_variances():
    rng = np.random.default_rng(20261120)
    trials, n = 10000, 20
    first = rng.binomial(n, .2, size=trials) / n
    second = rng.binomial(n, .8, size=trials) / n
    mixture = .7 * first + .3 * second
    direct = rng.binomial(60, .38, size=trials) / 60
    assert mixture.mean() == pytest.approx(.38, abs=.004)
    assert direct.mean() == pytest.approx(.38, abs=.004)
    assert mixture.var(ddof=1) == pytest.approx((.7 ** 2 + .3 ** 2) * .2 * .8 / 20, rel=.08)
    assert direct.var(ddof=1) == pytest.approx(.38 * .62 / 60, rel=.08)
    # Independently known conditional sample-variance arithmetic at counts 4/20 and 16/20.
    a = np.array([1] * 4 + [0] * 16).reshape(20, 1, 1)
    b = np.array([1] * 16 + [0] * 4).reshape(20, 1, 1)
    estimate = weighted_events([a, b], [.7, .3])
    assert estimate["event_probability"].item() == pytest.approx(.38)
    assert estimate["conditional_mc_se"].item() ** 2 == pytest.approx((.7 ** 2 + .3 ** 2) * .16 / 19)
