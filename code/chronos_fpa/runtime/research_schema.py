"""Shared identifiers and strict, loss-aware CSV contracts."""
from __future__ import annotations

import csv
import math
from pathlib import Path

import pandas as pd

WINDOW_KEY_COLS = ["source", "dataset_name", "series_id", "window_id", "window_start", "context_len", "horizon"]
GROUP_KEY_COLS = WINDOW_KEY_COLS + ["branch_mode", "branch_step"]
TEXT_COLUMNS = {"source", "dataset_name", "series_id", "branch_mode", "branch_id", "base_branch_id", "forced_tokens"}
INTEGER_COLUMNS = {"window_id", "window_start", "context_len", "horizon", "branch_step", "forecast_step", "token_id"}
SCHEMA_VERSION = 2
ANALYSIS_VERSION = "2.0-explicit-scale"


def integer_id(value) -> int:
    number = float(value)
    if not math.isfinite(number) or number != int(number):
        raise ValueError(f"Invalid integer identifier {value!r}")
    return int(number)


def read_csv(path: str | Path, missing_ok: bool = False, recover: bool = False) -> pd.DataFrame:
    """Reject ragged rows, including short rows pandas would silently pad.

    Recovery is audit-only: excluded records and their physical line positions
    are returned in frame.attrs['excluded_rows']; source files are never edited.
    """
    path = Path(path)
    if not path.exists():
        if missing_ok:
            return pd.DataFrame()
        raise FileNotFoundError(path)
    if path.stat().st_size == 0:
        return pd.DataFrame()
    rejected = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, [])
        if not header:
            return pd.DataFrame()
        if len(set(header)) != len(header):
            raise ValueError(f"Duplicate CSV columns in {path}")
        good = [] if recover else None
        for row in reader:
            if not row:
                continue
            if len(row) != len(header):
                detail = {"line": reader.line_num, "fields": len(row), "expected_fields": len(header)}
                if not recover:
                    raise ValueError(f"Malformed CSV {path}, line {reader.line_num}: {detail}. Use the audit tool; no rows were skipped.")
                rejected.append(detail)
            elif recover:
                good.append(row)
    dtypes = {col: "string" for col in header if col in TEXT_COLUMNS}
    if recover:
        from io import StringIO
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        writer.writerows(good)
        buffer.seek(0)
        source = buffer
    else:
        source = path
    frame = pd.read_csv(source, dtype=dtypes, keep_default_na=False, na_values=[""])
    frame.attrs["excluded_rows"] = rejected
    return frame


def is_base_branch(frame: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=frame.index)
    for column in ("is_base_token", "is_base_branch"):
        if column in frame:
            mask |= frame[column].astype(str).str.lower().isin({"true", "1", "yes"})
    return mask


def window_key(window) -> tuple:
    return tuple(str(getattr(window, col)) if col in TEXT_COLUMNS else integer_id(getattr(window, col)) for col in WINDOW_KEY_COLS)


def expected_group_keys(window, branch_steps, branch_modes, bundle_size: int) -> set[tuple]:
    key = window_key(window)
    modes = set(branch_modes)
    return {
        key + (mode, int(step))
        for step in branch_steps
        for mode in modes
        if 0 <= step < window.horizon
        and (mode == "single" or (mode == "bundle" and step + bundle_size <= window.horizon))
    }


def completed_group_keys(summary: pd.DataFrame) -> set[tuple]:
    if summary.empty:
        return set()
    if not set(GROUP_KEY_COLS).issubset(summary):
        raise ValueError("Missing group identifiers in summary")
    if summary[GROUP_KEY_COLS].isna().any().any():
        raise ValueError("Null group identifiers in summary")
    return {
        tuple(str(value) if col in TEXT_COLUMNS else integer_id(value) for col, value in zip(GROUP_KEY_COLS, row))
        for row in summary[GROUP_KEY_COLS].drop_duplicates().itertuples(index=False, name=None)
    }


def append_dataframe(path: str | Path, frame: pd.DataFrame) -> None:
    """Append only the exact existing schema. Never discard new columns."""
    path = Path(path)
    if frame.empty:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            columns = next(csv.reader(stream), [])
        if set(columns) != set(frame.columns):
            raise ValueError(f"CSV schema mismatch in {path}; refusing lossy append")
        frame = frame[columns]
        header = False
    else:
        header = True
    frame.to_csv(path, mode="a", header=header, index=False)


def validate_branch_keys(frame: pd.DataFrame, steps: bool = False) -> None:
    """Reject ambiguous joins instead of silently deduplicating observations."""
    if frame.empty:
        return
    if not set(GROUP_KEY_COLS).issubset(frame):
        raise ValueError("Missing window/group identifiers")
    for mode, subset in frame.groupby("branch_mode", dropna=False):
        if mode not in {"single", "bundle"}:
            raise ValueError(f"Unsupported branch mode {mode!r}")
        identity = "token_id" if mode == "single" else "branch_id"
        columns = GROUP_KEY_COLS + [identity] + (["forecast_step"] if steps else [])
        if not set(columns).issubset(subset) or subset[columns].isna().any().any():
            raise ValueError("Missing branch identifiers")
        if subset.duplicated(columns).any():
            raise ValueError("Duplicate branch/step identifiers; refusing ambiguous analysis")
