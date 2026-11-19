"""Local benchmark data records, loaders, and sliding windows."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

import numpy as np
import pandas as pd


@dataclass
class SeriesRecord:
    dataset_name: str
    series_id: str
    target: np.ndarray
    source: str


@dataclass
class WindowRecord:
    dataset_name: str
    series_id: str
    source: str
    window_id: int
    window_start: int
    context_len: int
    horizon: int
    values: np.ndarray

    @property
    def context(self) -> np.ndarray:
        return self.values[self.window_start : self.window_start + self.context_len]

    @property
    def future(self) -> np.ndarray:
        start = self.window_start + self.context_len
        return self.values[start : start + self.horizon]


def parse_int_list(value: str | Iterable[int]) -> List[int]:
    if isinstance(value, str):
        if not value.strip():
            return []
        return [int(part.strip()) for part in value.split(",") if part.strip()]
    return [int(part) for part in value]


def _clean_target(values) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float32).reshape(-1)
    arr[~np.isfinite(arr)] = np.nan
    return arr


def iter_csv_folder_series(
    folder: str | Path,
    target_columns: Optional[Iterable[str]] = None,
    min_length: Optional[int] = None,
) -> Iterator[SeriesRecord]:
    """Yield one univariate series per selected numeric CSV column."""
    folder = Path(folder)
    requested_columns = None if target_columns is None else set(target_columns)
    for path in sorted(folder.glob("*.csv")):
        df = pd.read_csv(path)
        if requested_columns is None:
            columns = [
                col
                for col in df.columns
                if col.lower() not in {"date", "timestamp", "time"}
                and pd.api.types.is_numeric_dtype(df[col])
            ]
        else:
            missing = requested_columns.difference(df.columns)
            if missing:
                raise ValueError(f"{path} is missing target columns: {sorted(missing)}")
            columns = [col for col in df.columns if col in requested_columns]

        for col in columns:
            target = _clean_target(df[col].to_numpy())
            if min_length is not None and len(target) < min_length:
                continue
            yield SeriesRecord(
                dataset_name=path.stem,
                series_id=col,
                target=target,
                source=str(path),
            )


def iter_benchmark_folder_series(
    folder: str | Path,
    dataset_names: Optional[Iterable[str]] = None,
    max_datasets: Optional[int] = None,
    max_series_per_dataset: Optional[int] = None,
    min_length: Optional[int] = None,
) -> Iterator[SeriesRecord]:
    """Yield exported Chronos benchmark series from local JSONL files."""
    folder = Path(folder)
    requested_names = None if dataset_names is None else set(dataset_names)
    yielded_datasets = set()
    yielded_per_dataset: dict[str, int] = {}

    for path in sorted(folder.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                dataset_name = str(row.get("dataset_name", path.stem))
                if requested_names is not None and dataset_name not in requested_names:
                    continue

                target = _clean_target(row["target"])
                if min_length is not None and len(target) < min_length:
                    continue

                if (
                    dataset_name not in yielded_datasets
                    and max_datasets is not None
                    and len(yielded_datasets) >= max_datasets
                ):
                    continue

                yielded_datasets.add(dataset_name)
                count = yielded_per_dataset.get(dataset_name, 0)
                if max_series_per_dataset is not None and count >= max_series_per_dataset:
                    continue

                yielded_per_dataset[dataset_name] = count + 1
                yield SeriesRecord(
                    dataset_name=dataset_name,
                    series_id=str(row.get("series_id", count)),
                    target=target,
                    source=str(row.get("source_repo", path)),
                )


def iter_sliding_windows(
    series: SeriesRecord,
    context_len: int,
    horizon: int,
    slide_step: Optional[int] = None,
    max_windows_per_series: Optional[int] = None,
    adaptive_context: bool = False,
    min_context_len: int = 64,
) -> Iterator[WindowRecord]:
    if context_len <= 0 or horizon <= 0:
        raise ValueError("context_len and horizon must be positive.")
    if min_context_len <= 0:
        raise ValueError("min_context_len must be positive.")
    if slide_step is None:
        slide_step = max(1, horizon // 2)
    if slide_step <= 0:
        raise ValueError("slide_step must be positive.")

    effective_context_len = context_len
    if adaptive_context and len(series.target) < context_len + horizon:
        effective_context_len = len(series.target) - horizon
        if effective_context_len < min_context_len:
            return

    max_start = len(series.target) - effective_context_len - horizon
    if max_start < 0:
        return

    count = 0
    for window_start in range(0, max_start + 1, slide_step):
        if max_windows_per_series is not None and count >= max_windows_per_series:
            break
        yield WindowRecord(
            dataset_name=series.dataset_name,
            series_id=series.series_id,
            source=series.source,
            window_id=count,
            window_start=window_start,
            context_len=effective_context_len,
            horizon=horizon,
            values=series.target,
        )
        count += 1
