"""Offline, flat-module imports for the application test suite."""

import os
from pathlib import Path
import socket
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "code" / "chronos_fpa"
for path in (REPO_ROOT / "scripts" / "viz", REPO_ROOT / "scripts" / "runs", MODULE_ROOT):
    sys.path.insert(0, str(path))

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "maintenance"))

import bootstrap  # noqa: E402

bootstrap.configure_imports()

# Set before test-module imports, not just before individual tests.
for variable in ("HF_HUB_OFFLINE", "HF_DATASETS_OFFLINE", "TRANSFORMERS_OFFLINE"):
    os.environ[variable] = "1"
os.environ["MPLBACKEND"] = "Agg"


@pytest.fixture(scope="session", autouse=True)
def single_threaded_torch():
    """Keep tiny CPU test doubles from paying many-core scheduling overhead."""
    import torch

    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(previous)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Fail accidental network access instead of downloading test dependencies/data."""
    def blocked(*args, **kwargs):
        raise AssertionError("Application tests must not access the network")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
