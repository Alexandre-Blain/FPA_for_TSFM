"""Versioned plot-only completion of an already evaluated offline campaign.

Preserves the first target-access freeze and every original numeric table.
No fits, sampling, model loading or hypothesis tests are repeated or changed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_chronos_incremental as analysis


def main(run):
    started = time.perf_counter()
    original = run / 'analysis'
    out = run / 'analysis_v2'
    amendment = analysis.load(run / 'analysis_v1_failed_plot_provenance/amendment.json')
    original_freeze = analysis.load(run / 'analysis_freeze.json')
    audit = analysis.load(run / 'integrity_audit.json')
    if audit['mathematical_and_raw_integrity'] != 'passed' or audit['preservation']['status'] != 'passed':
        raise ValueError('Validated raw evidence and historical preservation required')
    analysis.verify_sources(run, 'H1')
    if analysis.load(run/'analysis_v1_failed_plot_provenance/analysis_freeze.json') != original_freeze:
        raise ValueError('Original target-access freeze changed')
    for name, expected in amendment['original_analysis_outputs_sha256'].items():
        if analysis.digest(original/name) != expected:
            raise ValueError('Original numeric output changed: '+name)
    freeze = {'version':2, 'purpose':'plot-only correction; numeric evaluation reused byte-for-byte',
        'original_freeze_sha256':analysis.digest(run/'analysis_freeze.json'),
        'amendment_sha256':analysis.digest(run/'analysis_v1_failed_plot_provenance/amendment.json'),
        'finalizer_sha256':analysis.digest(Path(__file__)),
        'plot_source_sha256':analysis.digest(Path(analysis.__file__)),
        'source_numeric_outputs':amendment['original_analysis_outputs_sha256'],
        'scientific_protocol_changes':False, 'new_inference':False}
    freeze_path = run/'analysis_v2_freeze.json'
    if freeze_path.exists() and analysis.load(freeze_path) != freeze:
        raise ValueError('Versioned completion source changed; preserve evidence and create an explicit new revision')
    if not freeze_path.exists():
        analysis.save_clean(freeze_path, freeze)
    out.mkdir(exist_ok=True)
    for name in freeze['source_numeric_outputs']:
        destination=out/name
        if destination.exists():
            if analysis.digest(destination) != freeze['source_numeric_outputs'][name]:
                raise ValueError('Copied numeric output changed: '+name)
        else:
            shutil.copy2(original/name,destination)
    def table(name):
        return pd.read_csv(out/name,float_precision='round_trip')
    frame=table('H1_forecast_errors.csv')
    fits=analysis.load(out/'H1_fitted_models.json')
    h1={'frame':frame, 'scores':{(f['population'],f['target'],f['method']):np.array(f['log_prediction']) for f in fits},
        'comparisons':analysis.load(out/'H1_incremental_comparisons.json'),
        'costs':table('H1_actual_costs.csv')}
    comparisons=analysis.load(out/'H2_paired_comparisons.json')
    h2={'frame':table('H2_event_estimates.csv'),'references':table('H2_independent_references.csv'),
        'source':table('H2_source_averages.csv'),'summaries':table('H2_budget_summary.csv').to_dict('records'),
        'comparisons':comparisons,'taskb':table('H2_actual_future_Brier.csv'),
        'primary':next((c for c in comparisons if c['method']=='first_deviation_neyman_cost' and c['anchor']==480),None)}
    analysis.make_figures(run,out,h1,h2)
    summary={'H1_comparisons':h1['comparisons'],'H2_primary':h2['primary'],
        'formal_tests':analysis.load(out/'primary_tests.json'),
        'H1_evaluable_targets':int(frame.target_available.sum()),
        'H2_evaluable_actual_outcomes':int(h2['references'].groupby('window_id').actual_available.first().sum()),
        'model_subprocess_seconds':analysis.charged_seconds(run),
        'new_data_and_run_bytes':analysis.new_bytes(run),
        'collection_status':original_freeze['collection_status'],
        'resource_compliance':audit['resource_compliance'],
        'analysis_version':2,'numeric_evaluation_unchanged_from_v1':True,
        'plot_finalization_seconds':time.perf_counter()-started}
    analysis.save_clean(out/'scientific_summary.json',summary)
    for name,expected in freeze['source_numeric_outputs'].items():
        if analysis.digest(out/name) != expected:
            raise ValueError('Numeric invariance failed: '+name)
    analysis.save_clean(run/'analysis_complete.json',{'utc':datetime.now(timezone.utc).isoformat(),
        'analysis_version':2,'analysis_directory':'analysis_v2',
        'original_analysis_freeze_sha256':freeze['original_freeze_sha256'],
        'versioned_freeze_sha256':analysis.digest(freeze_path),
        'outputs':{p.name:analysis.digest(p) for p in out.iterdir() if p.is_file()},
        'resource_compliance':audit['resource_compliance']})
    analysis.save_clean(run/'offline_status.json',{'stage':'analysis complete; scientific interpretation, figure inspection, report and handout pending',
        'utc':datetime.now(timezone.utc).isoformat(),'analysis_directory':'analysis_v2','new_inference':False})
    print('VERSIONED OFFLINE ANALYSIS COMPLETE; original numeric outputs unchanged',flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    args=parser.parse_args()
    main(args.run.resolve())
