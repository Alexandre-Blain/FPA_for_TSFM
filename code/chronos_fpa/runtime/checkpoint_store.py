"""Atomic branch-group records; global CSVs are recoverable exports, not truth."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from research_schema import (
    GROUP_KEY_COLS, SCHEMA_VERSION, TEXT_COLUMNS, append_dataframe,
    completed_group_keys, is_base_branch, read_csv,
)
from results_io import publish_directory, save_dataframe, save_json


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_group(steps: pd.DataFrame, summary: pd.DataFrame) -> tuple:
    if steps.empty or summary.empty:
        raise ValueError("A committed group needs nonempty steps AND summary")
    keys = completed_group_keys(summary)
    if len(keys) != 1 or completed_group_keys(steps) != keys:
        raise ValueError("Steps and summary must describe exactly the same group")
    key = next(iter(keys))
    mode, branch_step = key[-2:]
    horizon = key[GROUP_KEY_COLS.index("horizon")]
    if mode not in {"single", "bundle"} or not 0 <= branch_step < horizon:
        raise ValueError("Invalid branch mode or position")
    identity = "token_id" if mode == "single" else "branch_id"
    for frame in (steps, summary):
        if identity not in frame or frame[identity].isna().any():
            raise ValueError(f"Missing branch identity {identity}")
    if summary.duplicated(identity).any() or steps.duplicated([identity, "forecast_step"]).any():
        raise ValueError("Duplicate branch or forecast step")
    if set(steps[identity].astype(str)) != set(summary[identity].astype(str)):
        raise ValueError("Steps/summary branch sets differ")
    if int(is_base_branch(summary).sum()) != 1:
        raise ValueError("Exactly one forced-base branch is required")
    for _, branch in steps.groupby(identity, dropna=False):
        positions = pd.to_numeric(branch["forecast_step"], errors="raise").to_numpy()
        if not np.array_equal(np.sort(positions), np.arange(horizon)):
            raise ValueError("A branch does not contain the complete forecasting horizon")
        if "relative_step_after_branch" not in branch or not np.array_equal(
            pd.to_numeric(branch["relative_step_after_branch"]).to_numpy(), positions - branch_step
        ):
            raise ValueError("Relative branch-step indexing is inconsistent")
        for column in ("law_shift_h", "base_q10", "base_q50", "base_q90", "branch_q10", "branch_q50", "branch_q90"):
            if column not in branch or not np.isfinite(pd.to_numeric(branch[column], errors="coerce")).all():
                raise ValueError(f"Missing or nonfinite forecast values: {column}")
    if "n_steps" in summary and not summary["n_steps"].eq(horizon - branch_step).all():
        raise ValueError("Summary post-branch step counts are incomplete")
    return key


class GroupStore:
    """Publish each group with one directory rename after both tables are durable.

    A crash during CSV export cannot corrupt committed groups. On resume, exports
    are rebuilt from validated group records. Incomplete .pending dirs are not
    commits; a pending final manifest requires explicit recovery before resume.
    """

    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.directory = self.run_dir / "branch_groups"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.initialized = not any(path.is_dir() and not path.name.startswith(".") for path in self.directory.iterdir())

    def _read_record(self, directory):
        with (directory / "manifest.json").open(encoding="utf-8") as stream:
            manifest = json.load(stream)
        if manifest["schema_version"] != SCHEMA_VERSION:
            raise ValueError(f"Incompatible group schema in {directory}")
        if file_hash(directory / "rng.pt") != manifest["rng_sha256"]:
            raise ValueError(f"RNG checkpoint checksum mismatch in {directory}")
        frames = []
        for name in ("steps", "summary"):
            path = directory / f"{name}.csv"
            if file_hash(path) != manifest["hashes"][name]:
                raise ValueError(f"Checksum mismatch in {path}; source preserved")
            frame = read_csv(path)
            if len(frame) != manifest["rows"][name]:
                raise ValueError(f"Manifest row-count mismatch in {path}")
            frames.append(frame)
        key = validate_group(*frames)
        if "trajectory_manifest" in frames[1]:
            from trajectory_export import validate_trajectory_links
            validate_trajectory_links(frames[1], self.run_dir)
        if list(key) != manifest["key"]:
            raise ValueError(f"Group key mismatch in {directory}")
        return manifest, *frames

    def _records(self):
        for directory in sorted(self.directory.iterdir()):
            if directory.is_dir() and not directory.name.startswith("."):
                yield self._read_record(directory)

    def recover(self) -> tuple[pd.DataFrame, set[tuple]]:
        pending = [path for path in self.directory.glob(".pending-*")
                   if path.is_dir() and (path / "manifest.json").exists()]
        if pending:
            raise ValueError(f"Unpublished checkpoint manifests found: {pending}. "
                             "Validate with recover_pending_group before resuming; refusing to regenerate completed computation.")
        steps, summaries, keys = [], [], set()
        schemas = {}
        sequences = []
        for manifest, step, summary in self._records():
            sequences.append(manifest["sequence"])
            key = tuple(manifest["key"])
            if key in keys:
                raise ValueError("Duplicate committed group")
            keys.add(key)
            steps.append(step)
            summaries.append(summary)
            mode = key[-2]
            signature = (tuple(step.columns), tuple(summary.columns))
            if mode in schemas and schemas[mode] != signature:
                raise ValueError("Mixed schemas inside committed branch mode")
            schemas[mode] = signature
        if sorted(sequences) != list(range(len(sequences))):
            raise ValueError("Committed group sequence is incomplete or duplicated")
        self.schemas = schemas
        self.next_sequence = len(sequences)
        self.initialized = True
        for name, frames in (("steps", steps), ("summary", summaries)):
            frame = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
            save_dataframe(self.run_dir / f"chronos_scan_{name}.csv", frame)
        return (pd.concat(summaries, ignore_index=True, sort=False) if summaries else pd.DataFrame()), keys

    def recover_pending_group(self, pending: str | Path) -> tuple:
        """Explicitly publish one fully validated pending record, never infer data.

        Ordinary resume does not promote pending records. Incomplete, corrupt,
        duplicate, out-of-order or schema-incompatible records are rejected.
        """
        pending = Path(pending).resolve()
        if pending.parent != self.directory.resolve() or not pending.name.startswith(".pending-"):
            raise ValueError("Pending checkpoint must be inside this store's branch_groups directory")
        manifest, steps, summary = self._read_record(pending)
        records = list(self._records())
        sequences = sorted(record[0]["sequence"] for record in records)
        if sequences != list(range(len(records))) or manifest["sequence"] != len(records):
            raise ValueError("Pending checkpoint sequence is incompatible; source preserved")
        key = tuple(manifest["key"])
        for old_manifest, old_steps, old_summary in records:
            if old_manifest["key"] == manifest["key"]:
                raise ValueError("Pending group already committed; source preserved")
            if old_manifest["key"][-2] == key[-2] and (
                tuple(old_steps.columns) != tuple(steps.columns) or
                tuple(old_summary.columns) != tuple(summary.columns)
            ):
                raise ValueError("Pending checkpoint schema is incompatible; source preserved")
        digest = hashlib.sha256(json.dumps(key, ensure_ascii=True).encode()).hexdigest()
        publish_directory(pending, self.directory / digest)
        self.recover()
        return key

    def commit(self, steps: pd.DataFrame, summary: pd.DataFrame) -> tuple:
        if not self.initialized:
            self.recover()
        key = validate_group(steps, summary)
        if "trajectory_manifest" in summary:
            from trajectory_export import validate_trajectory_links
            validate_trajectory_links(summary, self.run_dir)
        signature = (tuple(steps.columns), tuple(summary.columns))
        schemas = getattr(self, "schemas", {})
        if key[-2] in schemas and schemas[key[-2]] != signature:
            raise ValueError("Group schema changed during run; refusing incompatible commit")
        digest = hashlib.sha256(json.dumps(key, ensure_ascii=True).encode()).hexdigest()
        destination = self.directory / digest
        if destination.exists():
            # A duplicate callback is safe only if it repeats the same data.
            old = {tuple(item[0]["key"]): item[1:] for item in self._records()}[key]
            for a, b in zip(old, (steps, summary)):
                pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True), check_dtype=False, rtol=1e-12, atol=1e-14)
            return key
        pending = Path(tempfile.mkdtemp(prefix=".pending-", dir=self.directory))
        for name, frame in (("steps", steps), ("summary", summary)):
            save_dataframe(pending / f"{name}.csv", frame)
        import torch
        with (pending / "rng.pt").open("wb") as stream:
            torch.save({"cpu": torch.get_rng_state(), "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else []}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        sequence = getattr(self, "next_sequence", 0)
        save_json(pending / "manifest.json", {
            "schema_version": SCHEMA_VERSION, "key": key,
            "sequence": sequence, "rng_sha256": file_hash(pending / "rng.pt"),
            "rows": {"steps": len(steps), "summary": len(summary)},
            "hashes": {name: file_hash(pending / f"{name}.csv") for name in ("steps", "summary")},
        })
        publish_directory(pending, destination)
        self.next_sequence = sequence + 1
        schemas[key[-2]] = signature
        self.schemas = schemas
        # These exports may be interrupted. The committed directory is authoritative.
        try:
            append_dataframe(self.run_dir / "chronos_scan_steps.csv", steps)
            append_dataframe(self.run_dir / "chronos_scan_summary.csv", summary)
        except ValueError:
            self.recover()  # union schema when single and bundle groups coexist
        return key

    def restore_rng(self) -> None:
        """Restore after model loading, which itself may consume random numbers."""
        manifests = []
        for directory in self.directory.iterdir():
            if directory.is_dir() and not directory.name.startswith("."):
                with (directory / "manifest.json").open(encoding="utf-8") as stream:
                    manifests.append((json.load(stream)["sequence"], directory))
        if manifests:
            import torch
            state = torch.load(max(manifests)[1] / "rng.pt", map_location="cpu", weights_only=True)
            torch.set_rng_state(state["cpu"])
            if state["cuda"] and torch.cuda.is_available():
                torch.cuda.set_rng_state_all(state["cuda"])


def start_store(run_dir: Path, resuming: bool) -> tuple[GroupStore, pd.DataFrame, set[tuple]]:
    if resuming and not (run_dir / "run_state.json").exists():
        raise ValueError(
            "Historical CSV-only run: automatic in-place migration is disabled. "
            "Use scripts/maintenance/audit_research_runs.py for a loss-aware inventory; "
            "keep this run and launch a new experiment."
        )
    store = GroupStore(run_dir)
    summary, keys = store.recover()
    return store, summary, keys
