import argparse
import json
from pathlib import Path

import pandas as pd
import pytest

from checkpoint_store import GroupStore, start_store
from research_schema import read_csv
from results_io import save_json
from run_config import add_config_argument, parse_run_configuration
from fpa_test_tables import group_tables


def test_partial_or_corrupt_group_is_never_completed(tmp_path):
    store = GroupStore(tmp_path)
    steps, summary = group_tables()
    with pytest.raises(ValueError, match="complete forecasting horizon"):
        store.commit(steps.iloc[:-1], summary)
    assert list(store.directory.iterdir()) == []
    store.commit(steps, summary)
    committed = next(path for path in store.directory.iterdir() if not path.name.startswith("."))
    with (committed / "steps.csv").open("a") as stream:
        stream.write("broken\n")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        store.recover()


def test_interruption_between_files_and_before_publish_leaves_no_commit(tmp_path, monkeypatch):
    import checkpoint_store
    store = GroupStore(tmp_path)
    save = checkpoint_store.save_dataframe
    def fail_summary(path, frame):
        if Path(path).name == "summary.csv":
            raise OSError("simulated disk interruption")
        save(path, frame)
    monkeypatch.setattr(checkpoint_store, "save_dataframe", fail_summary)
    with pytest.raises(OSError):
        store.commit(*group_tables())
    monkeypatch.setattr(checkpoint_store, "save_dataframe", save)
    summary, keys = store.recover()
    assert summary.empty and not keys
    monkeypatch.setattr(checkpoint_store.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("publish failed")))
    with pytest.raises(OSError):
        store.commit(*group_tables())
    assert not [p for p in store.directory.iterdir() if not p.name.startswith(".")]


def test_committed_group_survives_export_failure_and_resume_rebuilds(tmp_path, monkeypatch):
    import checkpoint_store
    store = GroupStore(tmp_path)
    monkeypatch.setattr(checkpoint_store, "append_dataframe", lambda *args: (_ for _ in ()).throw(OSError("power loss")))
    with pytest.raises(OSError):
        store.commit(*group_tables())
    # Published group, not the interrupted exports, defines completion.
    summary, keys = GroupStore(tmp_path).recover()
    assert len(summary) == 2 and len(keys) == 1
    assert summary.series_id.tolist() == ["001", "001"]
    assert len(read_csv(tmp_path / "chronos_scan_steps.csv")) == 6


def test_duplicate_callback_does_not_append_twice_and_schema_change_fails(tmp_path):
    store = GroupStore(tmp_path)
    steps, summary = group_tables()
    store.commit(steps, summary)
    store.commit(steps, summary)
    assert len(read_csv(tmp_path / "chronos_scan_summary.csv")) == 2
    other_steps, other_summary = group_tables(step=1)
    with pytest.raises(ValueError, match="schema changed"):
        store.commit(other_steps, other_summary.assign(unexpected=3))


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_windows_directory_lock_is_retried_without_duplicate_commit(tmp_path, monkeypatch, winerror):
    import results_io
    real_replace = results_io.os.replace
    directory_attempts = []
    def flaky(source, destination):
        if Path(source).is_dir():
            directory_attempts.append((source, destination))
            if len(directory_attempts) < 3:
                error = PermissionError("temporary Windows publication denial")
                error.winerror = winerror
                raise error
        return real_replace(source, destination)
    monkeypatch.setattr(results_io.os, "replace", flaky)
    monkeypatch.setattr(results_io.time, "sleep", lambda _: None)
    store = GroupStore(tmp_path)
    with pytest.warns(RuntimeWarning, match="retrying without deleting"):
        store.commit(*group_tables())
    summary, keys = store.recover()
    assert len(directory_attempts) == 3 and len(keys) == 1 and len(summary) == 2
    assert not list(store.directory.glob(".pending-*"))


def leave_finished_pending(store, monkeypatch):
    import results_io
    real_replace = results_io.os.replace
    def deny_directory(source, destination):
        if Path(source).is_dir():
            error = PermissionError("persistent Windows publication denial")
            error.winerror = 5
            raise error
        return real_replace(source, destination)
    with monkeypatch.context() as patch:
        patch.setattr(results_io.os, "replace", deny_directory)
        patch.setattr(results_io.time, "sleep", lambda _: None)
        with pytest.warns(RuntimeWarning), pytest.raises(PermissionError):
            store.commit(*group_tables())
    return next(store.directory.glob(".pending-*"))


def test_finished_pending_checkpoint_requires_explicit_recovery_without_inference(tmp_path, monkeypatch):
    store = GroupStore(tmp_path)
    pending = leave_finished_pending(store, monkeypatch)
    original = {path.name: path.read_bytes() for path in pending.iterdir()}
    with pytest.raises(ValueError, match="refusing to regenerate"):
        GroupStore(tmp_path).recover()
    key = store.recover_pending_group(pending)
    summary, keys = GroupStore(tmp_path).recover()
    assert keys == {key} and len(summary) == 2
    committed = next(p for p in store.directory.iterdir() if not p.name.startswith("."))
    assert original == {path.name: path.read_bytes() for path in committed.iterdir()}
    assert not pending.exists()
    assert len(read_csv(tmp_path / "chronos_scan_steps.csv")) == 6


@pytest.mark.parametrize("defect", ["checksum", "sequence", "rows", "schema"])
def test_explicit_pending_recovery_rejects_inconsistent_record(tmp_path, monkeypatch, defect):
    store = GroupStore(tmp_path)
    pending = leave_finished_pending(store, monkeypatch)
    manifest_path = pending / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if defect == "checksum":
        with (pending / "steps.csv").open("a") as stream:
            stream.write("corrupt\n")
    elif defect == "sequence":
        manifest["sequence"] = 7
    elif defect == "rows":
        manifest["rows"]["steps"] += 1
    else:
        manifest["schema_version"] = -1
    save_json(manifest_path, manifest)
    with pytest.raises(ValueError):
        store.recover_pending_group(pending)
    assert pending.exists()
    assert not [p for p in store.directory.iterdir() if not p.name.startswith(".")]


def test_pending_recovery_cannot_move_outside_store_or_overwrite_directory(tmp_path):
    from results_io import publish_directory
    store = GroupStore(tmp_path / "store")
    outside = tmp_path / ".pending-outside"
    outside.mkdir()
    with pytest.raises(ValueError, match="inside this store"):
        store.recover_pending_group(outside)
    destination = tmp_path / "already_published"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("unchanged")
    with pytest.raises(FileExistsError):
        publish_directory(outside, destination)
    assert sentinel.read_text() == "unchanged" and outside.exists()
    with pytest.raises(ValueError, match="one parent directory"):
        publish_directory(outside, store.directory / "wrong-parent")


def test_strict_csv_preserves_identifiers_and_recovery_reports_rows(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text("series_id,value\n001,3\nNA,4\nbad\nother,1,extra\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no rows were skipped"):
        read_csv(path)
    recovered = read_csv(path, recover=True)
    assert recovered.series_id.tolist() == ["001", "NA"]
    assert [r["line"] for r in recovered.attrs["excluded_rows"]] == [4, 5]


def parser():
    p = argparse.ArgumentParser()
    add_config_argument(p)
    p.add_argument("--resume-from", default="")
    p.add_argument("--num-samples", type=int, default=10)
    p.add_argument("--no-progress", action="store_true")
    return p


def test_resume_restores_saved_settings_and_rejects_incompatible_override(tmp_path):
    save_json(tmp_path / "run_state.json", {"schema_version": 2, "args": {
        "num_samples": 40, "no_progress": False, "resume_from": "", "config": "",
    }})
    args, *_ = parse_run_configuration(parser(), ["--resume-from", str(tmp_path), "--no-progress"])
    assert args.num_samples == 40 and args.no_progress
    with pytest.raises(ValueError, match="Incompatible resume"):
        parse_run_configuration(parser(), ["--resume-from", str(tmp_path), "--num-samples", "5"])


def test_historical_csv_only_resume_does_not_mutate_it(tmp_path):
    path = tmp_path / "chronos_scan_summary.csv"
    path.write_text("series_id\nold\n")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Historical CSV-only"):
        start_store(tmp_path, resuming=True)
    assert path.read_bytes() == before
    assert not (tmp_path / "branch_groups").exists()
