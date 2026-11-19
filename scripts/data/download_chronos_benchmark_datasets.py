from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPOS = [
    "autogluon/chronos_datasets",
    "autogluon/chronos_datasets_extra",
]


def _parse_csv(value: str) -> list[str]:
    if not value.strip():
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _import_hf_datasets():
    """Import Hugging Face datasets without seeing this repo's ./datasets folder."""
    old_path = list(sys.path)
    filtered_path = []
    for item in old_path:
        resolved = Path(item or os.getcwd()).resolve()
        if resolved == ROOT:
            continue
        filtered_path.append(item)

    existing = sys.modules.get("datasets")
    if existing is not None and getattr(existing, "__file__", None) is None:
        sys.modules.pop("datasets", None)

    sys.path = filtered_path
    try:
        module = importlib.import_module("datasets")
    except ImportError as exc:
        raise ImportError(
            "Missing Hugging Face `datasets`. Run with e.g.:\n"
            "  $env:UV_CACHE_DIR = \"$PWD\\.uv_cache\"\n"
            "  uv run --with datasets scripts\\download_chronos_benchmark_datasets.py"
        ) from exc
    finally:
        sys.path = old_path

    if not hasattr(module, "load_dataset") or not hasattr(module, "get_dataset_config_names"):
        raise ImportError(
            "Imported `datasets`, but it is not the Hugging Face package. "
            "This usually means the repo's local ./datasets folder shadowed it."
        )
    return module


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value)


def _series_id_from_row(row, index: int) -> str:
    for key in ("item_id", "id", "series_id"):
        if key in row:
            return str(row[key])
    return str(index)


def _target_to_jsonable(values: Iterable) -> list[float | None]:
    out = []
    for value in values:
        if value is None:
            out.append(None)
            continue
        value = float(value)
        out.append(value if math.isfinite(value) else None)
    return out


def _metadata_to_jsonable(row: dict) -> dict:
    meta = {}
    for key in ("start", "freq", "prediction_length"):
        if key in row:
            meta[key] = str(row[key])
    return meta


def _get_dataset_config_names(hf_datasets, repo: str):
    try:
        return hf_datasets.get_dataset_config_names(repo, trust_remote_code=True)
    except TypeError:
        return hf_datasets.get_dataset_config_names(repo)


def _load_dataset(hf_datasets, repo: str, dataset_name: str, split: str):
    try:
        return hf_datasets.load_dataset(
            repo,
            dataset_name,
            split=split,
            trust_remote_code=True,
        )
    except TypeError:
        return hf_datasets.load_dataset(repo, dataset_name, split=split)


def run():
    parser = argparse.ArgumentParser(
        description="Download/export Chronos benchmark datasets to local JSONL files."
    )
    parser.add_argument("--repos", default=",".join(DEFAULT_REPOS))
    parser.add_argument(
        "--datasets",
        default="",
        help="Optional comma-separated dataset config names.",
    )
    parser.add_argument("--split", default="train")
    parser.add_argument("--output-dir", default="data/raw/chronos_benchmark")
    parser.add_argument("--max-datasets", type=int, default=0)
    parser.add_argument("--max-series-per-dataset", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--list-only", action="store_true")
    args = parser.parse_args()

    hf_datasets = _import_hf_datasets()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    requested = set(_parse_csv(args.datasets)) or None
    manifest = {
        "repos": _parse_csv(args.repos),
        "split": args.split,
        "datasets": [],
    }

    exported_datasets = 0
    for repo in _parse_csv(args.repos):
        config_names = (
            sorted(requested)
            if requested is not None
            else _get_dataset_config_names(hf_datasets, repo)
        )
        if args.list_only:
            print(f"\n{repo}")
            for name in config_names:
                print(f"- {name}")
            continue

        for dataset_name in config_names:
            if args.max_datasets and exported_datasets >= args.max_datasets:
                break

            file_name = (
                f"{_safe_name(repo)}__{_safe_name(dataset_name)}"
                f"__{_safe_name(args.split)}.jsonl"
            )
            output_path = output_dir / file_name
            if output_path.exists() and not args.overwrite:
                print(f"Skipping existing {output_path}")
                manifest["datasets"].append(
                    {
                        "repo": repo,
                        "dataset_name": dataset_name,
                        "split": args.split,
                        "path": str(output_path),
                        "skipped_existing": True,
                    }
                )
                exported_datasets += 1
                continue

            print(f"Downloading {repo}/{dataset_name} split={args.split}")
            ds = _load_dataset(hf_datasets, repo, dataset_name, args.split)

            n_series = 0
            with output_path.open("w", encoding="utf-8") as f:
                for idx, row in enumerate(ds):
                    if args.max_series_per_dataset and idx >= args.max_series_per_dataset:
                        break
                    if "target" not in row:
                        continue
                    payload = {
                        "source_repo": repo,
                        "dataset_name": dataset_name,
                        "split": args.split,
                        "series_id": _series_id_from_row(row, idx),
                        "target": _target_to_jsonable(row["target"]),
                        "metadata": _metadata_to_jsonable(row),
                    }
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                    n_series += 1

            manifest["datasets"].append(
                {
                    "repo": repo,
                    "dataset_name": dataset_name,
                    "split": args.split,
                    "path": str(output_path),
                    "n_series": n_series,
                }
            )
            exported_datasets += 1
            print(f"Saved {n_series} series to {output_path}")

        if args.max_datasets and exported_datasets >= args.max_datasets:
            break

    if not args.list_only:
        manifest_path = output_dir / "manifest.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"\nSaved manifest to {manifest_path}")


if __name__ == "__main__":
    run()



