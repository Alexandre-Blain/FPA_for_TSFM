"""Direct distributional predictions of context-only numerical baselines."""
from __future__ import annotations

import hashlib
import numpy as np


def predicted_paths(reference, branch, jump, phi, coordinates, model):
    """k is absolute forecast coordinate minus b, including on late supports."""
    x = np.asarray(reference, dtype=float)
    coords = np.asarray(coordinates, dtype=int)
    if x.ndim != 2 or np.any(coords <= branch) or np.any(coords >= x.shape[1]):
        raise ValueError("Only strictly post-fork coordinates are allowed")
    if not np.isfinite(jump) or not np.isfinite(phi) or abs(phi) > 1+1e-12:
        raise ValueError("Finite jump and context lag1 in [-1,1] required")
    if model not in {"persistent", "ar1"}:
        raise ValueError(model)
    response = np.ones(len(coords)) if model == "persistent" else phi ** (coords-branch)
    return x[:, coords] + jump*response


def choose_contrasts(distances, seed, window_id):
    """First-block only: ED-first and W1-first, with deterministic ID ties.

    Up to two selected singleton alternatives; a random remaining contrast is
    evaluated on holdout only. Matched opposite alternatives are not adaptively
    added to the fresh validation budget. All dense matched pairs stay analyzed.
    """
    rows = list(distances)
    if not rows:
        return {"selected": [], "random_control": None}
    def best(metric, excluded):
        eligible = [r for r in rows if (r["b"],r["token"]) not in excluded]
        return min(eligible, key=lambda r:(-r[metric],r["b"],r["token"])) if eligible else None
    ed = best("ed_fixed22", set())
    first = (ed["b"], ed["token"])
    w = best("w1_fixed22", {first})
    selected = [first] + ([(w["b"],w["token"])] if w is not None else [])
    remaining = sorted({(r["b"],r["token"]) for r in rows}-set(selected))
    derived = int.from_bytes(hashlib.sha256(f"{seed}:{window_id}:control".encode()).digest()[:8],"big")
    control = remaining[int(np.random.default_rng(derived).integers(len(remaining)))] if remaining else None
    return {"selected": [list(k) for k in selected],
            "random_control": list(control) if control else None, "control_seed": derived,
            "rule": "highest ED_relative22; highest W1_relative22 among remaining; one uniform remaining control"}
