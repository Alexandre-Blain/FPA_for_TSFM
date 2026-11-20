import os
import sys
import time

import pytest

from windows_job import WindowsJobProcess


@pytest.mark.skipif(os.name != "nt", reason="Native Windows Job Object integration")
def test_memory_accounting_and_termination_cover_redirector_descendants(tmp_path):
    marker = tmp_path / "child_ready"
    child = f"import pathlib,time; data=bytearray(64*1024*1024); pathlib.Path({str(marker)!r}).write_text('ready'); time.sleep(30)"
    parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(30)"
    with (tmp_path / "process.log").open("w") as log:
        process = WindowsJobProcess([sys.executable, "-c", parent], tmp_path, os.environ.copy(), log, 256 * 1024 ** 2)
        try:
            deadline = time.monotonic() + 10
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.05)
            assert marker.exists()
            assert process.active_processes() >= 2
            assert process.peak_job_memory() > 64 * 1024 ** 2
            process.kill()
            process.wait()
            assert process.active_processes() == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.close()
