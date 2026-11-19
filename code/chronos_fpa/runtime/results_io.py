from __future__ import annotations

import json
import os
import tempfile
import time
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd


def publish_directory(source: str | Path, destination: str | Path, attempts: int = 9) -> None:
    """Rename a complete sibling directory, tolerating brief Windows file locks.

    Never copy/delete a partially published group or overwrite an existing one.
    Persistent denial leaves the source intact for explicit recovery.
    """
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source.parent != destination.parent or source == destination:
        raise ValueError("Atomic directory publication must stay inside one parent directory")
    if attempts < 1:
        raise ValueError("Publication needs at least one attempt")
    for attempt in range(attempts):
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite published directory: {destination}")
        try:
            os.replace(source, destination)
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == attempts - 1:
                raise
            if attempt == 0:
                warnings.warn(f"Windows denied directory publication; retrying without deleting pending data: {source}", RuntimeWarning)
            time.sleep(min(.125 * 2 ** attempt, 2.0))


def _safe_run_name(value: str) -> str:
    safe = []
    for char in value.strip():
        safe.append(char if char.isalnum() or char in "-_." else "_")
    return "".join(safe).strip("_")


def make_run_dir(output_root: str | Path, grid_spec_path: str | None, run_name: str | None = None):
    """Create a dated output folder whose name is based on the JSON spec name."""
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    explicit_name = _safe_run_name(run_name or "")
    if explicit_name:
        spec_name = explicit_name
    elif grid_spec_path is None:
        spec_name = "default_grid"
    else:
        spec_name = Path(grid_spec_path).stem

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / f"{spec_name}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def save_json(path: str | Path, payload):
    path = Path(path)
    _atomic_write(path, lambda f: json.dump(payload, f, indent=2, default=str, ensure_ascii=False))


def save_dataframe(path: str | Path, frame: pd.DataFrame):
    path = Path(path)
    _atomic_write(path, lambda f: frame.to_csv(f, index=False))


def _atomic_write(path: Path, write) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

