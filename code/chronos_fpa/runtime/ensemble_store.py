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
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def get(self, identity):
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
        publish_directory(path, self.directory / manifest["task_id"])
        return manifest["task_id"]


def read_snapshot(directory, object_ids=None):
    """No mkdir, recovery, export writes or RNG restoration; freeze IDs first."""
    directory = Path(directory)
    names = sorted(p.name for p in directory.iterdir()
                   if p.is_dir() and re.fullmatch("[0-9a-f]{64}", p.name)) if object_ids is None else sorted(object_ids)
    if len(set(names)) != len(names) or any(not re.fullmatch("[0-9a-f]{64}", name) for name in names):
        raise ValueError("Snapshot IDs must be distinct finalized ensemble hashes")
    records, hashes = [], {}
    for name in names:
        path = directory / name
        manifest, arrays = read_object(path)
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
    records = [(m, a) for m, a in read_snapshot(store_directory)["records"]
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
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"b{b:02d}.json"
    if destination.exists():
        if canonical(json.loads(destination.read_text(encoding="utf-8"))) != canonical(result):
            raise ValueError("Refusing to replace a different finalized fork")
    else:
        save_json(destination, result)
    return result


def read_fork_snapshot(directory):
    """Read finalized fork manifests and bound object hashes, without any writes."""
    directory = Path(directory)
    paths = sorted(directory.glob("b[0-9][0-9].json"))
    forks, hashes = [], {}
    for path in paths:
        content = path.read_bytes()
        manifest = json.loads(content)
        if manifest.get("schema") != "chronos_complete_fork_v1":
            raise ValueError("Unsupported fork schema")
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
        forks.append(manifest)
        hashes[path.name] = hashlib.sha256(content).hexdigest()
    return {"snapshot_id": task_id(hashes), "forks": forks, "manifest_sha256": hashes}
