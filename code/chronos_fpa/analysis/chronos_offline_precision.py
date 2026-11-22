"""Offline empirical-law diagnostics. No decoder, model or network imports."""
from __future__ import annotations

import numpy as np

from chronos_distances import empirical_w1_by_horizon


def supports(b):
    if not 0 <= b <= 9:
        raise ValueError("Pilot positions are 0..9")
    return {"full": np.arange(b + 1, 32), "relative22": np.arange(b + 1, b + 23),
            "absolute22": np.arange(10, 32), "final8": np.arange(24, 32)}


def transform(paths, mode):
    x = np.asarray(paths, dtype=float)
    if mode == "raw":
        return x
    if mode == "centered":
        return x - x.mean(axis=-1, keepdims=True)
    if mode == "differenced":
        return np.diff(x, axis=-1)
    raise ValueError(mode)


def energy_matrices(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[1] or not a.shape[1]:
        raise ValueError("Nonempty equal coordinate supports required")
    def distance(x, y):
        return np.linalg.norm(x[:, None, :] - y[None, :, :], axis=-1) / np.sqrt(x.shape[1])
    return distance(a, b), distance(a, a), distance(b, b)


def energy_from_weights(matrices, wa, wb, unbiased=False):
    """Row(s) of normalized empirical frequencies; U excludes draw diagonals.

    Repeated observations selected by bootstrap are distinct resampled draws.
    Thus n/(n-1) multiplies within V terms, including zero distances of repeats.
    """
    ab, aa, bb = matrices
    wa, wb = np.asarray(wa), np.asarray(wb)
    cross = np.einsum("...i,ij,...j->...", wa, ab, wb, optimize=False)
    within_a = np.einsum("...i,ij,...j->...", wa, aa, wa, optimize=False)
    within_b = np.einsum("...i,ij,...j->...", wb, bb, wb, optimize=False)
    if unbiased:
        na, nb = unbiased
        if min(na, nb) < 2:
            raise ValueError("U statistic requires at least two draws per law")
        within_a = within_a * na / (na - 1)
        within_b = within_b * nb / (nb - 1)
    return 2 * cross - within_a - within_b


def distances(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    matrices = energy_matrices(a, b)
    weights = np.ones(len(a)) / len(a), np.ones(len(b)) / len(b)
    return {"w1": float(empirical_w1_by_horizon(a, b).mean()),
            "ed": float(energy_from_weights(matrices, *weights)),
            "ed_u": float(energy_from_weights(matrices, *weights, unbiased=(len(a), len(b))))}


def counts(indices, n):
    indices = np.asarray(indices)
    result = np.zeros((len(indices), n))
    np.add.at(result, (np.arange(len(indices))[:, None], indices), 1 / indices.shape[1])
    return result


def bootstrap_distances(a, b, ia, ib):
    """Equal-N whole-path bootstrap, caller owns shared-reference indices."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if ia.shape != ib.shape:
        raise ValueError("Equal-N bootstrap indices required")
    wa, wb = counts(ia, len(a)), counts(ib, len(b))
    matrices = energy_matrices(a, b)
    n = ia.shape[1]
    return {"w1": np.abs(np.sort(a[ia], axis=1) - np.sort(b[ib], axis=1)).mean(axis=(1, 2)),
            "ed": energy_from_weights(matrices, wa, wb),
            "ed_u": energy_from_weights(matrices, wa, wb, unbiased=(n, n))}


def permutation_distances(a, b, permutations, rng):
    """Exchange whole paths; plus-one upper-tail diagnostics for W1 and ED-V."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    n, m = len(a), len(b)
    if n != m:
        raise ValueError("This diagnostic uses equal sample counts")
    z = np.concatenate((a, b))
    order = np.argsort(rng.random((permutations, n + m)), axis=1)
    ia, ib = order[:, :n], order[:, n:]
    w1 = np.abs(np.sort(z[ia], axis=1) - np.sort(z[ib], axis=1)).mean(axis=(1, 2))
    dd = energy_matrices(z, z)[0]
    wa, wb = counts(ia, n + m), counts(ib, n + m)
    ed = energy_from_weights((dd, dd, dd), wa, wb)
    observed = distances(a, b)
    return {"p_" + key: float((1 + np.sum(values >= observed[key] - 1e-12)) / (permutations + 1))
            for key, values in (("w1", w1), ("ed", ed))}


def pool_designs():
    """Indices into three independent N20 streams, with explicit row identity."""
    designs = {f"N20_s{i}": np.arange(20 * i, 20 * (i + 1)) for i in range(3)}
    for i in range(3):
        for j in range(3):
            if i != j:
                designs[f"N30_s{i}_s{j}first10"] = np.r_[designs[f"N20_s{i}"], np.arange(20*j, 20*j+10)]
    designs["N30_disjointB"] = np.r_[designs["N20_s2"], np.arange(30, 40)]
    for i, j in ((0, 1), (0, 2), (1, 2)):
        designs[f"N40_s{i}_s{j}"] = np.r_[designs[f"N20_s{i}"], designs[f"N20_s{j}"]]
    designs["N60_all"] = np.arange(60)
    return designs


def assert_pool_compatible(manifests):
    """Only sampling seed may differ in immutable conditional identities."""
    identities = [{k: v for k, v in m["identity"].items() if k != "sampling_seed"} for m in manifests]
    if any(i != identities[0] for i in identities[1:]):
        raise ValueError("Cannot pool different conditional identities")
    streams = [m["metadata"]["rng"]["stream_id"] for m in manifests]
    seeds = [m["metadata"]["rng"]["seed"] for m in manifests]
    if len(set(streams)) != len(streams) or len(set(seeds)) != len(seeds):
        raise ValueError("Independent streams/seeds required")


def weighted_w1(x, wx, y, wy):
    """Exact scalar empirical W1; batch weights supported for path bootstrap."""
    x, y = np.asarray(x), np.asarray(y)
    wx, wy = np.asarray(wx), np.asarray(wy)
    if x.ndim != 1 or y.ndim != 1 or wx.shape[-1] != len(x) or wy.shape[-1] != len(y):
        raise ValueError("One weight per scalar observation")
    if (not np.isfinite(x).all() or not np.isfinite(y).all()
            or not np.isfinite(wx).all() or not np.isfinite(wy).all()
            or np.any(wx < 0) or np.any(wy < 0)
            or not np.allclose(wx.sum(axis=-1), 1) or not np.allclose(wy.sum(axis=-1), 1)):
        raise ValueError("Finite probability distributions required")
    z = np.r_[x, y]
    order = np.argsort(z, kind="stable")
    batch = np.broadcast_shapes(wx.shape[:-1], wy.shape[:-1])
    wx = np.broadcast_to(wx, batch + (len(x),))
    wy = np.broadcast_to(wy, batch + (len(y),))
    signed = np.concatenate((wx, -wy), axis=-1)
    cdf = np.cumsum(signed[..., order], axis=-1)
    return np.sum(np.abs(cdf[..., :-1]) * np.diff(z[order]), axis=-1)


def variance_partition(groups, weights):
    """Unbiased within and between (coarsened partition) at each coordinate.

    E[sum w_i (m_i-mbar)^2] = between + sum w_i(1-w_i) Var(m_i)
    for independent group mean estimates and deterministic weights.
    """
    weights = np.asarray(weights, dtype=float)
    if len(groups) != len(weights) or np.any(weights < 0) or not np.isclose(weights.sum(), 1):
        raise ValueError("Probability weights required")
    if any(len(g) < 2 for g in groups):
        raise ValueError("At least two trajectories per group")
    means = np.stack([np.asarray(g, dtype=float).mean(axis=0) for g in groups])
    variances = np.stack([np.asarray(g, dtype=float).var(axis=0, ddof=1) for g in groups])
    w = weights[:, None]
    grand = np.sum(w * means, axis=0)
    between = np.sum(w * (means - grand) ** 2, axis=0)
    bias = np.sum(w * (1-w) * variances / np.array([len(g) for g in groups])[:, None], axis=0)
    within = np.sum(w * variances, axis=0)
    return {"within": within, "between_plugin": between, "between_bias": bias,
            "between_corrected": between-bias, "total_corrected": within+between-bias}


def event_contributions(groups, weights):
    """Greedy group first; include the residual as an explicit coarsened group."""
    means = np.stack([np.asarray(g, dtype=float).mean(axis=0) for g in groups])
    weights = np.asarray(weights)
    if not np.isclose(weights.sum(), 1) or np.any(weights < 0):
        raise ValueError("Probability weights required")
    contributions = weights[1:, None] * (means[1:] - means[0])
    lhs = weights @ means - means[0]
    return lhs, contributions


def holm(p):
    p = np.asarray(p)
    order = np.argsort(p)
    adjusted = np.maximum.accumulate(p[order] * np.arange(len(p), 0, -1))
    result = np.empty_like(p)
    result[order] = np.minimum(adjusted, 1)
    return result
