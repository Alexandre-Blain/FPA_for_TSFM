"""Immutable ensemble objects and strictly read-only snapshot retrieval."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import numpy as np

from results_io import publish_directory, save_json


SCHEMA = "chronos_complete_token_ensemble_v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def task_id(identity):
    return hashlib.sha256(canonical(identity).encode()).hexdigest()


def describe(array):
    array = np.asarray(array)
    if array.dtype.hasobject:
        raise ValueError("Object arrays cannot be persisted")
    return {"shape": list(array.shape), "dtype": str(array.dtype),
            "sha256": hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()}


def read_object(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA or manifest["task_id"] != task_id(manifest["identity"]):
        raise ValueError("Ensemble identity/schema mismatch")
    with np.load(directory / "arrays.npz", allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    if set(arrays) != set(manifest["arrays"]) or any(describe(a) != manifest["arrays"][name] for name, a in arrays.items()):
        raise ValueError("Ensemble array checksum/shape/dtype mismatch")
    if "tokens" not in arrays or "values" not in arrays or arrays["tokens"].shape != arrays["values"].shape:
        raise ValueError("Complete aligned token/value paths are required")
    if arrays["tokens"].ndim != 2 or 0 in arrays["tokens"].shape or arrays["tokens"].dtype != np.int64 or not np.isfinite(arrays["values"]).all():
        raise ValueError("Nonempty int64 token paths and finite numeric values are required")
    return manifest, arrays


class EnsembleStore:
    def __init__(self, directory, scope=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        marker = self.directory / "_scope.json"
        existing = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else None
        if scope is not None:
            scope = json.loads(canonical(scope))
            if existing is not None and existing != scope:
                raise ValueError("Window scope differs from the existing ensemble store")
            if existing is None:
                if any(self.directory.iterdir()):
                    raise ValueError("Cannot assign a window scope to an existing unscoped store")
                save_json(marker, scope)
        self.scope = existing if scope is None else scope

    def _check_scope(self, identity):
        if self.scope is not None and any(identity.get(k) != v for k, v in self.scope.items()):
            raise ValueError("Ensemble identity belongs to another window/seed scope")

    def get(self, identity):
        self._check_scope(identity)
        path = self.directory / task_id(identity)
        if not path.exists():
            return None
        manifest, arrays = read_object(path)
        if manifest["identity"] != json.loads(canonical(identity)):
            raise ValueError("Conflicting ensemble identity")
        return manifest, arrays

    def put(self, identity, arrays, metadata):
        arrays = {name: np.ascontiguousarray(a) for name, a in arrays.items()}
        manifest = {"schema": SCHEMA, "task_id": task_id(identity), "identity": identity,
                    "metadata": metadata, "arrays": {name: describe(a) for name, a in arrays.items()}}
        previous = self.get(identity)
        if previous is not None:
            if canonical(previous[0]) != canonical(manifest):
                raise ValueError("Refusing to replace a conflicting finalized ensemble")
            return previous
        pending = Path(tempfile.mkdtemp(prefix=".pending-", dir=self.directory))
        with (pending / "arrays.npz").open("wb") as stream:
            np.savez_compressed(stream, **arrays)
            stream.flush()
            os.fsync(stream.fileno())
        save_json(pending / "manifest.json", manifest)
        read_object(pending)
        publish_directory(pending, self.directory / task_id(identity))
        return self.get(identity)

    def recover_pending(self, path):
        path = Path(path).resolve()
        if path.parent != self.directory.resolve() or not path.name.startswith(".pending-"):
            raise ValueError("Pending object must remain in this ensemble store")
        manifest, _ = read_object(path)
        self._check_scope(manifest["identity"])
        publish_directory(path, self.directory / manifest["task_id"])
        return manifest["task_id"]


def isolated_window_store(campaign_directory, scope):
    """One immutable cell namespace, even for identical tokens/seeds/positions."""
    required = {"dataset_id", "series_id", "forecast_origin", "context_sha256",
                "model_revision", "grid_revision", "policy", "sampling_seed"}
    if not required.issubset(scope):
        raise ValueError("Incomplete window scope")
    return EnsembleStore(Path(campaign_directory) / "cells" / task_id(scope) / "ensembles", scope=scope)


def read_snapshot(directory, object_ids=None, expected_scope=None):
    """No mkdir, recovery, export writes or RNG restoration; freeze IDs first."""
    directory = Path(directory)
    marker = directory / "_scope.json"
    scope = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else None
    if expected_scope is not None and scope != expected_scope:
        raise ValueError("Snapshot belongs to another window/seed scope")
    names = sorted(p.name for p in directory.iterdir()
                   if p.is_dir() and re.fullmatch("[0-9a-f]{64}", p.name)) if object_ids is None else sorted(object_ids)
    if len(set(names)) != len(names) or any(not re.fullmatch("[0-9a-f]{64}", name) for name in names):
        raise ValueError("Snapshot IDs must be distinct finalized ensemble hashes")
    records, hashes = [], {}
    for name in names:
        path = directory / name
        manifest, arrays = read_object(path)
        if scope is not None and any(manifest["identity"].get(k) != v for k, v in scope.items()):
            raise ValueError("Foreign window ensemble in scoped snapshot")
        if manifest["task_id"] != name:
            raise ValueError("Ensemble directory/manifest identity mismatch")
        hashes[name] = hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest()
        records.append((manifest, arrays))
    return {"snapshot_id": task_id(hashes), "object_ids": names, "manifest_sha256": hashes,
            "records": records}


def publish_fork_manifest(directory, store_directory, fork):
    """Publish q50 weights only after every selected/residual/null ensemble exists."""
    directory, store_directory = Path(directory), Path(store_directory)
    b, greedy = int(fork["b"]), int(fork["greedy_token"])
    if not 0 <= b <= 9:
        raise ValueError("Dense fork index must be 0..9")
    expected = {("reference" if t == greedy else "alternative", int(t)) for t in fork["selected_tokens"]}
    expected.add(("null", greedy))
    if fork["residual_mass"] > 0:
        expected.add(("residual", None))
    all_records = read_snapshot(store_directory)["records"]
    collection_keys = {canonical({k: v for k, v in m["identity"].items()
                                 if k not in {"role", "position", "token", "prefix", "sample_count"}})
                       for m, _ in all_records}
    if len(collection_keys) != 1:
        raise ValueError("Mixed or missing window scopes; use isolated window stores")
    collection_identity = json.loads(next(iter(collection_keys)))
    records = [(m, a) for m, a in all_records
               if m["identity"]["position"] == b and (m["identity"]["role"], m["identity"]["token"]) in expected]
    identities = [(m["identity"]["role"], m["identity"]["token"]) for m, _ in records]
    if len(records) != len(expected) or set(identities) != expected:
        raise ValueError("Cannot finalize an incomplete or duplicated fork")
    weights = np.asarray(fork["selected_weights"], dtype=float)
    if len(weights) != len(fork["selected_tokens"]) or (weights < 0).any() or not np.isclose(weights.sum() + fork["residual_mass"], 1., atol=1e-10, rtol=0):
        raise ValueError("Invalid fork mixture mass")
    objects = []
    for manifest, _ in records:
        path = store_directory / manifest["task_id"] / "manifest.json"
        relative = Path(os.path.relpath(path.parent, directory)).as_posix()
        objects.append({"task_id": manifest["task_id"], "relative_directory": relative,
                        "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    result = {"schema": "chronos_complete_fork_v1", "fork": fork, "objects": objects}
    # Legacy parents retain their original schema/content; new scoped stores bind
    # the entire collection identity before the manifest becomes visible.
    if (store_directory / "_scope.json").exists():
        result["collection_identity"] = collection_identity
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"b{b:02d}.json"
    if destination.exists():
        if canonical(json.loads(destination.read_text(encoding="utf-8"))) != canonical(result):
            raise ValueError("Refusing to replace a different finalized fork")
    else:
        save_json(destination, result)
    return result


def read_fork_snapshot(directory, expected_scope=None):
    """Read finalized fork manifests and bound object hashes, without any writes."""
    directory = Path(directory)
    paths = sorted(directory.glob("b[0-9][0-9].json"))
    forks, hashes = [], {}
    for path in paths:
        content = path.read_bytes()
        manifest = json.loads(content)
        if manifest.get("schema") != "chronos_complete_fork_v1":
            raise ValueError("Unsupported fork schema")
        collection = manifest.get("collection_identity")
        if expected_scope is not None and (collection is None or any(collection.get(k) != v for k, v in expected_scope.items())):
            raise ValueError("Fork belongs to another window/seed scope")
        seen_collections = set()
        for obj in manifest["objects"]:
            target = (directory / obj["relative_directory"]).resolve()
            if not target.is_relative_to(directory.parent.resolve()):
                raise ValueError("Fork object escapes its run")
            raw = (target / "manifest.json").read_bytes()
            if hashlib.sha256(raw).hexdigest() != obj["manifest_sha256"]:
                raise ValueError("Finalized fork object metadata checksum mismatch")
            record, _ = read_object(target)
            if record["task_id"] != obj["task_id"]:
                raise ValueError("Finalized fork object identity mismatch")
            key = {k: v for k, v in record["identity"].items()
                   if k not in {"role", "position", "token", "prefix", "sample_count"}}
            seen_collections.add(canonical(key))
            if collection is not None and key != collection:
                raise ValueError("Foreign window child in finalized fork")
        if len(seen_collections) != 1:
            raise ValueError("Mixed window identities in finalized fork")
        forks.append(manifest)
        hashes[path.name] = hashlib.sha256(content).hexdigest()
    return {"snapshot_id": task_id(hashes), "forks": forks, "manifest_sha256": hashes}
