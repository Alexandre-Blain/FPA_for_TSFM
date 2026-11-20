import numpy as np
import pytest

import ensemble_store
from ensemble_store import EnsembleStore, read_snapshot


def sample_arrays(value=3):
    return {"tokens": np.full((2, 32), value, dtype=np.int64),
            "values": np.full((2, 32), float(value), dtype=np.float32)}


def test_finalized_ensemble_resume_and_fixed_reader_snapshot(tmp_path):
    store = EnsembleStore(tmp_path)
    store.put({"role": "reference", "seed": 7}, sample_arrays(), {"captured": "tokens/values"})
    snapshot = read_snapshot(tmp_path)
    source_hash = snapshot["manifest_sha256"].copy()
    store.put({"role": "null", "seed": 8}, sample_arrays(4), {})
    frozen = read_snapshot(tmp_path, snapshot["object_ids"])
    assert frozen["snapshot_id"] == snapshot["snapshot_id"] and frozen["manifest_sha256"] == source_hash
    assert len(read_snapshot(tmp_path)["records"]) == 2
    _, arrays = store.get({"role": "reference", "seed": 7})
    np.testing.assert_array_equal(arrays["tokens"], sample_arrays()["tokens"])
    with pytest.raises(ValueError, match="conflicting"):
        store.put({"role": "reference", "seed": 7}, sample_arrays(9), {})


def test_reader_never_sees_pending_and_explicit_recovery_uses_existing_bytes(tmp_path, monkeypatch):
    store = EnsembleStore(tmp_path)
    publish = ensemble_store.publish_directory
    observed = []

    def interrupt(source, destination):
        observed.append(len(read_snapshot(tmp_path)["records"]))
        raise OSError("interrupted before directory publication")

    monkeypatch.setattr(ensemble_store, "publish_directory", interrupt)
    with pytest.raises(OSError):
        store.put({"role": "residual"}, sample_arrays(), {})
    assert observed == [0] and read_snapshot(tmp_path)["records"] == []
    pending = next(tmp_path.glob(".pending-*"))
    archive = (pending / "arrays.npz").read_bytes()
    monkeypatch.setattr(ensemble_store, "publish_directory", publish)
    identifier = store.recover_pending(pending)
    assert (tmp_path / identifier / "arrays.npz").read_bytes() == archive
    assert len(read_snapshot(tmp_path)["records"]) == 1


def test_corrupted_ensemble_is_rejected_without_repair(tmp_path):
    store = EnsembleStore(tmp_path)
    store.put({"role": "direct_cpd", "prefix_length": 11}, sample_arrays(), {})
    destination = next(p for p in tmp_path.iterdir() if not p.name.startswith("."))
    np.savez_compressed(destination / "arrays.npz", **sample_arrays(9))
    with pytest.raises(ValueError, match="checksum"):
        read_snapshot(tmp_path)
