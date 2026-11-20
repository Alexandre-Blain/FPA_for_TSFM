from pathlib import Path

import pytest

import results_io


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_transient_file_denial_retries_complete_bytes(tmp_path, monkeypatch, winerror):
    target = tmp_path / "export.json"
    target.write_text("old data")
    replace = results_io.os.replace
    attempts = []

    def flaky(source, destination):
        attempts.append(Path(source).read_bytes())
        if len(attempts) < 3:
            error = PermissionError("temporary denial")
            error.winerror = winerror
            raise error
        replace(source, destination)

    monkeypatch.setattr(results_io.os, "replace", flaky)
    monkeypatch.setattr(results_io.time, "sleep", lambda _: None)
    with pytest.warns(RuntimeWarning, match="retrying complete"):
        results_io.save_json(target, {"new": 7})
    assert len(attempts) == 3 and len(set(attempts)) == 1
    assert target.read_text() == '{\n  "new": 7\n}'
    assert not list(tmp_path.glob("*.tmp"))


def test_persistent_file_denial_preserves_old_target_and_finished_temporary(tmp_path, monkeypatch):
    target = tmp_path / "export.json"
    target.write_text("old data")
    attempts = []

    def denied(source, destination):
        attempts.append(source)
        error = PermissionError("persistent denial")
        error.winerror = 5
        raise error

    monkeypatch.setattr(results_io.os, "replace", denied)
    monkeypatch.setattr(results_io.time, "sleep", lambda _: None)
    with pytest.warns(RuntimeWarning), pytest.raises(PermissionError) as caught:
        results_io.save_json(target, {"new": 7})
    assert len(attempts) == 9
    assert target.read_text() == "old data"
    pending = list(tmp_path.glob("*.tmp"))
    assert len(pending) == 1 and '"new": 7' in pending[0].read_text()
    assert "preserved" in caught.value.__notes__[0]


def test_non_windows_denial_is_not_retried(tmp_path, monkeypatch):
    attempts = []

    def denied(source, destination):
        attempts.append(source)
        raise PermissionError("permanent ACL denial")

    monkeypatch.setattr(results_io.os, "replace", denied)
    with pytest.raises(PermissionError):
        results_io.save_json(tmp_path / "new.json", {})
    assert len(attempts) == 1
