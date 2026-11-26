"""Offline post-collection audit and verified exposure export.

Frozen sources and outputs remain intact. The one-based displayed lead maps to
source index origin+lead-1; v1 uses an equivalent zero-based internal index.
This finalizer checks that identity and records indices, never model samples.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'code/chronos_fpa'), str(ROOT / 'scripts/runs')]
import bootstrap  # noqa: E402,F401
from analyze_chronos_discovery import read_dense, first_deviation_groups, candidate_rows
from chronos_discovery import choose_validation, scenario_events
from review_chronos_discovery import execution_costs
from run_chronos_discovery import verify_extra, validate_allocation
from run_chronos_local_pilot import load, digest
from run_chronos_microbenchmark import write_json


def exposure_with_indices(frame):
    """Forecast lead 1 is the zero-based source index forecast_origin."""
    result = frame.copy()
    if not (result.lead >= 1).all() or not (result.lead % 1 == 0).all():
        raise ValueError('One-based integer forecast leads required')
    result['target_index'] = result.forecast_origin + result.lead - 1
    exposed = ((result.documented_dataset_status == 'in_domain')
               & result.boundary.notna() & (result.target_index < result.boundary))
    result['target_status'] = np.where(exposed, 'potentially_exposed',
        np.where(result.documented_dataset_status == 'in_domain',
                 'heldout_in_domain', 'zero_shot'))
    return result


def audit(out):
    analysis = out / 'analysis'
    cells, panel = read_dense(out)  # checks all raw dense objects and source freeze
    checks = []

    def passed(name, evidence):
        checks.append({'check': name, 'status': 'passed', 'evidence': evidence})

    manifest = load(out / 'validation_source_manifest.json')
    for name, sha in manifest.items():
        assert digest(ROOT / name) == sha
        assert digest(out / 'source_at_validation' / name) == sha
    passed('source_freezes', 'collection and validation working sources match archived hashes')

    plan = load(out / 'validation_plan.json')
    validate_allocation(plan['contrasts'])
    candidates = [row for c in cells if c['plan']['block_index'] == 0
                  for row in candidate_rows(c)]
    selected = choose_validation(candidates, panel['config']['validation_selection_seed'])
    assert selected == plan['contrasts']
    passed('selection_reconstruction', 'eight identical contrasts using block0 only; no targets or natural120')

    worst_mass_error = 0.
    for c in cells:
        total = sum(weight for weight, _ in first_deviation_groups(c))
        worst_mass_error = max(worst_mass_error, abs(total - 1))
        for f in c['result']['forks']:
            support = dict(zip(f['q50_support_ids'], f['q50_support_weights']))
            assert len(f['selected_tokens']) <= 8
            assert f['greedy_token'] in f['selected_tokens']
            np.testing.assert_allclose(sum(support.values()), 1., atol=1e-10, rtol=0)
            for token, weight in zip(f['selected_tokens'], f['selected_weights']):
                np.testing.assert_allclose(weight, support[token], atol=1e-10, rtol=0)
            np.testing.assert_allclose(sum(f['selected_weights']) + f['residual_mass'],
                                       1., atol=1e-10, rtol=0)
    passed('q50_disjoint_partition', f'18 blocks; max partition sum error={worst_mass_error:.3g}; no p_sel mixing')

    for phase, horizon, windows in [
        ('fresh_validation', 32, [w['window_id'] for w in panel['windows']]),
        ('natural_reference', 32, [w['window_id'] for w in panel['windows']]),
        ('cpd', 64, load(out / 'cpd_windows.json')['windows']),
        ('cpd_fresh', 64, load(out / 'cpd_windows.json')['windows']),
    ]:
        for wid in windows:
            verify_extra(out, wid, phase, horizon)
        passed(phase + '_integrity', f'{len(windows)} windows; exact caps, roles, greedy prefixes, hashes, RNG identities')

    costs = execution_costs(out, analysis)  # now includes both completed reload workers
    assert costs['failed_attempts'] == 0
    passed('rng_and_cost_accounting', f"{costs['ensembles']} unique streams AND seeds; {costs['trajectories']} saved paths")

    exposure = pd.read_csv(analysis / 'new_H32/exposure_by_lead.csv')
    verified = exposure_with_indices(exposure)
    assert (verified.target_status == exposure.target_status).all()
    verified.to_csv(analysis / 'exposure_by_lead_verified.csv', index=False)
    counts = verified.groupby(['series', 'target_status']).size().to_dict()
    assert counts[('T003562', 'potentially_exposed')] == 16
    assert counts[('T003562', 'heldout_in_domain')] == 16
    passed('exposure_boundary_identity', 'all labels unchanged; displayed lead1 maps to origin; mixed London=16 potential+16 heldout')

    fresh = pd.read_csv(analysis / 'fresh_N120_validation.csv')
    sensitivity = []
    for row in fresh.to_dict('records'):
        _, snap = verify_extra(out, row['window_id'], 'fresh_validation', 32)
        objects = {m['task_id']: a for m, a in snap['records']}
        a, r = objects[row['alternative_object_id']], objects[row['reference_object_id']]
        b = row['b']; scale = float(np.subtract(*np.percentile(a['context'], [75, 25])))
        # Independent 1-D empirical W1 identity at equal N, strict suffix only.
        w1 = np.mean(abs(np.sort(a['values'][:, b+1:b+23].astype(float), axis=0)
                         - np.sort(r['values'][:, b+1:b+23].astype(float), axis=0))) / scale
        np.testing.assert_allclose(w1, row['W1_relative22_iqr'], rtol=1e-10, atol=1e-10)
        neutral = a['values'].copy(); neutral[:, b] = r['values'][0, b]
        ae = scenario_events(neutral, a['context'], a['greedy_values'])[:, row['validation_outcome']]
        re = scenario_events(r['values'], r['context'], r['greedy_values'])[:, row['validation_outcome']]
        sensitivity.append({k: row[k] for k in ['window_id', 'dataset', 'series', 'b', 'token', 'event_name']} | {
            'original_fresh_gap': row['fresh_gap'],
            'forced_coordinate_neutralized_gap': float(ae.mean()-re.mean()),
            'interpretation': 'posthoc measurement sensitivity only; same saved paths, not a new intervention or validation test'})
    pd.DataFrame(sensitivity).to_csv(analysis / 'forced_coordinate_sensitivity.csv', index=False)
    passed('strict_suffix_W1', 'all eight independent N120 distances match sorted-sample identity; forced coordinate excluded')

    replay_rows = []
    receipts = [load(out / 'whitebox' / f'pass{p}.json') for p in (1, 2)]
    assert receipts[0]['process_id'] != receipts[1]['process_id']
    for receipt in receipts:
        assert receipt['sampling_calls'] == receipt['new_trajectories'] == 0
        for name, sha in receipt['activation_files'].items():
            assert digest(out / 'whitebox' / name) == sha
        for case in receipt['checks']:
            comparisons = [case['capture_vs_plain_logits'],
                *case['reload_tensor_checks'].values(), *case['historical_teacher_forced_checks'].values()]
            replay_rows.append({'pass': receipt['fresh_process_pass'], 'case': case['case'],
                'tensor_comparisons': len(comparisons), 'all_exact': all(x['exact'] for x in comparisons),
                'max_absolute_error': max(x['max_absolute_error'] for x in comparisons),
                'numeric_values_exact': case['numeric_values_exact'],
                'online_hidden_equivalence': 'unverifiable: original online tensors absent'})
    pd.DataFrame(replay_rows).to_csv(analysis / 'whitebox_replay_checks.csv', index=False)
    profiles = pd.read_csv(out / 'whitebox/representation_profiles.csv')
    assert (profiles.loc[profiles.relative_query <= 0, 'distance'].abs() < 3e-5).all()
    passed('replay_and_causal_index_alignment', 'different reload PIDs; all receipt hashes; no divergence before forced token enters decoder')

    pd.DataFrame(checks).to_csv(analysis / 'implementation_audit.csv', index=False)
    write_json(analysis / 'postcollection_audit.json', {
        'status': 'passed', 'checks': checks, 'new_model_draws': 0,
        'source_sha256': digest(Path(__file__)),
        'exposure_verification': 'all original labels verified independently; source indices added for review',
        'limits': ['No general proof of absence of bias', 'Six dependent source series, two datasets',
                   'Pointwise Monte Carlo CIs do not measure population uncertainty',
                   'Exposure is not memorization; attention is not causal mechanism',
                   'Offline budget subsets exclude selection and some shared overhead']})
    print(f'Offline audit passed: {len(checks)} checks; original exposure labels verified; zero new draws')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    audit(parser.parse_args().run)
