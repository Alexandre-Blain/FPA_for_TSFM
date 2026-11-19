"""Offline relabeling math, whole-path stability and minimal descriptors."""
import numpy as np
import pandas as pd
import pytest

import analyze_chronos_phase3_controls as controls
from chronos_distances import empirical_w1_by_horizon, energy_distance_v


def test_cached_statistics_known_shift_unequal_counts_and_unused_rows():
    pool = np.r_[np.zeros((3, 4)), np.full((4, 4), 2.), np.full((2, 4), 99.)]
    cache = controls.prepare_pool(pool)
    np.testing.assert_allclose(controls.pool_statistics(cache, [0, 1, 2], [3, 4]), [2., 4.])
    with pytest.raises(ValueError, match="disjoint"):
        controls.pool_statistics(cache, [0, 1], [1, 3])


def test_cached_statistics_preserve_joint_path_structure_and_match_validated_math():
    a, b = np.array([[0., 0.], [1., 1.]]), np.array([[0., 1.], [1., 0.]])
    observed, _ = controls.permutation_pair(a, b, 19, np.random.default_rng(3))
    np.testing.assert_allclose(observed, [0., np.sqrt(2) - 1], atol=1e-14)
    rng = np.random.default_rng(21)
    pool = rng.normal(size=(15, 7))
    a, b = pool[[1, 4, 5, 6]], pool[[2, 3, 9]]
    observed = controls.pool_statistics(controls.prepare_pool(pool), [1, 4, 5, 6], [2, 3, 9])
    np.testing.assert_allclose(observed, [empirical_w1_by_horizon(a, b).mean(), energy_distance_v(a, b)], atol=1e-13)


def test_permutation_p_includes_observation_ties_and_two_sided_asymmetry():
    null = np.zeros((9, 2))
    np.testing.assert_allclose(controls.permutation_p([1., 2.], null), [.1, .1])
    np.testing.assert_allclose(controls.permutation_p([0., 0.], null), [1., 1.])
    null[:, 0] = -3
    assert controls.permutation_p([-2., 1.], null, two_sided=True)[0] == 1


def test_holm_known_family_does_not_assume_independence():
    np.testing.assert_allclose(controls.holm_adjust([.04, .001, .02]), [.04, .003, .04])


def test_paired_subsampling_shares_reference_and_full_n_is_not_replicated():
    reference = np.tile(np.arange(50.)[:, None], (1, 3))
    constant = np.zeros_like(reference)
    rows = controls.subsample_group(reference, {11: constant, 12: constant}, constant,
                                   (20, 35, 50), 10, np.random.default_rng(9))
    table = pd.DataFrame(rows)
    pivot = table.pivot(index=["sample_size", "repeat"], columns="role", values="w1")
    np.testing.assert_allclose(pivot['11'], pivot['12'])
    np.testing.assert_allclose(pivot['11'], pivot['same_token'])
    assert len(table[table.sample_size.eq(50)]) == 3
    assert table[table.sample_size.eq(20)].w1.nunique() > 1


def test_asymmetry_keeps_reference_and_uses_signed_metric_difference():
    a = np.zeros((3, 4))
    observed, values = controls.asymmetry_permutations(a, a - 1, a + 3, 19, np.random.default_rng(7))
    np.testing.assert_allclose(observed, [2., 4.])
    assert values.shape == (19, 2)
    assert np.any(values[:, 0] < 0)


def test_temporal_statistic_uses_fixed_strict_suffix_segments():
    reference = np.zeros((3, 15))
    other = reference.copy()
    other[:, :10], other[:, 10:] = 2., 1.
    observed, null = controls.temporal_permutations(reference, other, 19, np.random.default_rng(2))
    np.testing.assert_allclose(observed, [2., 1., 1.])
    assert null.shape == (19, 3)


def test_descriptors_known_linear_path_and_endpoint_uncertainty():
    paths = np.array([[1., 3., 5., 7.], [2., 2., 2., 2.]])
    out = controls.path_descriptors(paths, 2.)
    np.testing.assert_allclose(out['ols_slope_iqr_per_step'], [1., 0.], atol=1e-14)
    np.testing.assert_allclose(out['endpoint_change_iqr'], [3., 0.])
    np.testing.assert_allclose(out['detrended_rms_iqr'], [0., 0.], atol=1e-14)
    lo, hi = controls.wilson_interval(0, 50)
    assert lo == 0 and hi == pytest.approx(.0713476, abs=1e-7)


def test_offline_streams_reproducible_and_no_output_inside_source(tmp_path):
    np.testing.assert_array_equal(controls.rng_for(1, 'point', 'null').random(10),
                                  controls.rng_for(1, 'point', 'null').random(10))
    assert not np.array_equal(controls.rng_for(1, 'point', 'null').random(10),
                              controls.rng_for(1, 'point', 'alt').random(10))
    with pytest.raises(ValueError, match="outside the Phase 2"):
        controls.run_controls(tmp_path, tmp_path / 'no', 19, 10)


def test_two_saved_forks_analyze_separately_without_changing_sources(tmp_path):
    import hashlib
    import json

    source = tmp_path / 'source'
    seed_dir = source / 'seed_1'
    seed_dir.mkdir(parents=True)
    (source / 'config.json').write_text(json.dumps({'seeds': [1]}))
    window = dict(source='fixture', dataset_name='fixture', series_id='0001',
                  window_id=0, window_start=0, context_len=4, horizon=4)
    rows = []
    for position in (0, 1):
        directory = seed_dir / 'trajectories' / str(position)
        directory.mkdir(parents=True)
        reference = np.tile(np.linspace(0, 1, 50)[:, None], (1, 3 - position))
        entries, arrays = [], {'same_token_null': reference[::-1].copy()}
        for offset, shift in ((0, 0), (-1, -1), (1, 1)):
            token = 5 + position * 10 + offset
            key = f'token_{token}'
            arrays[key] = reference + shift
            entries.append(dict(token_id=token, array_key=key, forced_value=shift,
                                is_reference=offset == 0, p_sel=.5 if offset == 0 else .25))
            rows.append({**window, 'branch_step': position, 'token_id': token,
                         'trajectory_manifest': f'trajectories/{position}/manifest.json'})
        descriptions = {k: {'shape': list(v.shape), 'dtype': str(v.dtype),
                            'sha256': hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest()}
                        for k, v in arrays.items()}
        np.savez_compressed(directory / 'ensembles.npz', **arrays)
        manifest = dict(schema_version='chronos_numeric_ensembles_v1', archive='ensembles.npz',
                        arrays=descriptions, window=window, branch_step=position,
                        context_iqr_valid=True, context_iqr=1., fork_id=str(position),
                        reference_array_key=f'token_{5 + position * 10}', ensembles=entries)
        (directory / 'manifest.json').write_text(json.dumps(manifest))
    pd.DataFrame(rows).to_csv(seed_dir / 'chronos_scan_summary.csv', index=False)
    original = {p: p.read_bytes() for p in source.rglob('*') if p.is_file()}
    output = controls.run_controls(source, tmp_path / 'output', 19, 10)
    table = pd.read_csv(output / 'permutation_tests.csv')
    assert len(table) == 12 and set(table.branch_step) == {0, 1}
    assert len(pd.read_csv(output / 'directional_asymmetry.csv')) == 4
    assert len(pd.read_csv(output / 'subsampling_draws.csv')) == 126
    assert json.loads((output / 'protocol.json').read_text())['n_point_seed_groups'] == 2
    assert all(path.read_bytes() == contents for path, contents in original.items())
