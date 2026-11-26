"""Boundary and information-leakage regressions for the offline final export."""
import numpy as np
import pandas as pd
import pytest

from finalize_chronos_discovery import exposure_with_indices
from chronos_discovery import risk_ranking, scenario_events


def test_exclusive_pretraining_cutoff_and_first_forecast_index():
    source = pd.DataFrame({'forecast_origin': [100]*4, 'lead': [1, 2, 3, 4],
        'boundary': [102]*4, 'documented_dataset_status': ['in_domain']*4})
    result = exposure_with_indices(source)
    assert result.target_index.tolist() == [100, 101, 102, 103]
    assert result.target_status.tolist() == ['potentially_exposed']*2 + ['heldout_in_domain']*2
    source['documented_dataset_status'] = 'zero_shot'
    assert (exposure_with_indices(source).target_status == 'zero_shot').all()
    source.loc[0, 'lead'] = 0
    with pytest.raises(ValueError):
        exposure_with_indices(source)


def test_tied_uncertainty_is_expected_permutation_aurc():
    # At every coverage, a complete tie has the expected risk of a random
    # ordering. IDs and input order must not turn ties into an oracle.
    loss = np.array([1., 9., 2., 4.])
    for order in [np.arange(4), np.array([3, 0, 2, 1])]:
        score = risk_ranking(np.ones(4), loss[order])
        assert score['aurc'] == pytest.approx(3.)
        assert score['neaurc'] == pytest.approx(1.)
    assert np.isnan(risk_ranking(np.arange(4), np.ones(4))['neaurc'])


def test_fixed_absolute_event_does_not_move_with_prefix():
    context = np.array([-1., 1.]*256)
    paths = np.zeros((2, 64)); paths[0, 56:] = 2.
    greedy = np.zeros(64)
    events = scenario_events(paths, context, greedy)
    assert events[:, 2].tolist() == [False, False]  # last context=1, IQR=2; strict >.5
    paths[0, 56:] = 2.01
    assert scenario_events(paths, context, greedy)[:, 4].tolist() == [True, False]
