from datetime import datetime, timezone
import json

import pytest

import run_chronos_microbenchmark as benchmark


def test_supervisor_deadline_kills_child_and_records_consumed_reservation(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "model_wall_seconds": 1, "task_wall_seconds": 14400,
        "task_started_utc": datetime.now(timezone.utc).isoformat(),
        "minimum_system_free_bytes": 1, "max_process_bytes": 2 ** 31,
        "max_output_bytes": 2 ** 29,
    }))

    class Process:
        returncode = None

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self):
            return self.returncode

        def peak_job_memory(self):
            return 123

        def close(self):
            pass

    child = Process()
    monkeypatch.setattr(benchmark, "start_model_process", lambda *args, **kwargs: child)
    monkeypatch.setattr(benchmark.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(benchmark, "memory_usage", lambda *args: {
        "system_free_bytes": 2 ** 32, "peak_working_set_bytes": 123})
    ticks = iter([0., 2., 3.])
    monkeypatch.setattr(benchmark.time, "monotonic", lambda: next(ticks))
    output = tmp_path / "result/benchmark"
    assert benchmark.supervise(config, output) == 2
    ledger = json.loads((output / "budget.json").read_text())
    assert ledger["stop_reason"] == "hard_model_or_task_deadline"
    assert ledger["spent_model_seconds"] == 3
    with pytest.raises(RuntimeError, match="exhausted"):
        benchmark.supervise(config, output)


def test_supervisor_refuses_unresolved_reservation_before_starting_model(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    output = tmp_path / "result/benchmark"
    output.mkdir(parents=True)
    (output / "budget.json").write_text('{"status":"running","spent_model_seconds":0}')
    config = tmp_path / "config.json"
    config.write_text("{}")
    with pytest.raises(RuntimeError, match="unresolved"):
        benchmark.supervise(config, output)
