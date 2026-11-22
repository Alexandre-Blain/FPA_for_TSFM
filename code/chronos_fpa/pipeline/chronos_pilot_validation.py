"""Read-only validation of a complete local pilot cell and its estimands."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from chronos_outcomes import compare_fixed22_and_full, weighted_events, window_outcomes
from ensemble_store import read_fork_snapshot, read_snapshot


def validate_cell(directory, scope, results, *, direct_samples=60):
    directory = Path(directory)
    snapshot = read_snapshot(directory / "ensembles", expected_scope=scope)
    parents = read_fork_snapshot(directory / "forks", expected_scope=scope)
    if len(parents["forks"]) != 10 or [f["fork"]["b"] for f in parents["forks"]] != list(range(10)):
        raise ValueError("Ten complete dense forks required")
    records = snapshot["records"]
    lookup = {(m["identity"]["position"], m["identity"]["role"], m["identity"]["token"]): (m, a)
              for m, a in records}
    if len(lookup) != len(records):
        raise ValueError("Duplicated ensemble roles")
    expected = set()
    greedy = np.asarray(results["greedy_tokens"])
    greedy_values = np.asarray(results["greedy_values"])
    iqr = results["context_iqr"]
    groups_by_position = {}
    for manifest, arrays in records:
        identity = manifest["identity"]
        count = direct_samples if identity["role"] in {"direct_cpd", "overlap_direct"} else 20
        if arrays["tokens"].shape != (count, 32) or identity["sample_count"] != count:
            raise ValueError("H32/N20/N60 shape mismatch")
        context = arrays["context"]
        if hashlib.sha256(context.tobytes()).hexdigest() != scope["context_sha256"]:
            raise ValueError("Context mismatch")
        prefix = identity["prefix"]
        if not np.all(arrays["tokens"][:, :len(prefix)] == np.asarray(prefix)[None]):
            raise ValueError("Forced prefix mismatch")
        np.testing.assert_array_equal(arrays["greedy_tokens"], greedy)
        np.testing.assert_array_equal(arrays["greedy_values"], greedy_values)
    for b, parent in enumerate(parents["forks"]):
        fork = results["forks"][b]
        if parent["fork"] != fork or fork["greedy_token"] != int(greedy[b]):
            raise ValueError("Fork summary differs from immutable parent")
        tokens, weights = fork["selected_tokens"], fork["selected_weights"]
        if not 1 <= len(tokens) <= 8 or tokens[0] != fork["greedy_token"]:
            raise ValueError("Candidate cap/greedy-first invariant")
        if not np.isclose(sum(weights) + fork["residual_mass"], 1., rtol=0, atol=1e-10):
            raise ValueError("Mixture mass mismatch")
        if fork["selected_mass"] < .9 and len(tokens) != 8:
            raise ValueError("Coverage below target without exhausting cap")
        groups = []
        for token in tokens:
            key = (b, "reference" if token == fork["greedy_token"] else "alternative", token)
            expected.add(key)
            groups.append(lookup[key][1])
        null_key = (b, "null", fork["greedy_token"])
        expected.add(null_key)
        null = lookup[null_key][1]
        null_metrics, _ = compare_fixed22_and_full(groups[0]["values"], null["values"], b, context)
        for token, alternative in zip(tokens[1:], groups[1:]):
            row = next(r for r in results["distances"] if r["b"] == b and r["token"] == token)
            metrics, profile = compare_fixed22_and_full(groups[0]["values"], alternative["values"], b, context)
            for name, value in metrics.items():
                if isinstance(value, str):
                    assert row[name] == value
                else:
                    np.testing.assert_allclose(row[name], value, rtol=1e-12, atol=1e-12)
            np.testing.assert_allclose(row["w1_profile"], profile, rtol=1e-12, atol=1e-12)
            for name, value in null_metrics.items():
                if isinstance(value, str):
                    assert row["same_token_null"][name] == value
                else:
                    np.testing.assert_allclose(row["same_token_null"][name], value, rtol=1e-12, atol=1e-12)
        if fork["residual_mass"] > 0:
            key = (b, "residual", None)
            expected.add(key)
            residual = lookup[key][1]
            if not set(residual["tokens"][:, b]).issubset(fork["residual_ids"]):
                raise ValueError("Residual draws outside complementary support")
            groups.append(residual)
            weights = weights + [fork["residual_mass"]]
        groups_by_position[b] = (groups, weights)
        estimate = weighted_events([window_outcomes(a["values"], greedy_values, iqr)["events"] for a in groups], weights)
        np.testing.assert_allclose(estimate["event_probability"], results["outcome_distributions"][str(b)]["event_probability"], atol=1e-12)
    for position in range(10, 16):
        if position == 10:
            arrays = lookup[(9, "reference", int(greedy[9]))][1]
        else:
            key = (position, "direct_cpd", None)
            expected.add(key)
            arrays = lookup[key][1]
        estimate = window_outcomes(arrays["values"], greedy_values, iqr)["events"].mean(axis=0)
        np.testing.assert_allclose(estimate, results["outcome_distributions"][str(position)]["event_probability"], atol=1e-12)
    for position in (0, 9, 10):
        key = (position, "overlap_direct", None)
        expected.add(key)
        arrays = lookup[key][1]
        estimate = window_outcomes(arrays["values"], greedy_values, iqr)["events"].mean(axis=0)
        np.testing.assert_allclose(estimate, results["overlap_calibration"][str(position)]["event_probability"], atol=1e-12)
    if expected != set(lookup):
        raise ValueError("Missing or unexpected cell ensemble")
    return {"snapshot_id": snapshot["snapshot_id"], "object_ids": snapshot["object_ids"],
            "manifest_sha256": snapshot["manifest_sha256"], "fork_snapshot_id": parents["snapshot_id"],
            "fork_manifest_sha256": parents["manifest_sha256"], "ensembles": len(records),
            "paths": sum(len(a["tokens"]) for _, a in records), "validated_forks": 10,
            "records": records, "lookup": lookup, "groups_by_position": groups_by_position}


def read_complete_cell(directory, scope, *, direct_samples=60):
    directory = Path(directory)
    marker = json.loads((directory / "complete.json").read_text(encoding="utf-8"))
    if marker["scope"] != scope or marker["status"] != "complete":
        raise ValueError("Complete marker scope/status mismatch")
    for name, digest in marker["files"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Completed cell file checksum mismatch")
    results = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    validation = validate_cell(directory, scope, results, direct_samples=direct_samples)
    for key in ("snapshot_id", "fork_snapshot_id", "manifest_sha256", "fork_manifest_sha256", "ensembles", "paths"):
        if marker["validation"][key] != validation[key]:
            raise ValueError(f"Complete cell changed: {key}")
    return marker, results, validation
