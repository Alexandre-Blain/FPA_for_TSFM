from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CHRONOS_CODE = ROOT / "code" / "chronos_fpa"
for path in (CHRONOS_CODE, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import bootstrap

from chronos_benchmark_scan import (
    DEFAULT_BRANCH_STEPS,
    DEFAULT_BUNDLE_CONTINUATION_RANKS,
    NORMALIZED_SCORE_COL,
    RAW_SCORE_COL,
    iter_benchmark_folder_series,
    iter_csv_folder_series,
    iter_sliding_windows,
    parse_int_list,
    rank_scan_summary,
    resolve_score_column,
    scan_window,
)
from chronos_io import DEFAULT_CHRONOS_MODEL_ID, load_chronos_t5_raw
from chronos_scan_visualization import plot_chronos_scan_outputs
from results_io import make_run_dir, save_dataframe, save_json
from run_config import add_config_argument, parse_run_configuration, prepare_run_state
from trajectory_export import add_trajectory_arguments, validate_trajectory_arguments, trajectory_options_from_args


def _parse_csv(value: str) -> list[str]:
    if not value.strip():
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


from functools import partial
from checkpoint_store import start_store
from research_schema import (
    WINDOW_KEY_COLS, GROUP_KEY_COLS, read_csv, append_dataframe as _append_dataframe,
    window_key as _window_key, expected_group_keys as _expected_group_keys,
)
from run_progress import completed_windows_from_frame as _completed_window_keys, write_checkpoint as _write_checkpoint
from run_progress import unresolved_errors

_read_csv_if_exists = partial(read_csv, missing_ok=True)


def _group_key(window, branch_mode, branch_step):
    return _window_key(window) + (branch_mode, int(branch_step))


def run(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description="Scan Chronos benchmark-style datasets for token-branch shifts."
    )
    add_config_argument(parser)
    add_trajectory_arguments(parser)
    parser.add_argument("--model-id", default=DEFAULT_CHRONOS_MODEL_ID)
    parser.add_argument("--device", default=None)
    parser.add_argument("--dtype", default=None)
    parser.add_argument(
        "--source",
        choices=["benchmark-folder", "csv-folder"],
        default="benchmark-folder",
    )
    parser.add_argument("--benchmark-folder", default="data/raw/chronos_benchmark")
    parser.add_argument("--csv-folder", default=None)
    parser.add_argument("--target-columns", default="")
    parser.add_argument(
        "--datasets",
        default="",
        help="Optional comma-separated exported dataset names.",
    )
    parser.add_argument("--context-len", type=int, default=512)
    parser.add_argument(
        "--adaptive-context",
        action="store_true",
        help="Shrink context_len for short series when possible.",
    )
    parser.add_argument("--no-adaptive-context", action="store_false", dest="adaptive_context")
    parser.add_argument("--min-context-len", type=int, default=64)
    parser.add_argument("--horizon", type=int, default=64)
    parser.add_argument(
        "--slide-step",
        type=int,
        default=None,
        help="Sliding-window stride. Default is horizon // 2.",
    )
    parser.add_argument(
        "--branch-steps",
        default=",".join(str(step) for step in DEFAULT_BRANCH_STEPS),
    )
    parser.add_argument(
        "--branch-modes",
        default="single,bundle",
        help="Comma-separated modes among: single,bundle.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--bundle-size", type=int, default=3)
    parser.add_argument(
        "--bundle-continuation-ranks",
        default=",".join(str(rank) for rank in DEFAULT_BUNDLE_CONTINUATION_RANKS),
    )
    parser.add_argument("--num-samples", type=int, default=30)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument(
        "--sample-top-k",
        type=int,
        default=50,
        help="Use 0 to disable top-k sampling truncation.",
    )
    parser.add_argument(
        "--bad-base-threshold",
        type=float,
        default=1.0,
        help=(
            "Warn when greedy base MAE / context_iqr reaches this value. "
            "Undefined context scales are reported separately."
        ),
    )
    parser.add_argument("--max-datasets", type=int, default=1)
    parser.add_argument("--max-series-per-dataset", type=int, default=3)
    parser.add_argument("--max-windows-per-series", type=int, default=2)
    parser.add_argument("--max-total-windows", type=int, default=10)
    parser.add_argument(
        "--rank-score-column",
        default="",
        help=(
            "Column used to rank branches. Empty = "
            f"{NORMALIZED_SCORE_COL}. Use {RAW_SCORE_COL} for raw ranking."
        ),
    )
    parser.add_argument(
        "--visualisation",
        action="store_true",
        help="Generate PNG figures from the raw scan CSV outputs at the end.",
    )
    parser.add_argument("--visualisation-top-n", type=int, default=25)
    parser.add_argument(
        "--visualisation-score-column",
        default="",
        help=(
            "Score column used in generated figures. Default uses context_iqr; "
            "no automatic normalization fallback."
        ),
    )
    parser.add_argument(
        "--auto-refinement",
        action="store_true",
        help=(
            "After the main scan, automatically rerun the most sensitive "
            "windows with denser branch steps and more token ranks."
        ),
    )
    parser.add_argument(
        "--refinement-global-top-windows",
        type=int,
        default=20,
        help="Number of globally highest-scoring windows selected for auto-refinement.",
    )
    parser.add_argument(
        "--refinement-per-dataset-top-windows",
        type=int,
        default=5,
        help="Number of highest-scoring windows selected per dataset for auto-refinement.",
    )
    parser.add_argument(
        "--refinement-branch-steps",
        default="0,2,4,6,8,10,12,16",
        help="Dense branch-step list used by auto-refinement.",
    )
    parser.add_argument(
        "--refinement-top-k",
        type=int,
        default=15,
        help="Number of forced token ranks tested at each refinement branch step.",
    )
    parser.add_argument(
        "--refinement-num-samples",
        type=int,
        default=40,
        help="Number of Chronos samples per forced branch in auto-refinement.",
    )
    parser.add_argument(
        "--refinement-branch-modes",
        default="single",
        help="Comma-separated refinement modes. Default keeps the targeted pass cheaper: single.",
    )
    parser.add_argument(
        "--refinement-run-name",
        default="chronos_refinement_dense",
        help="Readable folder prefix for the refinement run.",
    )
    parser.add_argument(
        "--refinement-output-root",
        default="",
        help=(
            "Where to save refinement runs. Default creates a refinement subfolder "
            "inside the main run folder."
        ),
    )
    parser.add_argument(
        "--refinement-resume-from",
        default="",
        help="Existing refinement folder to resume after the main scan has completed.",
    )
    parser.add_argument(
        "--refinement-visualisation",
        action="store_true",
        help="Generate refinement PNG figures after the targeted pass.",
    )
    parser.add_argument("--output-root", default="result")
    parser.add_argument(
        "--run-name",
        default="",
        help=(
            "Optional readable output folder prefix. The timestamp is still "
            "appended, for example --run-name topology_scan."
        ),
    )
    parser.add_argument(
        "--resume-from",
        default="",
        help=(
            "New-format result folder to resume. Validated atomic branch groups "
            "are restored using the saved scientific configuration."
        ),
    )
    parser.add_argument(
        "--checkpoint-every-branch-groups",
        type=int,
        default=1,
        help=(
            "Write checkpoint metadata every N completed branch groups. "
            "Every group is saved atomically regardless of this interval. "
            "Use 0 to disable checkpoint metadata writes during the run."
        ),
    )
    parser.add_argument("--no-progress", action="store_true")
    args, config_path, input_config, config_parameters = parse_run_configuration(parser, argv)
    validate_trajectory_arguments(args)
    if args.auto_refinement and (args.trajectory_metrics or args.save_trajectories) and args.refinement_branch_modes != "single":
        raise ValueError("Trajectory metrics require single-token auto-refinement")

    if args.checkpoint_every_branch_groups < 0:
        raise ValueError("--checkpoint-every-branch-groups must be >= 0.")
    if args.auto_refinement and args.source != "benchmark-folder":
        raise ValueError("--auto-refinement currently requires --source benchmark-folder.")
    if args.top_k <= 0 or args.num_samples <= 0 or args.max_total_windows <= 0:
        raise ValueError("top_k, num_samples and max_total_windows must be positive")

    if args.resume_from:
        run_dir = Path(args.resume_from)
        if not run_dir.exists():
            raise FileNotFoundError(f"Cannot resume from missing folder: {run_dir}")
        print(f"Resuming Chronos benchmark scan outputs in: {run_dir}")
    else:
        run_dir = make_run_dir(
            args.output_root,
            "chronos_benchmark_scan",
            run_name=args.run_name or None,
        )
        print(f"Saving Chronos benchmark scan outputs to: {run_dir}")
    save_json(
        run_dir / ("resume_input_config_latest.json" if args.resume_from else "input_config.json"),
        input_config
        or {
            "description": "Generated from CLI arguments after parsing.",
            "parameters": vars(args),
        },
    )

    branch_steps = parse_int_list(args.branch_steps)
    branch_modes = _parse_csv(args.branch_modes)
    if not branch_steps or not branch_modes or set(branch_modes) - {"single", "bundle"}:
        raise ValueError("Provide branch steps and modes drawn from single,bundle")
    bundle_continuation_ranks = parse_int_list(args.bundle_continuation_ranks)
    sample_top_k = None if args.sample_top_k == 0 else args.sample_top_k

    prepare_run_state(run_dir, args, "scan")
    store, existing_summary_df, completed_groups = start_store(run_dir, bool(args.resume_from))
    completed_windows = _completed_window_keys(
        existing_summary_df,
        completed_groups=completed_groups,
        branch_steps=branch_steps,
        branch_modes=branch_modes,
        bundle_size=args.bundle_size,
    )
    if args.resume_from:
        print(
            "Resume state: "
            f"{len(completed_groups)} completed branch groups, "
            f"{len(completed_windows)} completed windows."
        )

    model, tokenizer, chronos_config = load_chronos_t5_raw(
        model_id=args.model_id,
        device=args.device,
        dtype=args.dtype,
    )
    if args.resume_from:
        store.restore_rng()

    trajectory_options = trajectory_options_from_args(args, run_dir, model, chronos_config)

    min_series_length = (
        args.min_context_len + args.horizon
        if args.adaptive_context
        else args.context_len + args.horizon
    )

    if args.source == "benchmark-folder":
        series_iter = iter_benchmark_folder_series(
            args.benchmark_folder,
            dataset_names=_parse_csv(args.datasets) or None,
            max_datasets=args.max_datasets,
            max_series_per_dataset=args.max_series_per_dataset,
            min_length=min_series_length,
        )
    else:
        if args.csv_folder is None:
            raise ValueError("--csv-folder is required when --source=csv-folder.")
        series_iter = iter_csv_folder_series(
            args.csv_folder,
            target_columns=_parse_csv(args.target_columns) or None,
            min_length=min_series_length,
        )

    steps_path = run_dir / "chronos_scan_steps.csv"
    summary_path = run_dir / "chronos_scan_summary.csv"
    errors_path = run_dir / "chronos_scan_errors.csv"
    checkpoint_counter = 0
    newly_completed_windows = 0

    def checkpoint_callback(step_df, summary_df, window, branch_mode, branch_step):
        nonlocal checkpoint_counter
        group_key = _group_key(window, branch_mode, branch_step)
        if group_key in completed_groups:
            return

        store.commit(step_df, summary_df)
        completed_groups.add(group_key)
        checkpoint_counter += 1

        if (
            args.checkpoint_every_branch_groups > 0
            and checkpoint_counter % args.checkpoint_every_branch_groups == 0
        ):
            _write_checkpoint(
                run_dir,
                status="running",
                completed_groups=completed_groups,
                completed_windows=completed_windows,
                last_event={
                    "source": window.source,
                    "dataset_name": window.dataset_name,
                    "series_id": window.series_id,
                    "window_id": window.window_id,
                    "window_start": window.window_start,
                    "branch_mode": branch_mode,
                    "branch_step": branch_step,
                },
            )

    for series in series_iter:
        for window in iter_sliding_windows(
            series,
            context_len=args.context_len,
            horizon=args.horizon,
            slide_step=args.slide_step,
            max_windows_per_series=args.max_windows_per_series,
            adaptive_context=args.adaptive_context,
            min_context_len=args.min_context_len,
        ):
            if len(completed_windows) >= args.max_total_windows:
                break
            expected_groups = _expected_group_keys(
                window,
                branch_steps=branch_steps,
                branch_modes=branch_modes,
                bundle_size=args.bundle_size,
            )
            missing_groups = expected_groups.difference(completed_groups)
            if not expected_groups or not missing_groups:
                if expected_groups:
                    completed_windows.add(_window_key(window))
                continue
            try:
                print(
                    "Scanning "
                    f"{window.dataset_name}/{window.series_id} "
                    f"window={window.window_id} start={window.window_start}"
                )
                step_df, summary_df = scan_window(
                    model=model,
                    tokenizer=tokenizer,
                    chronos_config=chronos_config,
                    window=window,
                    branch_steps=branch_steps,
                    branch_modes=branch_modes,
                    top_k=args.top_k,
                    bundle_size=args.bundle_size,
                    bundle_continuation_ranks=bundle_continuation_ranks,
                    num_samples=args.num_samples,
                    temperature=args.temperature,
                    sample_top_k=sample_top_k,
                    bad_base_threshold=args.bad_base_threshold,
                    show_progress=not args.no_progress,
                    completed_branch_groups={
                        (key[-2], int(key[-1]))
                        for key in completed_groups
                        if key[: len(WINDOW_KEY_COLS)] == _window_key(window)
                    },
                    checkpoint_callback=checkpoint_callback,
                    trajectory_options=trajectory_options,
                )
                if expected_groups.issubset(completed_groups):
                    completed_windows.add(_window_key(window))
                    newly_completed_windows += 1
                    _write_checkpoint(
                        run_dir,
                        status="running",
                        completed_groups=completed_groups,
                        completed_windows=completed_windows,
                        last_event={
                            "source": window.source,
                            "dataset_name": window.dataset_name,
                            "series_id": window.series_id,
                            "window_id": window.window_id,
                            "window_start": window.window_start,
                            "event": "window_complete",
                        },
                    )
            except Exception as exc:
                error_df = pd.DataFrame(
                    [
                        {
                            "source": window.source,
                            "dataset_name": window.dataset_name,
                            "series_id": window.series_id,
                            "window_id": window.window_id,
                            "window_start": window.window_start,
                            "context_len": window.context_len,
                            "horizon": window.horizon,
                            "error": repr(exc),
                        }
                    ]
                )
                _append_dataframe(errors_path, error_df)
                _write_checkpoint(
                    run_dir,
                    status="error_recorded",
                    completed_groups=completed_groups,
                    completed_windows=completed_windows,
                    last_event={
                        "source": window.source,
                        "dataset_name": window.dataset_name,
                        "series_id": window.series_id,
                        "window_id": window.window_id,
                        "window_start": window.window_start,
                        "error": repr(exc),
                    },
                )
        if len(completed_windows) >= args.max_total_windows:
            break

    summary_df, completed_groups = store.recover()
    completed_windows = _completed_window_keys(summary_df, completed_groups, branch_steps, branch_modes, args.bundle_size)
    steps_df = _read_csv_if_exists(steps_path)
    rank_score_column = args.rank_score_column.strip() or None
    ranking_df = rank_scan_summary(summary_df, rank_col=rank_score_column)
    resolved_rank_score_column = resolve_score_column(summary_df, rank_score_column)
    errors_df = _read_csv_if_exists(errors_path)
    active_errors = unresolved_errors(errors_df, completed_windows)
    undefined_quality_groups = (
        int(summary_df.drop_duplicates(GROUP_KEY_COLS)["base_forecast_bad"].isna().sum())
        if not summary_df.empty and "base_forecast_bad" in summary_df else 0
    )
    warning_cols = [
        "source",
        "dataset_name",
        "series_id",
        "window_id",
        "window_start",
        "context_len",
        "horizon",
        "branch_mode",
        "branch_step",
        "base_mae",
        "base_rmse",
        "gt_mean_abs",
        "gt_std",
        "gt_rms",
        "gt_range",
        "gt_iqr",
        "context_mean_abs",
        "context_std",
        "context_rms",
        "context_range",
        "context_iqr",
        "window_scale",
        "base_mae_over_gt_mean_abs",
        "base_mae_over_context_iqr",
        "base_mae_over_context_std",
        "base_mae_over_context_range",
        "base_mae_over_gt_iqr",
        "base_mae_over_gt_std",
        "base_mae_over_gt_range",
        "base_mae_over_window_scale",
        "base_forecast_bad",
    ]
    if not summary_df.empty and "base_forecast_bad" in summary_df.columns:
        base_warning_df = (
            summary_df[summary_df["base_forecast_bad"].fillna(False).astype(bool)]
            [[col for col in warning_cols if col in summary_df.columns]]
            .drop_duplicates()
            .sort_values("base_mae_over_context_iqr", ascending=False)
            .reset_index(drop=True)
        )
    else:
        base_warning_df = pd.DataFrame(columns=warning_cols)

    save_dataframe(run_dir / "chronos_scan_steps.csv", steps_df)
    save_dataframe(run_dir / "chronos_scan_summary.csv", summary_df)
    save_dataframe(run_dir / "chronos_scan_ranking.csv", ranking_df)
    save_dataframe(run_dir / "chronos_scan_errors.csv", errors_df)
    save_dataframe(run_dir / "chronos_base_quality_warnings.csv", base_warning_df)
    save_json(
        run_dir / "config.json",
        {
            "args": vars(args),
            "config_path": str(config_path) if config_path else "",
            "config_parameters": config_parameters,
            "branch_steps": branch_steps,
            "branch_modes": branch_modes,
            "bundle_continuation_ranks": bundle_continuation_ranks,
            "sample_top_k_resolved": sample_top_k,
            "min_series_length": min_series_length,
            "bad_base_threshold": args.bad_base_threshold,
            "rank_score_column": resolved_rank_score_column,
            "automatic_scale_fallback": False,
            "completed_windows": len(completed_windows),
            "newly_completed_windows": newly_completed_windows,
            "completed_branch_groups": len(completed_groups),
            "undefined_base_quality_groups": undefined_quality_groups,
            "chronos_config": {
                "context_length": chronos_config.context_length,
                "prediction_length": chronos_config.prediction_length,
                "n_tokens": chronos_config.n_tokens,
                "n_special_tokens": chronos_config.n_special_tokens,
                "model_type": chronos_config.model_type,
                "tokenizer_class": chronos_config.tokenizer_class,
            },
        },
    )
    _write_checkpoint(
        run_dir,
        status="complete" if active_errors.empty and len(completed_windows) else "partial",
        completed_groups=completed_groups,
        completed_windows=completed_windows,
        last_event={
            "completed_windows": len(completed_windows),
            "newly_completed_windows": newly_completed_windows,
            "completed_branch_groups": len(completed_groups),
        },
    )

    print("\nTop branch-shift windows:")
    display_cols = [
        "source",
        "dataset_name",
        "series_id",
        "window_id",
        "window_start",
        "branch_mode",
        "branch_step",
        "mean_law_shift",
        "max_law_shift",
        "context_iqr",
        "window_scale",
        "base_mae_over_gt_mean_abs",
        "base_mae_over_context_iqr",
        "progressive_token_bin_forking_score",
        "context_iqr_scaled_progressive_token_bin_forking_score",
        "context_std_scaled_progressive_token_bin_forking_score",
        "context_range_scaled_progressive_token_bin_forking_score",
        "progressive_token_bin_forking_score_over_window_scale",
        "window_scaled_progressive_token_bin_forking_score",
        "token_probability",
        "token_surprisal",
        "normalized_token_entropy",
        "top1_top2_margin",
        "peak_relative_step_after_branch",
        "persistence_ratio",
    ]
    if not ranking_df.empty:
        print(f"(ranked by {resolved_rank_score_column})")
        print(ranking_df[[col for col in display_cols if col in ranking_df.columns]].head(20).to_string(index=False))
    else:
        print("(no successful branch summaries)")

    if not base_warning_df.empty:
        print(
            f"\nWARNING: Chronos base forecast looks poor for "
            f"{len(base_warning_df)} window/mode/step entries; "
            "see chronos_base_quality_warnings.csv."
        )
    if undefined_quality_groups:
        print(f"\nWARNING: {undefined_quality_groups} groups have undefined base quality (invalid scale or forecast error); this is not a good-forecast classification.")

    if not errors_df.empty:
        print(f"\nEncountered {len(errors_df)} window errors; see chronos_scan_errors.csv.")

    if args.visualisation:
        figure_paths = plot_chronos_scan_outputs(
            run_dir,
            top_n=args.visualisation_top_n,
            score_col=args.visualisation_score_column or None,
        )
        if figure_paths:
            print("\nSaved visualisation figures:")
            for path in figure_paths:
                print(f"- {path}")
        else:
            print("\nNo visualisation figures generated; scan CSVs may be empty.")

    if args.auto_refinement and active_errors.empty and len(completed_windows):
        del model, tokenizer, chronos_config
        gc.collect()
        from run_chronos_targeted_refinement import run_with_args as run_refinement

        refinement_output_root = (
            Path(args.refinement_output_root)
            if args.refinement_output_root
            else run_dir / "refinement"
        )
        refinement_args = [
            "--source-run",
            str(run_dir),
            "--benchmark-folder",
            str(args.benchmark_folder),
            "--model-id",
            str(args.model_id),
            "--context-len",
            str(args.context_len),
            "--horizon",
            str(args.horizon),
            "--min-context-len",
            str(args.min_context_len),
            "--branch-modes",
            str(args.refinement_branch_modes),
            "--refine-branch-steps",
            str(args.refinement_branch_steps),
            "--refine-top-k",
            str(args.refinement_top_k),
            "--num-samples",
            str(args.refinement_num_samples),
            "--temperature",
            str(args.temperature),
            "--sample-top-k",
            str(args.sample_top_k),
            "--bad-base-threshold",
            str(args.bad_base_threshold),
            "--global-top-windows",
            str(args.refinement_global_top_windows),
            "--per-dataset-top-windows",
            str(args.refinement_per_dataset_top_windows),
            "--output-root",
            str(refinement_output_root),
            "--run-name",
            str(args.refinement_run_name),
            "--checkpoint-every-branch-groups",
            str(args.checkpoint_every_branch_groups),
        ]
        if args.trajectory_metrics:
            refinement_args.append("--trajectory-metrics")
        if args.save_trajectories:
            refinement_args.append("--save-trajectories")
        refinement_args.extend(["--sampling-seed", str(args.sampling_seed)])
        if args.device is not None:
            refinement_args.extend(["--device", str(args.device)])
        if args.dtype is not None:
            refinement_args.extend(["--dtype", str(args.dtype)])
        if args.slide_step is not None:
            refinement_args.extend(["--slide-step", str(args.slide_step)])
        if args.rank_score_column.strip():
            refinement_args.extend(["--rank-score-column", args.rank_score_column.strip()])
        if args.adaptive_context:
            refinement_args.append("--adaptive-context")
        else:
            refinement_args.append("--no-adaptive-context")
        if args.refinement_resume_from:
            refinement_args.extend(["--resume-from", args.refinement_resume_from])
        elif (run_dir / "refinement_state.json").exists():
            with (run_dir / "refinement_state.json").open(encoding="utf-8") as stream:
                previous_refinement = json.load(stream)["run_dir"]
            refinement_args.extend(["--resume-from", previous_refinement])
        if args.refinement_visualisation:
            refinement_args.extend(["--visualisation", "--visualisation-top-n", str(args.visualisation_top_n)])
            if args.visualisation_score_column:
                refinement_args.extend(["--visualisation-score-column", args.visualisation_score_column])
        if args.no_progress:
            refinement_args.append("--no-progress")

        print("\nStarting automatic targeted refinement...")
        _write_checkpoint(run_dir, "refinement_running", completed_groups, completed_windows,
                          {"stage": "automatic_refinement"})
        refinement_dir = run_refinement(
            refinement_args,
            on_run_ready=lambda path: save_json(run_dir / "refinement_state.json", {"run_dir": str(path)}),
        )
        with (refinement_dir / "checkpoint.json").open(encoding="utf-8") as stream:
            refinement_status = json.load(stream)["status"]
        _write_checkpoint(run_dir, "complete" if refinement_status == "complete" else "partial",
                          completed_groups, completed_windows,
                          {"stage": "automatic_refinement", "refinement_run": str(refinement_dir),
                           "refinement_status": refinement_status})
        print(f"Automatic targeted refinement saved to: {refinement_dir}")

    print(f"\nSaved results to: {run_dir}")


if __name__ == "__main__":
    run()



