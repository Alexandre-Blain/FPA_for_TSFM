"""Read-only research inventory. Never import inference, plotting or store writers."""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "code" / "chronos_fpa"))
import bootstrap  # noqa: E402,F401
from research_schema import GROUP_KEY_COLS, TEXT_COLUMNS, WINDOW_KEY_COLS, read_csv  # noqa: E402

ARTIFACTS = {
    "config.json", "input_config.json", "run_state.json", "checkpoint.json",
    "chronos_scan_summary.csv", "chronos_scan_steps.csv", "selected_refinement_windows.csv",
}
LIMITS = [
    "Inventory only: no inference, analysis regeneration, source repair, migration or deletion.",
    "Completion is relative to recorded settings and available local data, not scientific usefulness.",
    "Partial runs may retain useful observations; integrity and completion are separate assessments.",
    "Current source identifiers, bounds and finite values do not prove original dataset provenance or predictive validity.",
    "Historical figures have a potential series_id numeric-conversion risk. No figure is declared wrong without individual verification.",
    "branch_groups is excluded from run discovery and table validation; committed store integrity is not certified.",
    "Step CSVs use a strict streaming csv reader equivalent to the schema width contract; smaller tables use research_schema.read_csv.",
    "Expected branch counts are not reconstructed from top_k: forced-base and bundle choices may vary. Observed branches are paired across tables.",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def within(path, parent):
    return path == parent or parent in path.parents


def walk_files(root, exclude_groups=False):
    """Do not follow directory links; store records are optionally pruned."""
    def fail(error):
        raise error
    for directory, names, files in os.walk(root, followlinks=False, onerror=fail):
        names[:] = sorted(n for n in names if not (exclude_groups and n == "branch_groups"))
        for name in sorted(files):
            yield Path(directory) / name


def discover_runs(root):
    return sorted({p.parent for p in walk_files(root, True) if p.name in ARTIFACTS})


def issue(run, code, message, **detail):
    run["issues"].append({"code": code, "message": message, **detail})


def integer(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError("not a finite integer")
        return int(number)
    except (InvalidOperation, TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"Invalid integer identifier: {value!r}") from error


def key(row, columns):
    values = []
    for col in columns:
        value = row.get(col)
        if col in TEXT_COLUMNS:
            if value is None or str(value).strip().lower() in {"", "nan", "<na>", "none", "null"}:
                raise ValueError(f"Missing text identifier {col}")
            values.append(str(value))
        else:
            values.append(integer(value))
    result = tuple(values)
    if "horizon" in columns and result[columns.index("horizon")] <= 0:
        raise ValueError("Nonpositive horizon")
    for col in ("window_id", "window_start", "branch_step"):
        if col in columns and result[columns.index(col)] < 0:
            raise ValueError(f"Negative {col}")
    if "context_len" in columns and result[columns.index("context_len")] <= 0:
        raise ValueError("Nonpositive context length")
    if "branch_step" in columns and integer(row["branch_step"]) >= integer(row["horizon"]):
        raise ValueError("branch_step outside horizon")
    return result


def branch_key(row):
    group = key(row, GROUP_KEY_COLS)
    mode = row["branch_mode"]
    if mode not in {"single", "bundle"}:
        raise ValueError(f"Unknown branch_mode {mode!r}")
    identity = "token_id" if mode == "single" else "branch_id"
    return group + key(row, [identity])


def load_json(path, run):
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8-sig") as stream:
            value = json.load(stream)
        if not isinstance(value, dict):
            raise ValueError("Expected an object")
        return value
    except (OSError, UnicodeError, ValueError) as error:
        issue(run, "unreadable_json", str(error), file=path.name)
        return None


def load_table(path, run):
    if not path.exists():
        run["tables"][path.name] = {"exists": False, "rows": 0, "rejected_count": 0, "rejected_rows": []}
        return []
    try:
        # Recovery is explicitly restricted to this audit, never the experiment readers.
        frame = read_csv(path, recover=True)
        rejected = frame.attrs.get("excluded_rows", [])
        run["tables"][path.name] = {
            "exists": True, "rows": len(frame), "columns": list(frame.columns),
            "rejected_count": len(rejected), "rejected_rows": rejected,
        }
        if rejected:
            issue(run, "rejected_csv_rows", "Ragged records excluded from audit view only; source preserved.",
                  file=path.name, count=len(rejected), lines=[r["line"] for r in rejected])
        return frame.to_dict("records")
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        issue(run, "unreadable_csv", str(error), file=path.name)
        run["tables"][path.name] = {"exists": True, "error": str(error), "rows": 0}
        return []


def configuration(directory, run):
    documents = {name: load_json(directory / name, run) for name in
                 ("input_config.json", "config.json", "run_state.json", "checkpoint.json")}
    args = {}
    origin = None
    for name in ("input_config.json", "config.json", "run_state.json"):
        payload = documents[name]
        if payload is None:
            continue
        settings = payload.get("args", payload.get("parameters", payload))
        if not isinstance(settings, dict):
            issue(run, "invalid_settings", "Expected an args/parameters object.", file=name)
            continue
        args.update(settings)
        origin = name
    run["configuration"] = {"settings_source": origin, "settings": args,
                            "documents": documents}
    return args, documents


def comma_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return list(value)


def expected_groups(windows, settings):
    steps = comma_list(settings.get("refine_branch_steps", settings.get("branch_steps")))
    modes = comma_list(settings.get("branch_modes"))
    if not steps or not modes:
        return None
    if not set(modes) <= {"single", "bundle"}:
        raise ValueError("Unsupported configured branch mode")
    bundle_size = integer(settings.get("bundle_size", 3))
    if bundle_size <= 0:
        raise ValueError("Nonpositive bundle_size")
    return {window + (mode, integer(step)) for window in windows
            for mode in modes for step in steps if 0 <= integer(step) < window[6]
            and (mode == "single" or integer(step) + bundle_size <= window[6])}


def stream_steps(path, run):
    """Retain branch/step bitmaps, not the potentially large forecast table."""
    branches = {}
    detail = {"exists": path.exists(), "rows": 0, "rejected_count": 0, "rejected_rows": [],
              "invalid_identifier_count": 0, "invalid_identifier_examples": [],
              "duplicate_step_count": 0, "invalid_step_count": 0,
              "relative_step_mismatch_count": 0, "nonfinite_value_count": 0}
    run["tables"][path.name] = detail
    if not path.exists() or not path.stat().st_size:
        return branches
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            header = next(reader, [])
            detail["columns"] = header
            if len(set(header)) != len(header):
                raise ValueError("Duplicate CSV columns")
            required = set(GROUP_KEY_COLS + ["forecast_step"])
            if not required.issubset(header):
                raise ValueError(f"Missing step identifiers: {sorted(required - set(header))}")
            for values in reader:
                if not values:
                    continue
                if len(values) != len(header):
                    detail["rejected_rows"].append({"line": reader.line_num, "fields": len(values),
                                                    "expected_fields": len(header)})
                    continue
                detail["rows"] += 1
                row = dict(zip(header, values))
                try:
                    identity = branch_key(row)
                    step = integer(row["forecast_step"])
                except (KeyError, ValueError) as error:
                    detail["invalid_identifier_count"] += 1
                    if len(detail["invalid_identifier_examples"]) < 10:
                        detail["invalid_identifier_examples"].append({"line": reader.line_num, "error": str(error)})
                    continue
                state = branches.setdefault(identity, {"mask": 0, "rows": 0})
                state["rows"] += 1
                horizon = identity[6]
                # Avoid allocating an enormous bitmap from an out-of-range corrupted step.
                if not 0 <= step < horizon:
                    detail["invalid_step_count"] += 1
                    continue
                bit = 1 << step
                if state["mask"] & bit:
                    detail["duplicate_step_count"] += 1
                state["mask"] |= bit
                if row.get("relative_step_after_branch", "") != "":
                    try:
                        if integer(row["relative_step_after_branch"]) != step - identity[8]:
                            detail["relative_step_mismatch_count"] += 1
                    except ValueError:
                        detail["relative_step_mismatch_count"] += 1
                for column in ("law_shift_h", "base_q10", "base_q50", "base_q90", "branch_q10", "branch_q50", "branch_q90"):
                    if column in row:
                        try:
                            if not math.isfinite(float(row[column])):
                                raise ValueError("Nonfinite")
                        except (TypeError, ValueError, OverflowError):
                            detail["nonfinite_value_count"] += 1
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        detail["error"] = str(error)
        issue(run, "unreadable_steps", str(error), file=path.name,
              line=reader.line_num if "reader" in locals() else None)
    detail["rejected_count"] = len(detail["rejected_rows"])
    for name in ("rejected_count", "invalid_identifier_count", "duplicate_step_count", "invalid_step_count",
                 "relative_step_mismatch_count", "nonfinite_value_count"):
        if detail[name]:
            issue(run, name, "Strict streaming step-table validation found anomalies.",
                  file=path.name, count=detail[name])
    return branches


class DataInventory:
    """Read JSONL once per folder, retaining identifiers, lengths and invalid positions."""

    def __init__(self):
        self.cache = {}

    def get(self, folder):
        if folder in self.cache:
            return self.cache[folder]
        records, errors = [], []
        paths = sorted(folder.glob("*.jsonl")) if folder.is_dir() else []
        for path in paths:
            try:
                with path.open(encoding="utf-8-sig") as stream:
                    for line_number, line in enumerate(stream, 1):
                        if not line.strip():
                            continue
                        try:
                            row = json.loads(line)
                            if not isinstance(row, dict):
                                raise ValueError("Expected a JSONL object")
                            # Never derive scientific identity or validity from a directory/filename.
                            identity = key({"source": row.get("source_repo"),
                                            "dataset_name": row.get("dataset_name"),
                                            "series_id": row.get("series_id")}, WINDOW_KEY_COLS[:3])
                            target = row["target"]
                            if not isinstance(target, list):
                                raise ValueError("target must be an array")
                            bad = []
                            for index, value in enumerate(target):
                                try:
                                    if value is None or not math.isfinite(float(value)):
                                        bad.append(index)
                                except (TypeError, ValueError, OverflowError):
                                    bad.append(index)
                            records.append({"identity": identity, "length": len(target), "bad": bad})
                        except (KeyError, TypeError, ValueError) as error:
                            errors.append({"file": str(path), "line": line_number, "error": str(error)})
            except (OSError, UnicodeError) as error:
                errors.append({"file": str(path), "error": str(error)})
        result = {"records": records, "errors": errors, "file_count": len(paths),
                  "usable": bool(paths) and not errors}
        self.cache[folder] = result
        return result


def resolve_path(value):
    path = Path(str(value).replace("\\", "/"))
    return (path if path.is_absolute() else ROOT / path).resolve()


def scan_windows(records, settings):
    """Mirror local loader/window eligibility, without running a forecast."""
    required = {"context_len", "horizon", "adaptive_context", "min_context_len"}
    if not required.issubset(settings):
        return None
    context = integer(settings["context_len"])
    horizon = integer(settings["horizon"])
    minimum = integer(settings["min_context_len"])
    stride = integer(settings.get("slide_step") or max(1, horizon // 2))
    if min(context, horizon, minimum, stride) <= 0:
        raise ValueError("Nonpositive window setting")
    requested = set(comma_list(settings.get("datasets")))
    datasets, counts, windows = set(), Counter(), set()
    for record in records:
        source, dataset, series = record["identity"]
        if requested and dataset not in requested:
            continue
        length = record["length"]
        if length < (minimum if settings["adaptive_context"] else context) + horizon:
            continue
        if dataset not in datasets and settings.get("max_datasets") is not None and len(datasets) >= integer(settings["max_datasets"]):
            continue
        datasets.add(dataset)
        if settings.get("max_series_per_dataset") is not None and counts[dataset] >= integer(settings["max_series_per_dataset"]):
            continue
        counts[dataset] += 1
        effective_context = min(context, length - horizon) if settings["adaptive_context"] else context
        for index, start in enumerate(range(0, length - effective_context - horizon + 1, stride)):
            if settings.get("max_windows_per_series") is not None and index >= integer(settings["max_windows_per_series"]):
                break
            if settings.get("max_total_windows") is not None and len(windows) >= integer(settings["max_total_windows"]):
                return windows
            windows.add((source, dataset, series, index, start, effective_context, horizon))
    return windows


def coverage(run, settings, observed, selected, inventory, override):
    value = override or settings.get("benchmark_folder")
    result = {"status": "indeterminate", "recorded_benchmark_folder": settings.get("benchmark_folder"),
              "explicit_override": str(override) if override else None,
              "observed_windows": len(observed), "observed_series": len({w[:3] for w in observed}),
              "observed_datasets": sorted({w[1] for w in observed})}
    if not value or settings.get("source", "benchmark-folder") != "benchmark-folder":
        result["reason"] = "No supported benchmark JSONL reference; CSV-folder source validation is not implemented."
        return result, selected
    folder = resolve_path(value)
    result["checked_folder"] = str(folder)
    data = inventory.get(folder)
    result["source_file_count"] = data["file_count"]
    result["source_errors"] = data["errors"]
    if not data["usable"]:
        result["reason"] = "Source folder missing, empty or not fully readable; no validity inferred from its name."
        return result, selected
    by_id = defaultdict(list)
    for record in data["records"]:
        by_id[record["identity"]].append(record)
    missing, ambiguous, out_of_bounds, nonfinite = [], [], [], []
    for window in sorted(observed | (selected or set())):
        matches = by_id.get(window[:3], [])
        if not matches:
            missing.append(window)
        elif len(matches) != 1:
            ambiguous.append(window)
        elif window[4] + window[5] + window[6] > matches[0]["length"]:
            out_of_bounds.append(window)
        elif any(window[4] <= index < window[4] + window[5] + window[6] for index in matches[0]["bad"]):
            nonfinite.append(window)
    result.update(missing_series_windows=missing, ambiguous_series_windows=ambiguous,
                  out_of_bounds_windows=out_of_bounds, nonfinite_windows=nonfinite)
    for code, values in (("identifier_not_found_in_current_data", missing), ("ambiguous_source_identifier", ambiguous),
                         ("window_out_of_bounds", out_of_bounds), ("nonfinite_source_window", nonfinite)):
        if values:
            issue(run, code, "Mismatch against current explicitly identified local source records, not proof about original data.",
                  count=len(values), examples=values[:10])
    expected = selected if selected is not None else scan_windows(data["records"], settings)
    if expected is not None:
        result.update(expected_windows=len(expected), missing_windows=sorted(expected - observed),
                      unexpected_windows=sorted(observed - expected))
    requested_datasets = set(comma_list(settings.get("datasets")))
    available_datasets = {record["identity"][1] for record in data["records"]}
    result["requested_datasets_without_records"] = sorted(requested_datasets - available_datasets)
    if missing or ambiguous or out_of_bounds or nonfinite or (expected is not None and observed - expected):
        result["status"] = "inconsistent"
    elif expected is not None and (expected - observed or requested_datasets - available_datasets):
        result["status"] = "partial"
    elif expected:
        result["status"] = "completed"
    return result, expected


def keyed_rows(rows, columns, run, table):
    found = set()
    invalid = []
    duplicates = 0
    for number, row in enumerate(rows, 1):
        try:
            identity = branch_key(row) if columns == "branch" else key(row, columns)
            duplicates += identity in found
            found.add(identity)
        except (KeyError, ValueError) as error:
            invalid.append({"accepted_row": number, "error": str(error)})
    if invalid:
        issue(run, "invalid_identifiers", "Missing or broken identifiers; no synthetic identity substituted.",
              file=table, count=len(invalid), examples=invalid[:10])
    if duplicates:
        issue(run, "duplicate_summary_branches" if columns == "branch" else "duplicate_selected_windows",
              "Duplicate logical identities.", file=table, count=duplicates)
    return found


def audit_run(directory, result_root, inventory, benchmark_folder=None):
    run = {"path": directory.relative_to(result_root).as_posix(), "issues": [], "tables": {}}
    settings, documents = configuration(directory, run)
    summary = load_table(directory / "chronos_scan_summary.csv", run)
    summaries = keyed_rows(summary, "branch", run, "chronos_scan_summary.csv")
    step_branches = stream_steps(directory / "chronos_scan_steps.csv", run)
    selected_path = directory / "selected_refinement_windows.csv"
    selected_rows = load_table(selected_path, run)
    selected = keyed_rows(selected_rows, WINDOW_KEY_COLS, run, selected_path.name) if selected_path.exists() else None
    error_rows = load_table(directory / "chronos_scan_errors.csv", run)
    missing_recorded = load_table(directory / "missing_refinement_windows.csv", run)
    run["recorded_error_rows"] = len(error_rows)
    run["recorded_missing_refinement_rows"] = len(missing_recorded)
    observed = {branch[:7] for branch in summaries | set(step_branches)}
    groups = {branch[:9] for branch in summaries}
    missing_steps = summaries - set(step_branches)
    missing_summary = set(step_branches) - summaries
    incomplete_horizons = []
    for branch, state in step_branches.items():
        # bit_count alone is safe because out-of-range steps were excluded above.
        if state["mask"].bit_count() != branch[6]:
            incomplete_horizons.append({"branch": branch, "expected_steps": branch[6],
                                        "observed_unique_steps": state["mask"].bit_count()})
    run["pairing"] = {"summary_branches": len(summaries), "step_branches": len(step_branches),
                      "summary_without_steps": sorted(missing_steps), "steps_without_summary": sorted(missing_summary),
                      "incomplete_horizons": incomplete_horizons}
    for code, values in (("summary_without_steps", missing_steps), ("steps_without_summary", missing_summary),
                         ("incomplete_branch_horizon", incomplete_horizons)):
        if values:
            issue(run, code, "Paired branch/horizon records are missing.", count=len(values))
    if selected is not None:
        run["selection"] = {"selected_windows": len(selected), "actual_windows": len(observed),
                            "selected_not_observed": sorted(selected - observed),
                            "observed_not_selected": sorted(observed - selected)}
        if observed - selected:
            issue(run, "selected_actual_window_mismatch", "Actual windows do not match the full selected target identities.",
                  count=len(observed - selected), examples=sorted(observed - selected)[:10])
    try:
        run["data_coverage"], expected = coverage(run, settings, observed, selected, inventory, benchmark_folder)
        expected_on_observed = expected_groups(observed, settings)
        expected_all = expected_groups(expected, settings) if expected is not None else None
    except (TypeError, ValueError) as error:
        issue(run, "invalid_configuration", str(error))
        run["data_coverage"] = {"status": "indeterminate", "reason": str(error)}
        expected, expected_on_observed, expected_all = None, None, None
    if expected_on_observed is not None and groups - expected_on_observed:
        issue(run, "unexpected_branch_groups", "Observed groups contradict recorded branch settings.",
              count=len(groups - expected_on_observed), examples=sorted(groups - expected_on_observed)[:10])
    complete_branches = summaries & {branch for branch, state in step_branches.items()
                                    if state["mask"].bit_count() == branch[6]}
    incomplete_groups = {branch[:9] for branch in summaries - complete_branches}
    paired_groups = groups - incomplete_groups
    missing_groups = (expected_all - paired_groups) if expected_all is not None else None
    complete_windows = set()
    for window in observed:
        required = expected_groups({window}, settings) if expected_on_observed is not None else None
        if required and required <= paired_groups:
            complete_windows.add(window)
    completion = "indeterminate"
    if expected_all and not missing_groups and not (expected - observed):
        completion = "completed"
    elif (missing_groups or missing_steps or missing_summary or incomplete_horizons or error_rows
          or missing_recorded or (selected is not None and selected - observed)
          or (expected_on_observed is not None and expected_on_observed - paired_groups)):
        completion = "partial"
    run["completion"] = {"status": completion, "observed_windows": len(observed),
                         "paired_complete_windows": len(complete_windows), "observed_groups": len(groups),
                         "paired_complete_groups": len(paired_groups),
                         "expected_groups": len(expected_all) if expected_all is not None else None,
                         "missing_groups": sorted(missing_groups) if missing_groups is not None else None}
    checkpoint = documents["checkpoint.json"]
    if checkpoint:
        for field, actual in (("completed_branch_groups", len(groups)), ("completed_windows", len(complete_windows))):
            if field == "completed_windows" and expected_on_observed is None:
                continue
            if field in checkpoint:
                try:
                    if integer(checkpoint[field]) != actual:
                        issue(run, "checkpoint_count_mismatch", "Checkpoint counter differs from the exported table view; store records were not inspected.",
                              field=field, recorded=checkpoint[field], observed=actual)
                except ValueError as error:
                    issue(run, "invalid_checkpoint_count", str(error), field=field)
        if checkpoint.get("status") in {"complete", "completed"} and completion == "partial":
            issue(run, "checkpoint_completion_mismatch", "Checkpoint says complete but table/target coverage is partial.")
    integrity = "inconsistent" if run["issues"] else "consistent"
    if not summaries or not step_branches or (directory / "branch_groups").exists():
        if integrity != "inconsistent":
            integrity = "indeterminate"
    run["integrity"] = {"status": integrity, "issue_count": len(run["issues"]),
                        "scope": "Exported CSVs and metadata only; no committed-store certification."}
    run["status"] = "inconsistent" if integrity == "inconsistent" else completion
    if run["data_coverage"]["status"] == "inconsistent":
        run["status"] = "inconsistent"
    elif run["status"] == "completed" and run["data_coverage"]["status"] != "completed":
        run["status"] = run["data_coverage"]["status"]
    run["historical_visualization_risk"] = {"status": "potential", "scope": "Historical series_id numeric conversion before the current text-column protection.",
                                           "conclusion": "Requires figure-by-figure provenance/identifier verification; not a blanket invalidation."}
    return run


def snapshot(roots):
    files, errors = [], []
    for label, root in roots.items():
        try:
            for path in walk_files(root):
                relative = f"{label}/{path.relative_to(root).as_posix()}"
                try:
                    if path.is_symlink():
                        raise ValueError("Symlink not followed")
                    before = path.stat()
                    digest = hashlib.sha256()
                    with path.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise ValueError("File changed while hashing")
                    files.append({"path": relative, "size": after.st_size, "mtime_ns": after.st_mtime_ns,
                                  "mtime": datetime.fromtimestamp(after.st_mtime, timezone.utc).isoformat(),
                                  "sha256": digest.hexdigest()})
                except (OSError, ValueError) as error:
                    errors.append({"path": relative, "error": str(error)})
        except OSError as error:
            errors.append({"path": str(root), "error": str(error)})
        if not root.is_dir():
            errors.append({"path": str(root), "error": "Snapshot root does not exist"})
    return {"created_at": utc_now(), "roots": {k: str(v) for k, v in roots.items()},
            "files": sorted(files, key=lambda r: r["path"]), "errors": errors}


def compare_manifests(before, after):
    left = {entry["path"]: entry for entry in before["files"]}
    right = {entry["path"]: entry for entry in after["files"]}
    shared = left.keys() & right.keys()
    changed = sorted(p for p in shared if any(left[p][k] != right[p][k] for k in ("size", "sha256")))
    metadata = sorted(p for p in shared if str(left[p]["mtime_ns"]) != str(right[p]["mtime_ns"]))
    added, removed = sorted(right.keys() - left.keys()), sorted(left.keys() - right.keys())
    errors = before.get("errors", []) + after.get("errors", [])
    return {"preserved": not (changed or metadata or added or removed or errors),
            "before_count": len(left), "after_count": len(right), "changed_content": changed,
            "changed_mtime": metadata, "added": added, "removed": removed, "errors": errors}


def write_json(path, payload):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write("\n")


def write_manifest(directory, name, manifest):
    write_json(directory / f"{name}.json", manifest)
    with (directory / f"{name}.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "size", "mtime_ns", "mtime", "sha256"])
        writer.writeheader()
        writer.writerows(manifest["files"])


def read_manifest(path):
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream, strict=True))
        for row in rows:
            row["size"] = integer(row["size"])
        return {"files": rows, "errors": []}
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def markdown(report):
    lines = ["# Research Run Inventory", "", f"Generated: {report['created_at']}", "",
             "## Scientific Limits", ""] + [f"- {limit}" for limit in LIMITS]
    lines += ["", "## Status Definitions", "",
              "Overall: completed / partial / inconsistent / indeterminate. Integrity: consistent / inconsistent / indeterminate.",
              "Completion describes available paired exports relative to the known plan, independently of integrity.",
              "Data coverage checks current source identifiers, window bounds and finite values, not scientific validity.", "",
              "## Preservation", "", f"`{json.dumps(report['preservation'], ensure_ascii=True)}`", "",
              "## Runs", "", "| Run | Overall | Data Coverage | Integrity | Completion | Windows | Issues |",
              "| --- | --- | --- | --- | --- | ---: | ---: |"]
    for run in report["runs"]:
        lines.append(f"| {run['path'].replace('|', '/')} | {run['status']} | {run['data_coverage']['status']} | "
                     f"{run['integrity']['status']} | {run['completion']['status']} | "
                     f"{run['completion']['observed_windows']} | {len(run['issues'])} |")
    for run in report["runs"]:
        lines += ["", f"### {run['path']}", "",
                  f"Summary branches: {run['pairing']['summary_branches']}; step branches: {run['pairing']['step_branches']}; "
                  f"paired complete groups: {run['completion']['paired_complete_groups']}."]
        if "selection" in run:
            selection = run["selection"]
            lines.append(f"Selected targets: {selection['selected_windows']}; selected not observed: "
                         f"{len(selection['selected_not_observed'])}; actual not selected: {len(selection['observed_not_selected'])}.")
        for name, table in run["tables"].items():
            if table.get("rejected_count"):
                lines.append(f"- `{name}`: {table['rejected_count']} rejected records; physical ending line numbers: "
                             + ", ".join(str(row["line"]) for row in table["rejected_rows"]) + ". Sources unchanged.")
        for item in run["issues"]:
            detail = {k: v for k, v in item.items() if k not in {"code", "message", "examples"}}
            lines.append(f"- `{item['code']}`: {item['message']} {json.dumps(detail, ensure_ascii=True)}")
        if not run["issues"]:
            lines.append("No anomalies detected in the inspected export scope; this is not a scientific validation.")
    lines += ["", "Detailed missing branch/window identities, rejected records and source evidence are in audit.json.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-root", type=Path, default=ROOT / "result")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "maintenance")
    parser.add_argument("--benchmark-folder", type=Path, help="Explicit current-data reference override; recorded, never silently substituted.")
    parser.add_argument("--snapshot", action="store_true", help="Hash every result/ and data/ file before/after, including branch_groups; write JSON and CSV manifests.")
    parser.add_argument("--verify-manifest", type=Path, help="Compare a prior JSON/CSV manifest with current result/ and data/ files after code cleanup.")
    args = parser.parse_args(argv)
    result_root, output = args.result_root.resolve(), args.output_dir.resolve()
    benchmark = args.benchmark_folder.resolve() if args.benchmark_folder else None
    protected = [ROOT / "result", ROOT / "data", ROOT / "presentations", result_root]
    if benchmark:
        protected.append(benchmark)
    if any(within(output, path.resolve()) for path in protected):
        parser.error("Output must be separate from result, data, presentations and source folders.")
    if not result_root.is_dir():
        parser.error(f"Result root not found: {result_root}")
    roots = {"result": result_root, "data": ROOT / "data"}
    prior = read_manifest(args.verify_manifest.resolve()) if args.verify_manifest else None
    before = snapshot(roots) if args.snapshot or prior is not None else None
    runs = []
    inventory = DataInventory()
    for directory in discover_runs(result_root):
        print(f"Auditing {directory.relative_to(result_root).as_posix()}", flush=True)
        runs.append(audit_run(directory, result_root, inventory, benchmark))
    after = snapshot(roots) if before is not None else None
    preservation = compare_manifests(before, after) if before is not None else {"preserved": None, "reason": "Hash snapshots not requested."}
    if prior is not None:
        preservation["prior_manifest"] = str(args.verify_manifest.resolve())
        preservation["prior_comparison"] = compare_manifests(prior, after)
    destination = output / datetime.now(timezone.utc).strftime("audit_%Y%m%dT%H%M%S_%fZ")
    destination.mkdir(parents=True, exist_ok=False)
    report = {"created_at": utc_now(), "result_root": str(result_root), "limits": LIMITS,
              "counts": dict(Counter(run["status"] for run in runs)), "preservation": preservation, "runs": runs}
    if before is not None:
        write_manifest(destination, "inventory_before", before)
        write_manifest(destination, "inventory_after", after)
    write_json(destination / "audit.json", report)
    with (destination / "report.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(markdown(report))
    print(f"Report: {destination / 'report.md'}")
    print(f"JSON: {destination / 'audit.json'}")
    print(f"Statuses: {report['counts']}")
    if before is not None:
        print(f"Preservation: {preservation['preserved']} ({len(before['files'])} files)")
    return 2 if (preservation.get("preserved") is False or
                 preservation.get("prior_comparison", {}).get("preserved") is False) else 0


if __name__ == "__main__":
    raise SystemExit(main())
