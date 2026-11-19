from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from chronos_scales import resolve_score_column
from research_schema import is_base_branch, read_csv


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def read_csv_robust(path: Path, context: str = "analysis") -> tuple[pd.DataFrame, list[str]]:
    """Compatibility wrapper: production analysis always uses strict CSV reading."""
    return read_csv(path), []
