"""Locate plain research modules without installing a package."""
from pathlib import Path
import sys


def configure_imports() -> None:
    root = Path(__file__).resolve().parent
    for directory in ("core", "data", "metrics", "runtime", "pipeline", "analysis", "visualization"):
        path = str(root / directory)
        if path not in sys.path:
            sys.path.insert(0, path)


configure_imports()
