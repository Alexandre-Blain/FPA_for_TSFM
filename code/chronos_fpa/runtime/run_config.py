from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def add_config_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default="",
        help=(
            "JSON config file. Values under the 'parameters' object become "
            "CLI defaults; explicit CLI arguments still override them."
        ),
    )


def apply_json_config_defaults(
    parser: argparse.ArgumentParser,
    argv: list[str] | None = None,
) -> tuple[Path | None, dict[str, Any], dict[str, Any]]:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", default="")
    pre_args, _ = pre_parser.parse_known_args(argv)
    if not pre_args.config:
        return None, {}, {}

    config_path = Path(pre_args.config)
    with config_path.open("r", encoding="utf-8-sig") as handle:
        raw_config = json.load(handle)

    if not isinstance(raw_config, dict):
        raise ValueError(f"Config file must contain a JSON object: {config_path}")

    parameters = raw_config.get("parameters", raw_config)
    if not isinstance(parameters, dict):
        raise ValueError(
            "Config file must either be a flat object or contain a 'parameters' object."
        )

    valid_dests = {
        action.dest
        for action in parser._actions
        if action.dest is not argparse.SUPPRESS
    }
    unknown = sorted(set(parameters).difference(valid_dests))
    if unknown:
        raise ValueError(
            f"Unknown config parameter(s) in {config_path}: {unknown}. "
            "Use argparse destination names, for example 'num_samples' for --num-samples."
        )

    parser.set_defaults(**parameters)
    return config_path, raw_config, parameters.copy()


MUTABLE_RUN_OPTIONS = {
    "config", "resume_from", "no_progress", "visualisation", "visualisation_top_n",
    "visualisation_score_column", "checkpoint_every_branch_groups",
    "refinement_visualisation", "refinement_resume_from", "refinement_output_root",
}


def parse_run_configuration(parser: argparse.ArgumentParser, argv=None):
    """Restore saved defaults before parsing overrides, rejecting mixed experiments."""
    config_path, payload, parameters = apply_json_config_defaults(parser, argv)
    preliminary = parser.parse_args(argv)
    if preliminary.resume_from:
        state_path = Path(preliminary.resume_from) / "run_state.json"
        if not state_path.exists():
            raise ValueError("CSV-only historical checkpoint: audit it first; in-place migration is disabled.")
        with state_path.open(encoding="utf-8") as stream:
            state = json.load(stream)
        from research_schema import SCHEMA_VERSION
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported checkpoint schema; original run was not modified.")
        from chronos_scales import SCORE_CONVENTIONS
        if "metric_conventions" in state and state["metric_conventions"] != SCORE_CONVENTIONS:
            raise ValueError("Metric conventions changed; start a new run instead of mixing definitions.")
        saved = state["args"]
        # JSON and explicitly supplied CLI options still apply, but cannot alter
        # scientific settings while appending to the same experiment.
        parser.set_defaults(**saved)
        parser.set_defaults(**parameters)
        parser.set_defaults(resume_from=preliminary.resume_from)
        args = parser.parse_args(argv)
        changes = {
            key: (saved[key], value) for key, value in vars(args).items()
            if key in saved and key not in MUTABLE_RUN_OPTIONS and value != saved[key]
        }
        if changes:
            raise ValueError(f"Incompatible resume parameters: {changes}. Start a new run instead.")
    else:
        args = preliminary
    return args, config_path, payload, parameters


def prepare_run_state(run_dir: Path, args, kind: str) -> None:
    from research_schema import ANALYSIS_VERSION, SCHEMA_VERSION
    from results_io import save_json
    from chronos_scales import SCORE_CONVENTIONS
    state_path = run_dir / "run_state.json"
    if state_path.exists():
        with state_path.open(encoding="utf-8") as stream:
            saved = json.load(stream)
        if saved.get("kind") != kind:
            raise ValueError("Cannot resume a different run type in this directory")
        return
    save_json(state_path, {
        "schema_version": SCHEMA_VERSION, "analysis_version": ANALYSIS_VERSION,
        "metric_conventions": SCORE_CONVENTIONS,
        "kind": kind, "args": vars(args),
    })


