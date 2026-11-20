"""One-window opt-in sampler, including residual and fixed-outcome CPD inputs."""
from __future__ import annotations

import hashlib
import time

import numpy as np
import torch

from chronos_decoding import _ensemble_generator, _mask_to_chronos_value_tokens, decode_token_samples_to_values
from chronos_distances import context_iqr_scale
from chronos_exploratory import POLICY_VERSION, policy_probabilities, select_candidates
from chronos_outcomes import compare_fixed22_and_full, weighted_events, window_outcomes
from ensemble_store import publish_fork_manifest, task_id


def collect_window(engine, tokenizer, scale, context, store, provenance, *,
                   samples_per_group=20, direct_samples=60, seed=20261120,
                   batch_size=8, overlap_positions=(0, 9, 10)):
    """Frozen C512/H32 dense positions; caller explicitly labels micro sample N."""
    context = np.asarray(context, dtype=np.float32).reshape(-1)
    if len(context) != 512 or not np.isfinite(context).all():
        raise ValueError("A complete finite C512 context is required")
    scale_iqr, valid, _ = context_iqr_scale(context)
    if not valid:
        raise ValueError("Invalid context IQR; no implicit fallback")
    if samples_per_group <= 0 or direct_samples != 60 or batch_size <= 0:
        raise ValueError("Invalid group size, direct N60 or batch size")
    greedy_tokens = engine.greedy(32)
    greedy_values = decode_token_samples_to_values(tokenizer, greedy_tokens[None], scale)[0].numpy()
    shared = {**provenance, "context_sha256": hashlib.sha256(context.tobytes()).hexdigest(),
              "policy": POLICY_VERSION, "horizon": 32, "batch_size": batch_size,
              "sampling_seed": seed}
    if store.scope is not None:
        store._check_scope(shared)
    accounting = {"new_ensembles": 0, "reused_ensembles": 0, "new_paths": 0, "reused_paths": 0}
    timings, fork_rows, distances, outcomes, p10 = [], [], [], {}, None

    def ensemble(role, prefix, count, *, position, token=None, q=None, candidates=None):
        identity = {**shared, "role": role, "position": position, "token": token,
                    "prefix": list(prefix), "sample_count": count}
        previous = store.get(identity)
        if previous is not None:
            manifest, arrays = previous
            accounting["reused_ensembles"] += 1
            accounting["reused_paths"] += count
            timings.append({"role": role, "position": position, "token": token,
                            "reused": True, "generation_seconds": 0., "paths": count})
            return arrays
        generator, rng = _ensemble_generator(engine.model, seed, task_id(shared), task_id(identity))
        started = time.perf_counter()
        if role == "residual":
            tokens = engine.sample_residual(prefix, q, candidates, 32, count, generator)
        else:
            tokens = engine.sample(prefix, 32, count, generator, batch_size=batch_size)
        values = decode_token_samples_to_values(tokenizer, tokens, scale).numpy()
        arrays = {"tokens": tokens.numpy(), "values": values,
                  "context": context, "greedy_tokens": greedy_tokens.numpy(), "greedy_values": greedy_values}
        elapsed = time.perf_counter() - started
        metadata = {"rng": rng, "generation_seconds": elapsed,
                    "coordinate_convention": "complete forecast 0..31; forced b excluded from distances",
                    "captured_fields": ["full_tokens", "numeric_values", "context", "full_greedy_tokens", "full_greedy_values"],
                    "omitted_replayable_fields": ["logits", "hidden_states", "attentions"],
                    "prefix_conditioning": "start token and all previous generated tokens; private mutable self-KV"}
        if role == "residual":
            metadata.update(residual_ids=list(candidates.residual_ids), residual_mass=candidates.residual_mass)
        store.put(identity, arrays, metadata)
        accounting["new_ensembles"] += 1
        accounting["new_paths"] += count
        timings.append({"role": role, "position": position, "token": token,
                        "reused": False, "generation_seconds": elapsed, "paths": count})
        return arrays

    for b in range(10):
        prefix = greedy_tokens[:b].tolist()
        logits = engine.prefix_state(prefix).logits
        q = policy_probabilities(logits, engine.config)[0].detach().cpu()
        p_sel = torch.softmax(_mask_to_chronos_value_tokens(logits, engine.config), dim=-1)[0].cpu()
        greedy = int(greedy_tokens[b])
        selected = select_candidates(q, greedy)
        groups = {}
        for token in selected.token_ids:
            groups[token] = ensemble("reference" if token == greedy else "alternative",
                                     prefix + [token], samples_per_group, position=b, token=token)
        reference = groups[greedy]
        null = ensemble("null", prefix + [greedy], samples_per_group, position=b, token=greedy)
        event_ensembles = [window_outcomes(groups[t]["values"], greedy_values, scale_iqr)["events"]
                           for t in selected.token_ids]
        weights = list(selected.weights)
        if selected.residual_mass > 0:
            residual = ensemble("residual", prefix, samples_per_group, position=b,
                                q=q, candidates=selected)
            event_ensembles.append(window_outcomes(residual["values"], greedy_values, scale_iqr)["events"])
            weights.append(selected.residual_mass)
        outcomes[str(b)] = {**weighted_events(event_ensembles, weights), "method": "q50_weighted_conditional_mixture"}
        null_metrics, _ = compare_fixed22_and_full(reference["values"], null["values"], b, context)
        for token in selected.token_ids:
            if token == greedy:
                continue
            metrics, profile = compare_fixed22_and_full(reference["values"], groups[token]["values"], b, context)
            distances.append({"b": b, "token": token, "p_sel": float(p_sel[token]),
                              "q50": selected.weights[selected.token_ids.index(token)],
                              **metrics, "w1_profile": profile.tolist(),
                              "same_token_null": null_metrics})
        support = torch.where(q > 0)[0].tolist()
        q_normalized = q.double() / q.double().sum()
        p_positive = p_sel[p_sel > 0].double()
        fork_rows.append({"b": b, "greedy_token": greedy,
                          "selected_tokens": list(selected.token_ids), "selected_weights": list(selected.weights),
                          "p_sel_selected": [float(p_sel[t]) for t in selected.token_ids],
                          "selected_mass": selected.selected_mass, "residual_mass": selected.residual_mass,
                          "residual_ids": list(selected.residual_ids), "target_attained": selected.target_attained,
                          "q50_support_ids": support, "q50_support_weights": (q.double() / q.double().sum())[support].tolist(),
                          "entropy_q50_nats": float(-(q_normalized[q_normalized > 0] * q_normalized[q_normalized > 0].log()).sum()),
                          "entropy_p_sel_nats": float(-(p_positive * p_positive.log()).sum()),
                          "sampling_temperature": 1., "sample_top_k": 50, "top_p": 1.})
        publish_fork_manifest(store.directory.parent / "forks", store.directory, fork_rows[-1])
        if b == 9:
            p10 = window_outcomes(reference["values"], greedy_values, scale_iqr)["events"]
    outcomes["10"] = {**weighted_events([p10], [1.]), "method": "reuse_b9_forced_greedy"}
    for t in range(11, 16):
        values = ensemble("direct_cpd", greedy_tokens[:t].tolist(), direct_samples, position=t)["values"]
        events = window_outcomes(values, greedy_values, scale_iqr)["events"]
        outcomes[str(t)] = {**weighted_events([events], [1.]), "method": "direct_N60"}
    overlap = {}
    for t in overlap_positions:
        values = ensemble("overlap_direct", greedy_tokens[:t].tolist(), direct_samples, position=t)["values"]
        estimate = weighted_events([window_outcomes(values, greedy_values, scale_iqr)["events"]], [1.])
        overlap[str(t)] = {**estimate, "difference_from_primary": estimate["event_probability"] - outcomes[str(t)]["event_probability"]}
    return {"accounting": accounting, "forks": fork_rows, "distances": distances,
            "outcome_distributions": outcomes, "overlap_calibration": overlap,
            "timings": timings, "greedy_tokens": greedy_tokens.numpy(), "greedy_values": greedy_values,
            "context_iqr": scale_iqr, "samples_per_group": samples_per_group,
            "direct_samples": direct_samples, "sampling_policy": POLICY_VERSION,
            "interpretation": "micro validation only; conditional MC errors are not population CIs or formal CPD"}
