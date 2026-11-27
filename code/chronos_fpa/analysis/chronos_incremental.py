"""Frozen, target-free features and probability estimators for campaign H1/H2.

The estimand is the effective q50 policy, not the untruncated model softmax.
Stratification and importance sampling are classical Monte Carlo methods.
"""
from __future__ import annotations

import numpy as np

EVENT_NAMES = ('downside_8_31', 'upside_8_31', 'late_mean_downside', 'terminal_direction_disagreement')


def future_events(paths, context, greedy):
    a, c, g = map(lambda x: np.asarray(x, dtype=float), (paths, context, greedy))
    scale = float(np.subtract(*np.percentile(c, [75, 25])))
    if a.ndim != 2 or a.shape[1] != 32 or g.shape != (32,) or not np.isfinite(a).all():
        raise ValueError('Complete finite H32 paths required')
    if not np.isfinite(scale) or scale <= 1e-12:
        raise ValueError('Positive context IQR required')
    z = (a-c[-1])/scale
    def direction(x):
        return np.where(x > .05, 1, np.where(x < -.05, -1, 0))
    return np.column_stack((z[:, 8:32].min(1) <= -1,
        z[:, 8:32].max(1) >= 1, z[:, 24:32].mean(1) <= -.5,
        direction(z[:, 31]) != direction((g[31]-c[-1])/scale)))


def checked_probabilities(probabilities):
    if any(not np.isfinite(v) or v < 0 for v in probabilities.values()):
        raise ValueError('Invalid token probability')
    q = {int(t): float(v) for t, v in probabilities.items() if v > 0}
    if not q or not np.isfinite(list(q.values())).all() or min(q.values()) <= 0:
        raise ValueError('Finite positive token support required')
    if not np.isclose(sum(q.values()), 1., atol=8*np.finfo(np.float32).eps, rtol=0):
        raise ValueError('Token probability mass not normalized')
    # q comes from float32 softmax; normalize its complete support once in
    # float64. The sampler uses the same complete-support relative weights.
    total = sum(q.values())
    return {t: v/total for t, v in q.items()}


def sparse_tokens(probabilities, greedy, maximum=5):
    q = checked_probabilities(probabilities)
    if greedy not in q or maximum < 2:
        raise ValueError('Greedy must be in support')
    ranked = sorted(q, key=lambda t: (-q[t], t))
    chosen = [greedy]
    for t in ranked:
        if t not in chosen and len(chosen) < maximum-1:
            chosen.append(t)
    remaining = [t for t in q if t not in chosen]
    if remaining:
        # Quantizer IDs are monotone numerical bins. Prefer an extreme
        # outside the probability-ranked set, with deterministic ID ties.
        chosen.append(max(remaining, key=lambda t: (min(abs(t-s) for s in chosen), -t)))
    return chosen


def first_token_partition(forks):
    f = forks[0]; q = checked_probabilities(f['probabilities']); g = f['greedy']
    ranked = sorted((t for t in q if t != g), key=lambda t: (-q[t], t))
    selected = [g] + ranked[:2]
    groups = [{'name': f'token_{t}', 'prefix': [], 'position': 0,
               'support': [t], 'weight': q[t]} for t in selected]
    residual = sorted(set(q)-set(selected))
    if residual:
        groups.append({'name': 'residual', 'prefix': [], 'position': 0,
                       'support': residual, 'weight': sum(q[t] for t in residual)})
    validate_partition(groups)
    return groups


def first_deviation_partition(forks):
    if len(forks) < 5:
        raise ValueError('Greedy decisions b0..b4 required')
    groups = []; prefix = []; mass = 1.
    for b, f in enumerate(forks[:5]):
        q = checked_probabilities(f['probabilities']); g = f['greedy']
        if g not in q:
            raise ValueError('Greedy token absent')
        other = sorted((t for t in q if t != g), key=lambda t: (-q[t], t))
        for name, support in [('highest', other[:1]), ('remaining', other[1:])]:
            if support:
                groups.append({'name': f'b{b}_{name}', 'prefix': list(prefix),
                    'position': b, 'support': support,
                    'weight': mass*sum(q[t] for t in support)})
        mass *= q[g]; prefix.append(g)
    if mass > 0:
        groups.append({'name': 'all_five_greedy', 'prefix': prefix,
                       'position': 5, 'support': [], 'weight': mass})
    validate_partition(groups)
    return groups


def validate_partition(groups):
    w = np.array([s['weight'] for s in groups])
    if not len(w) or (w <= 0).any() or not np.isfinite(w).all() or not np.isclose(w.sum(), 1., atol=1e-12, rtol=0):
        raise ValueError('Positive exhaustive partition weights must sum to one')
    for i, a in enumerate(groups):
        for b in groups[i+1:]:
            ap, bp = a['prefix'], b['prefix']
            common = min(len(ap), len(bp))
            if ap[:common] != bp[:common]:
                continue
            if len(ap) == len(bp):
                if not a['support'] or not b['support'] or set(a['support']) & set(b['support']):
                    raise ValueError('Overlapping strata')
            else:
                short, long = (a, b) if len(ap) < len(bp) else (b, a)
                if not short['support'] or long['prefix'][len(short['prefix'])] in short['support']:
                    raise ValueError('Overlapping prefix strata')


def stratified_estimate(events, weights, alpha=.05):
    arrays = [np.asarray(a, dtype=float) for a in events]
    w = np.asarray(weights, dtype=float)
    if len(w) != len(arrays) or not np.isfinite(w).all() or not np.isclose(w.sum(), 1., atol=1e-12, rtol=0) or (w <= 0).any() or not 0 < alpha < 1:
        raise ValueError('Invalid stratum weights')
    if any(a.ndim != 2 or len(a) < 2 or not np.isin(a, [0, 1]).all() or a.shape[1] != arrays[0].shape[1] for a in arrays):
        raise ValueError('At least two independent binary paths per stratum required')
    means = np.stack([a.mean(0) for a in arrays])
    estimate = w @ means
    variance = np.sum(w[:, None]**2 * np.stack([a.var(0, ddof=1)/len(a) for a in arrays]), axis=0)
    radius = np.sqrt(.5*np.log(2/alpha)*sum(x*x/len(a) for x, a in zip(w, arrays)))
    return {'probability': estimate, 'variance': variance,
        'lo': np.maximum(0, estimate-radius), 'hi': np.minimum(1, estimate+radius),
        'interval': 'pointwise finite-sample Hoeffding, fixed allocation conditional on independent pilot'}


def importance_estimate(strata, events, weights, proposal, alpha=.05):
    j, a, w, p = np.asarray(strata, int), np.asarray(events, float), np.asarray(weights, float), np.asarray(proposal, float)
    if len(p) != len(w) or (p <= 0).any() or (w <= 0).any() or not np.isfinite(p).all() or not np.isfinite(w).all() or not np.isclose(p.sum(), 1, atol=1e-12, rtol=0) or not np.isclose(w.sum(), 1, atol=1e-12, rtol=0) or not 0 < alpha < 1:
        raise ValueError('Importance proposal must cover every positive stratum')
    if a.ndim != 2 or len(a) != len(j) or len(j) < 2 or not np.isin(a, [0, 1]).all() or (j < 0).any() or (j >= len(w)).any():
        raise ValueError('Independent proposal draws and binary events required')
    likelihood = w[j]/p[j]; samples = likelihood[:, None]*a
    estimate = samples.mean(0); radius = np.max(w/p)*np.sqrt(np.log(2/alpha)/(2*len(j)))
    return {'probability': estimate, 'variance': samples.var(0, ddof=1)/len(j),
        'lo': np.clip(estimate-radius,0,1), 'hi': np.clip(estimate+radius,0,1),
        'weight_ess_diagnostic': float(likelihood.sum()**2/(likelihood @ likelihood)),
        'interval': 'pointwise Hoeffding, endpoints projected to [0,1]; raw estimate not clipped or self-normalized'}


def budget_allocation(weights, costs, budget, strategy, variances=None, minimum=2):
    """Outcome-independent final allocation, given fixed independent pilot.

    Incremental allocation gives nested snapshots at increasing budgets. Every
    nonempty stratum is represented, or the whole combination is infeasible.
    """
    w, c = np.asarray(weights, float), np.asarray(costs, float)
    if not len(w) or len(w) != len(c) or (c <= 0).any() or not np.isfinite(c).all() or (w <= 0).any() or not np.isfinite(w).all() or not np.isfinite(budget) or minimum<2:
        raise ValueError('Positive weights and finite per-path costs required')
    n = np.full(len(w), minimum, dtype=int); spent = float(n @ c)
    if spent > budget + 1e-12:
        return None
    v = np.ones(len(w))*.25 if variances is None else np.asarray(variances, float)
    if strategy not in ('uniform', 'proportional', 'neyman_cost') or v.shape != w.shape or (v < 0).any() or not np.isfinite(v).all():
        raise ValueError('Unknown allocation or invalid pilot variances')
    while True:
        priorities = (1/(n+1) if strategy == 'uniform' else w/(n+1) if strategy == 'proportional'
                      else w*w*v/(n*(n+1)*c))
        k = int(np.argmax(priorities))
        if spent+c[k] > budget+1e-12:
            return n
        spent += c[k]; n[k] += 1


def decision_variance(groups, weights, token_probabilities, position, context):
    """Coarse-group and unbiased cross-block token variance components.

    Each group has 2 independent N20 blocks. Residual first-token matches use
    inverse conditional probabilities; this can be noisy and may be negative.
    No clipping or claim that the residual is a single actual token.
    """
    q = checked_probabilities(token_probabilities); w = np.asarray(weights, float)
    scale = float(np.subtract(*np.percentile(context, [75, 25])))
    ys = [(np.asarray(a['values'], float)[:, position+1:position+23]-context[-1])/scale for a in groups]
    if any(len(y) != 40 for y in ys) or len(w) != len(ys) or not np.isclose(w.sum(), 1):
        raise ValueError('Two complete independent N20 blocks per mixture group required')
    means = np.stack([y.mean(0) for y in ys]); mu = w @ means
    coarse = np.sum(w[:, None]*(means-mu)**2, axis=0)
    bias = np.sum((w*(1-w))[:, None]*np.stack([y.var(0, ddof=1)/40 for y in ys]), axis=0)
    mu1 = sum(weight*y[:20].mean(0) for weight, y in zip(w, ys))
    mu2 = sum(weight*y[20:].mean(0) for weight, y in zip(w, ys))
    second = np.zeros(22); cross = np.zeros(22)
    for weight, y, a in zip(w, ys, groups):
        tokens = np.asarray(a['tokens'])[:, position]
        second += weight*np.mean(y*y, axis=0)
        for token in set(map(int, tokens)):
            # E[sum matching products/(n1*n2) * R^2/q_t] = q_t m_t^2.
            # This also gives q_t*m1*m2 for a fixed single-token group.
            one = y[:20][tokens[:20] == token].sum(0)
            two = y[20:][tokens[20:] == token].sum(0)
            cross += weight*weight/q[token]*(one*two)/(20*20)
    token_between = cross-mu1*mu2
    total = second-mu1*mu2
    return {'between_group_corrected': float(np.mean(coarse-bias)),
            'between_token_crossblock': float(token_between.mean()),
            'within_token_crossblock': float((total-token_between).mean())}
