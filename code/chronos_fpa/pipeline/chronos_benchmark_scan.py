from __future__ import annotations

from typing import Callable, Iterable, Optional

import pandas as pd

from chronos_analysis import (
    analyze_chronos_named_branches,
    analyze_chronos_token_branches,
    summarize_chronos_branches,
    summarize_chronos_named_branches,
)
from chronos_data import (
    WindowRecord,
    iter_benchmark_folder_series,
    iter_csv_folder_series,
    iter_sliding_windows,
    parse_int_list,
)
# Preserve the public scan-module imports used by existing scripts.
from chronos_scales import (
    DEFAULT_BRANCH_STEPS,
    DEFAULT_BUNDLE_CONTINUATION_RANKS,
    NORMALIZED_SCORE_COL,
    RAW_SCORE_COL,
    _attach_base_forecast_bad,
    _attach_base_quality,
    _attach_normalized_branch_scores,
    _attach_temporal_forking_scores,
    _attach_topology_regime,
    compute_base_forecast_quality,
    resolve_score_column,
)


def _add_window_metadata(frame: pd.DataFrame, window: WindowRecord, branch_mode: str) -> pd.DataFrame:
    out = frame.copy()
    out.insert(0, "branch_mode", branch_mode)
    out.insert(0, "horizon", window.horizon)
    out.insert(0, "context_len", window.context_len)
    out.insert(0, "window_start", window.window_start)
    out.insert(0, "window_id", window.window_id)
    out.insert(0, "series_id", window.series_id)
    out.insert(0, "dataset_name", window.dataset_name)
    out.insert(0, "source", window.source)
    return out


def _analyze_group(decoded, window, mode, bad_base_threshold):
    analyze, summarize = (
        (analyze_chronos_token_branches, summarize_chronos_branches)
        if mode == "single" else
        (analyze_chronos_named_branches, summarize_chronos_named_branches)
    )
    steps = analyze(decoded)
    summary = summarize(steps)
    quality = compute_base_forecast_quality(
        decoded["base_values"], window.future, context_values=window.context,
    )
    summary = _attach_base_quality(summary, quality)
    summary = _attach_normalized_branch_scores(summary)
    summary = _attach_temporal_forking_scores(summary)
    summary = _attach_topology_regime(summary)
    summary = _attach_base_forecast_bad(summary, bad_base_threshold)
    return _add_window_metadata(steps, window, mode), _add_window_metadata(summary, window, mode)


def scan_window(
    model,
    tokenizer,
    chronos_config,
    window: WindowRecord,
    branch_steps: Iterable[int] = DEFAULT_BRANCH_STEPS,
    branch_modes: Iterable[str] = ("single", "bundle"),
    top_k: int = 5,
    bundle_size: int = 3,
    bundle_continuation_ranks: Iterable[int] = DEFAULT_BUNDLE_CONTINUATION_RANKS,
    num_samples: int = 30,
    temperature: float = 1.0,
    sample_top_k: Optional[int] = 50,
    bad_base_threshold: float = 1.0,
    show_progress: bool = False,
    completed_branch_groups: Optional[set[tuple[str, int]]] = None,
    checkpoint_callback: Optional[
        Callable[[pd.DataFrame, pd.DataFrame, WindowRecord, str, int], None]
    ] = None,
    trajectory_options: Optional[dict] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run Chronos FPA branch scans for one context/future window."""
    from chronos_decoding import (
        decode_with_token_bin_intervention,
        decode_with_token_bundle_intervention,
    )
    from chronos_io import prepare_chronos_context

    context = prepare_chronos_context(window.context, device="cpu")
    step_frames, summary_frames = [], []
    branch_modes = set(branch_modes)
    if not branch_modes or branch_modes - {"single", "bundle"}:
        raise ValueError("Branch modes must be drawn from single,bundle")
    if trajectory_options is not None and branch_modes != {"single"}:
        raise ValueError("Strict-suffix trajectory metrics currently support single branches only")
    completed_branch_groups = completed_branch_groups or set()

    for branch_step in branch_steps:
        if branch_step < 0 or branch_step >= window.horizon:
            continue

        if "single" in branch_modes and ("single", branch_step) not in completed_branch_groups:
            extra = {}
            if trajectory_options is not None:
                from trajectory_export import fork_namespace
                extra = {"sampling_seed": trajectory_options["sampling_seed"], "rng_namespace": fork_namespace(window)}
            decode_out = decode_with_token_bin_intervention(
                model=model,
                tokenizer=tokenizer,
                chronos_config=chronos_config,
                context=context,
                prediction_length=window.horizon,
                branch_step=branch_step,
                top_k=top_k,
                num_samples=num_samples,
                temperature=temperature,
                sample_top_k=sample_top_k,
                include_base_token_branch=True,
                show_progress=show_progress,
                **extra,
            )
            step_df, summary_df = _analyze_group(decode_out, window, "single", bad_base_threshold)
            if trajectory_options is not None:
                from chronos_distances import attach_sampled_fork_metrics
                from trajectory_export import save_fork_ensembles
                step_df, summary_df = attach_sampled_fork_metrics(decode_out, step_df, summary_df, window.context)
                reference = decode_out["branches"][decode_out["base_token_at_branch"]]
                summary_df["reference_rng_stream_id"] = reference["rng"]["stream_id"]
                summary_df["same_token_null_rng_stream_id"] = decode_out["same_token_null"]["rng"]["stream_id"]
                summary_df["ensemble_rng_stream_id"] = summary_df.token_id.map({
                    token: entry["rng"]["stream_id"] for token, entry in decode_out["branches"].items()
                })
                if trajectory_options.get("output_dir") is not None:
                    from pathlib import Path
                    directory = Path(trajectory_options["output_dir"])
                    manifest = save_fork_ensembles(directory, decode_out, window, trajectory_options.get("provenance", {}))
                    summary_df["trajectory_manifest"] = str(manifest.relative_to(directory.parent)).replace("\\", "/")
            step_frames.append(step_df)
            summary_frames.append(summary_df)
            if checkpoint_callback is not None:
                checkpoint_callback(step_df, summary_df, window, "single", branch_step)

        if (
            "bundle" in branch_modes
            and branch_step + bundle_size <= window.horizon
            and ("bundle", branch_step) not in completed_branch_groups
        ):
            decode_out = decode_with_token_bundle_intervention(
                model=model,
                tokenizer=tokenizer,
                chronos_config=chronos_config,
                context=context,
                prediction_length=window.horizon,
                branch_step=branch_step,
                initial_top_k=top_k,
                bundle_size=bundle_size,
                continuation_ranks=bundle_continuation_ranks,
                num_samples=num_samples,
                temperature=temperature,
                sample_top_k=sample_top_k,
                include_base_branch=True,
                show_progress=show_progress,
            )
            step_df, summary_df = _analyze_group(decode_out, window, "bundle", bad_base_threshold)
            step_frames.append(step_df)
            summary_frames.append(summary_df)
            if checkpoint_callback is not None:
                checkpoint_callback(step_df, summary_df, window, "bundle", branch_step)

    if step_frames:
        all_steps = pd.concat(step_frames, ignore_index=True)
    else:
        all_steps = pd.DataFrame()
    if summary_frames:
        all_summary = pd.concat(summary_frames, ignore_index=True)
    else:
        all_summary = pd.DataFrame()
    return all_steps, all_summary


def rank_scan_summary(summary_df: pd.DataFrame, rank_col: Optional[str] = None) -> pd.DataFrame:
    if summary_df.empty:
        return summary_df
    rank_col = resolve_score_column(summary_df, rank_col)
    return summary_df.sort_values(rank_col, ascending=False).reset_index(drop=True)


