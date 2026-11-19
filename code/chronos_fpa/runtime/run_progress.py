"""Common progress bookkeeping for scans and targeted refinements."""
from datetime import datetime
import subprocess

from research_schema import GROUP_KEY_COLS, SCHEMA_VERSION, WINDOW_KEY_COLS, expected_group_keys
from results_io import save_json


def completed_windows_from_frame(frame, completed_groups, branch_steps, branch_modes, bundle_size):
    from types import SimpleNamespace
    completed = set()
    if frame.empty:
        return completed
    for values in frame[WINDOW_KEY_COLS].drop_duplicates().to_dict("records"):
        expected = expected_group_keys(SimpleNamespace(**values), branch_steps, branch_modes, bundle_size)
        if expected and expected.issubset(completed_groups):
            completed.add(next(iter(expected))[:len(WINDOW_KEY_COLS)])
    return completed


def write_checkpoint(run_dir, status, completed_groups, completed_windows, last_event=None):
    import json
    with (run_dir / "run_state.json").open(encoding="utf-8") as stream:
        kind = json.load(stream)["kind"]
    script = "run_chronos_targeted_refinement.py" if kind == "refinement" else "run_chronos_benchmark_scan.py"
    save_json(run_dir / "checkpoint.json", {
        "schema_version": SCHEMA_VERSION,
        "status": status, "updated_at": datetime.now().isoformat(timespec="seconds"),
        "completed_branch_groups": len(completed_groups), "completed_windows": len(completed_windows),
        "last_event": last_event or {},
        "resume_command_hint": subprocess.list2cmdline([
            ".\\.venv\\Scripts\\python.exe", f"scripts\\runs\\{script}", "--resume-from", str(run_dir),
        ]),
    })


def unresolved_errors(errors, completed_windows):
    """Keep the error history, but do not let resolved attempts block completion."""
    if errors.empty:
        return errors
    from types import SimpleNamespace
    from research_schema import window_key
    return errors.loc[
        [window_key(SimpleNamespace(**row)) not in completed_windows for row in errors.to_dict("records")]
    ]
