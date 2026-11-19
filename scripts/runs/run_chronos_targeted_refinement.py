from __future__ import annotations

import argparse
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
    DEFAULT_BUNDLE_CONTINUATION_RANKS,
    NORMALIZED_SCORE_COL,
    RAW_SCORE_COL,
    iter_benchmark_folder_series,
    iter_sliding_windows,
    parse_int_list,
    rank_scan_summary,
    resolve_score_column,
    scan_window,
)
from chronos_io import DEFAULT_CHRONOS_MODEL_ID, load_chronos_t5_raw
from chronos_scan_visualization import plot_chronos_scan_outputs
from chronos_scales import normalization_scale_for_score
from results_io import make_run_dir, save_dataframe, save_json
from run_config import add_config_argument, parse_run_configuration, prepare_run_state
from trajectory_export import add_trajectory_arguments, validate_trajectory_arguments, trajectory_options_from_args


from functools import partial
from checkpoint_store import start_store
from research_schema import (
    WINDOW_KEY_COLS, GROUP_KEY_COLS, read_csv, append_dataframe as _append_dataframe,
    window_key as _window_key, window_key as _window_key_from_row,
    expected_group_keys as _expected_group_keys, is_base_branch as _is_base_branch,
    validate_branch_keys,
)
from run_progress import completed_windows_from_frame as _completed_window_keys_from_targets, write_checkpoint as _write_checkpoint

BRANCH_MATCH_COLS = GROUP_KEY_COLS + ["branch_identity"]
_read_csv_if_exists = partial(read_csv, missing_ok=True)


def _parse_csv(value):
    return [part.strip() for part in value.split(",") if part.strip()]


def _group_key(window, branch_mode, branch_step):
    return _window_key(window) + (branch_mode, int(branch_step))


def _select_target_windows(
    source_run: Path,
    global_top_windows: int,
    per_dataset_top_windows: int,
    rank_score_col: str | None,
) -> pd.DataFrame:
    summary = _read_csv_if_exists(source_run / "chronos_scan_summary.csv")
    if summary.empty:
        summary = _read_csv_if_exists(source_run / "chronos_scan_ranking.csv")
    if summary.empty:
        raise ValueError(f"No summary/ranking CSV found in {source_run}")

    score_col = resolve_score_column(summary, rank_score_col)
    if score_col not in summary.columns:
        raise ValueError(f"Missing rank score column {score_col!r} in {source_run}")
    if not set(WINDOW_KEY_COLS).issubset(summary.columns):
        missing = sorted(set(WINDOW_KEY_COLS).difference(summary.columns))
        raise ValueError(f"Source run is missing window columns: {missing}")

    work = summary[~_is_base_branch(summary)].copy()
    if work.empty:
        raise ValueError("No alternative branches available for refinement selection")
    work[score_col] = pd.to_numeric(work[score_col], errors="coerce")
    work = work.dropna(subset=[score_col])

    grouped = (
        work.sort_values(score_col, ascending=False).groupby(WINDOW_KEY_COLS, dropna=False)
        .agg(
            source_max_score=(score_col, "max"),
            source_best_branch_step=("branch_step", "first"),
        )
        .reset_index()
        .sort_values("source_max_score", ascending=False)
    )
    global_targets = grouped.head(global_top_windows)
    per_dataset_targets = (
        grouped.groupby("dataset_name", group_keys=False)
        .head(per_dataset_top_windows)
        .sort_values("source_max_score", ascending=False)
    )
    selected = (
        pd.concat([global_targets, per_dataset_targets], ignore_index=True)
        .drop_duplicates(WINDOW_KEY_COLS)
        .sort_values("source_max_score", ascending=False)
        .reset_index(drop=True)
    )
    for col in ("window_id", "window_start", "context_len", "horizon"):
        selected[col] = pd.to_numeric(selected[col], errors="coerce").astype(int)
    return selected


def _write_stability_reports(source_run: Path, run_dir: Path, score_col: str) -> None:
    source_summary = _read_csv_if_exists(source_run / "chronos_scan_summary.csv")
    refined_summary = _read_csv_if_exists(run_dir / "chronos_scan_summary.csv")
    if source_summary.empty or refined_summary.empty:
        return
    source_summary, refined_summary = source_summary.copy(), refined_summary.copy()
    for frame in (source_summary, refined_summary):
        validate_branch_keys(frame)
        frame["branch_identity"] = [
            f"token:{int(row.token_id)}" if row.branch_mode == "single" else f"bundle:{row.branch_id}|tokens:{row.forced_tokens}"
            for row in frame.itertuples(index=False)
        ]

    common_match_cols = [col for col in BRANCH_MATCH_COLS if col in source_summary.columns and col in refined_summary.columns]
    if len(common_match_cols) < len(GROUP_KEY_COLS):
        return
    if score_col not in source_summary.columns or score_col not in refined_summary.columns:
        raise ValueError("Stability comparison requires the SAME score column in both runs")

    source_work = source_summary[~_is_base_branch(source_summary)].copy()
    refined_work = refined_summary[~_is_base_branch(refined_summary)].copy()
    for frame in (source_work, refined_work):
        frame[score_col] = pd.to_numeric(frame[score_col], errors="coerce")
    source_work = source_work.dropna(subset=[score_col])
    refined_work = refined_work.dropna(subset=[score_col])
    if source_work.empty or refined_work.empty:
        return

    source_cols = common_match_cols + [score_col]
    refined_cols = common_match_cols + [score_col]
    optional_cols = [
        "token_rank",
        "token_probability",
        "token_surprisal",
        "normalized_token_entropy",
        "top1_top2_margin",
        "topology_regime",
    ]
    scale = normalization_scale_for_score(score_col)
    if scale:
        optional_cols += [f"{scale}_scaled_{kind}_forking_score" for kind in ("instant", "persistent", "progressive")]
    source_cols.extend([col for col in optional_cols if col in source_work.columns])
    refined_cols.extend([col for col in optional_cols if col in refined_work.columns])

    merged = source_work[source_cols].merge(
        refined_work[refined_cols],
        on=common_match_cols,
        how="inner",
        suffixes=("_source", "_refined"),
        validate="one_to_one",
    )
    if merged.empty:
        return

    merged["score_source"] = pd.to_numeric(merged[f"{score_col}_source"], errors="coerce")
    merged["score_refined"] = pd.to_numeric(merged[f"{score_col}_refined"], errors="coerce")
    merged["score_delta"] = merged["score_refined"] - merged["score_source"]
    merged["score_abs_delta"] = merged["score_delta"].abs()
    merged["score_relative_delta"] = (
        merged["score_delta"] / merged["score_source"].abs()
    ).where(merged["score_source"].abs() > 1e-12)

    research_dir = run_dir / "recherche"
    research_dir.mkdir(parents=True, exist_ok=True)
    save_dataframe(research_dir / "stability_branch_comparison.csv", merged)

    window_summary = (
        merged.groupby(WINDOW_KEY_COLS, dropna=False)
        .agg(
            matched_branches=("score_delta", "size"),
            source_max_score=("score_source", "max"),
            refined_max_score=("score_refined", "max"),
            mean_abs_score_delta=("score_abs_delta", "mean"),
            max_abs_score_delta=("score_abs_delta", "max"),
        )
        .reset_index()
    )
    window_summary["max_score_delta"] = (
        window_summary["refined_max_score"] - window_summary["source_max_score"]
    )
    save_dataframe(research_dir / "stability_window_summary.csv", window_summary)

    payload = {
        "score_column": score_col,
        "matched_branches": int(len(merged)),
        "matched_windows": int(len(window_summary)),
        "mean_abs_score_delta": float(merged["score_abs_delta"].mean()),
        "median_abs_score_delta": float(merged["score_abs_delta"].median()),
        "max_abs_score_delta": float(merged["score_abs_delta"].max()),
        "source_run": str(source_run),
        "refinement_run": str(run_dir),
    }
    save_json(research_dir / "stability_summary.json", payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rerun selected high-shift Chronos windows with denser token/step coverage."
    )
    add_config_argument(parser)
    add_trajectory_arguments(parser)
    parser.add_argument("--source-run", default="", help="Existing scan result folder used to select top windows.")
    parser.add_argument("--benchmark-folder", default="data/raw/chronos_benchmark")
    parser.add_argument("--model-id", default=DEFAULT_CHRONOS_MODEL_ID)
    parser.add_argument("--device", default=None)
    parser.add_argument("--dtype", default=None)
    parser.add_argument("--context-len", type=int, default=512)
    parser.add_argument("--horizon", type=int, default=64)
    parser.add_argument("--slide-step", type=int, default=None)
    parser.add_argument("--adaptive-context", action="store_true", default=True)
    parser.add_argument("--no-adaptive-context", action="store_false", dest="adaptive_context")
    parser.add_argument("--min-context-len", type=int, default=64)
    parser.add_argument("--branch-modes", default="single")
    parser.add_argument(
        "--refine-branch-steps",
        default="0,2,4,6,8,10,12,16",
        help="Dense branch-step list for targeted refinement.",
    )
    parser.add_argument("--refine-top-k", type=int, default=15)
    parser.add_argument("--num-samples", type=int, default=40)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--sample-top-k", type=int, default=50)
    parser.add_argument("--bad-base-threshold", type=float, default=1.0)
    parser.add_argument("--global-top-windows", type=int, default=20)
    parser.add_argument("--per-dataset-top-windows", type=int, default=5)
    parser.add_argument("--rank-score-column", default="")
    parser.add_argument("--output-root", default="result")
    parser.add_argument("--run-name", default="chronos_refinement")
    parser.add_argument("--resume-from", default="")
    parser.add_argument("--visualisation", action="store_true")
    parser.add_argument("--visualisation-top-n", type=int, default=50)
    parser.add_argument(
        "--visualisation-score-column",
        default="",
        help=(
            "Score column used in generated figures. Empty uses context_iqr; "
            "no automatic normalization fallback."
        ),
    )
    parser.add_argument("--checkpoint-every-branch-groups", type=int, default=1)
    parser.add_argument("--no-progress", action="store_true")
    return parser


def run_with_args(argv: list[str] | None = None, on_run_ready=None) -> Path:
    parser = build_parser()
    args, config_path, input_config, config_parameters = parse_run_configuration(parser, argv)
    validate_trajectory_arguments(args)

    if not args.source_run:
        raise ValueError("--source-run is required, either in CLI or in --config parameters.")
    if args.refine_top_k <= 0:
        raise ValueError("--refine-top-k must be positive.")
    if args.num_samples <= 0:
        raise ValueError("--num-samples must be positive.")
    if args.checkpoint_every_branch_groups < 0:
        raise ValueError("--checkpoint-every-branch-groups must be >= 0.")
    if args.global_top_windows < 0 or args.per_dataset_top_windows < 0:
        raise ValueError("Refinement selection counts must be nonnegative")

    source_run = Path(args.source_run)
    branch_steps = parse_int_list(args.refine_branch_steps)
    branch_modes = _parse_csv(args.branch_modes)
    if not branch_steps or not branch_modes or set(branch_modes) - {"single", "bundle"}:
        raise ValueError("Provide branch steps and modes drawn from single,bundle")
    sample_top_k = None if args.sample_top_k == 0 else args.sample_top_k
    rank_score_col = args.rank_score_column.strip() or None

    if args.resume_from:
        run_dir = Path(args.resume_from)
        if not run_dir.exists():
            raise FileNotFoundError(f"Cannot resume from missing folder: {run_dir}")
        print(f"Resuming targeted refinement in: {run_dir}")
    else:
        run_dir = make_run_dir(args.output_root, "chronos_refinement", run_name=args.run_name)
        print(f"Saving targeted refinement outputs to: {run_dir}")
    run_config_payload = input_config or {
        "description": "Generated from CLI arguments after parsing.",
        "parameters": vars(args),
    }
    if args.resume_from and (run_dir / "input_config.json").exists():
        save_json(run_dir / "resume_input_config_latest.json", run_config_payload)
    else:
        save_json(run_dir / "input_config.json", run_config_payload)

    prepare_run_state(run_dir, args, "refinement")
    store, existing_summary, completed_groups = start_store(run_dir, bool(args.resume_from))
    selected_path = run_dir / "selected_refinement_windows.csv"
    if args.resume_from and not selected_path.exists():
        raise ValueError("Missing frozen refinement selection; refusing to silently reselect targets")
    if args.resume_from and selected_path.exists() and selected_path.stat().st_size > 0:
        targets_df = _read_csv_if_exists(selected_path)
    else:
        targets_df = _select_target_windows(
            source_run=source_run,
            global_top_windows=args.global_top_windows,
            per_dataset_top_windows=args.per_dataset_top_windows,
            rank_score_col=rank_score_col,
        )
        save_dataframe(selected_path, targets_df)

    if on_run_ready is not None:
        on_run_ready(run_dir)

    target_keys = {_window_key_from_row(row) for row in targets_df.itertuples(index=False)}
    target_datasets = sorted(targets_df["dataset_name"].astype(str).unique())
    print(
        f"Selected {len(target_keys)} unique windows from {source_run} "
        f"({args.global_top_windows} global + {args.per_dataset_top_windows}/dataset policy)."
    )
    print(f"Refinement branch_steps={branch_steps}, top_k={args.refine_top_k}, samples={args.num_samples}")

    steps_path = run_dir / "chronos_scan_steps.csv"
    summary_path = run_dir / "chronos_scan_summary.csv"
    errors_path = run_dir / "chronos_scan_errors.csv"
    completed_windows = _completed_window_keys_from_targets(
        targets_df,
        completed_groups=completed_groups,
        branch_steps=branch_steps,
        branch_modes=branch_modes,
        bundle_size=3,
    )
    if args.resume_from:
        print(
            "Resume state: "
            f"{len(completed_groups)} completed branch groups, "
            f"{len(completed_windows)} completed target windows."
        )
    checkpoint_counter = 0

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
                    "dataset_name": window.dataset_name,
                    "series_id": window.series_id,
                    "window_id": window.window_id,
                    "branch_mode": branch_mode,
                    "branch_step": branch_step,
                },
            )

    model, tokenizer, chronos_config = load_chronos_t5_raw(
        model_id=args.model_id,
        device=args.device,
        dtype=args.dtype,
    )
    if args.resume_from:
        store.restore_rng()

    trajectory_options = trajectory_options_from_args(args, run_dir, model, chronos_config)

    found_windows = set()
    for series in iter_benchmark_folder_series(
        args.benchmark_folder,
        dataset_names=target_datasets,
        max_datasets=None,
        max_series_per_dataset=None,
        min_length=args.min_context_len + args.horizon if args.adaptive_context else args.context_len + args.horizon,
    ):
        for window in iter_sliding_windows(
            series,
            context_len=args.context_len,
            horizon=args.horizon,
            slide_step=args.slide_step,
            max_windows_per_series=None,
            adaptive_context=args.adaptive_context,
            min_context_len=args.min_context_len,
        ):
            key = _window_key(window)
            if key not in target_keys:
                continue
            found_windows.add(key)
            expected = _expected_group_keys(
                window,
                branch_steps=branch_steps,
                branch_modes=branch_modes,
                bundle_size=3,
            )
            missing = expected.difference(completed_groups)
            if not missing:
                completed_windows.add(key)
                continue

            try:
                print(
                    "Refining "
                    f"{window.dataset_name}/{window.series_id} "
                    f"window={window.window_id} start={window.window_start}"
                )
                scan_window(
                    model=model,
                    tokenizer=tokenizer,
                    chronos_config=chronos_config,
                    window=window,
                    branch_steps=branch_steps,
                    branch_modes=branch_modes,
                    top_k=args.refine_top_k,
                    trajectory_options=trajectory_options,
                    bundle_size=3,
                    bundle_continuation_ranks=DEFAULT_BUNDLE_CONTINUATION_RANKS,
                    num_samples=args.num_samples,
                    temperature=args.temperature,
                    sample_top_k=sample_top_k,
                    bad_base_threshold=args.bad_base_threshold,
                    show_progress=not args.no_progress,
                    completed_branch_groups={
                        (group[-2], int(group[-1]))
                        for group in completed_groups
                        if group[: len(WINDOW_KEY_COLS)] == key
                    },
                    checkpoint_callback=checkpoint_callback,
                )
                if expected.issubset(completed_groups):
                    completed_windows.add(key)
            except Exception as exc:
                _append_dataframe(
                    errors_path,
                    pd.DataFrame(
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
                    ),
                )

            if found_windows == target_keys:
                break
        if found_windows == target_keys:
            break

    summary_df, completed_groups = store.recover()
    completed_windows = _completed_window_keys_from_targets(targets_df, completed_groups, branch_steps, branch_modes, 3)
    steps_df = _read_csv_if_exists(steps_path)
    ranking_df = rank_scan_summary(summary_df, rank_col=rank_score_col)
    errors_df = _read_csv_if_exists(errors_path)
    missing_windows = sorted(target_keys.difference(found_windows))

    save_dataframe(run_dir / "chronos_scan_steps.csv", steps_df)
    save_dataframe(run_dir / "chronos_scan_summary.csv", summary_df)
    save_dataframe(run_dir / "chronos_scan_ranking.csv", ranking_df)
    save_dataframe(run_dir / "chronos_scan_errors.csv", errors_df)
    save_dataframe(run_dir / "missing_refinement_windows.csv", pd.DataFrame(missing_windows, columns=WINDOW_KEY_COLS))
    save_json(
        run_dir / "config.json",
        {
            "args": vars(args),
            "config_path": str(config_path) if config_path else "",
            "config_parameters": config_parameters,
            "source_run": str(source_run),
            "selected_windows": len(target_keys),
            "found_windows": len(found_windows),
            "completed_windows": len(completed_windows),
            "completed_branch_groups": len(completed_groups),
            "refine_branch_steps": branch_steps,
            "branch_modes": branch_modes,
            "refine_top_k": args.refine_top_k,
            "num_samples": args.num_samples,
            "sample_top_k_resolved": sample_top_k,
            "rank_score_column": resolve_score_column(summary_df, rank_score_col),
            "automatic_scale_fallback": False,
        },
    )
    resolved_score_column = resolve_score_column(summary_df, rank_score_col)
    _write_stability_reports(source_run, run_dir, resolved_score_column)
    _write_checkpoint(
        run_dir,
        status="complete" if completed_windows == target_keys else "partial",
        completed_groups=completed_groups,
        completed_windows=completed_windows,
        last_event={
            "found_windows": len(found_windows),
            "missing_windows": len(missing_windows),
        },
    )

    if args.visualisation:
        plot_chronos_scan_outputs(
            run_dir,
            top_n=args.visualisation_top_n,
            score_col=args.visualisation_score_column or None,
        )

    print("\nTargeted refinement complete.")
    print(f"Found windows: {len(found_windows)} / {len(target_keys)}")
    if missing_windows:
        print("Some selected windows were not found; see missing_refinement_windows.csv.")
    print(f"Saved results to: {run_dir}")
    return run_dir


def run() -> None:
    run_with_args()


if __name__ == "__main__":
    run()



