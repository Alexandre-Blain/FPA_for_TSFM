from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Dict, Iterable, List, Optional

import torch


def _maybe_tqdm(iterable, enabled: bool = True, **kwargs):
    if not enabled:
        return iterable
    try:
        from tqdm.auto import tqdm
    except Exception:
        return iterable
    return tqdm(iterable, **kwargs)


@dataclass
class TokenAlternative:
    rank: int
    token_id: int
    probability: float
    value: float
    is_base_token: bool
    top1_probability: float = float("nan")
    top2_probability: float = float("nan")
    top1_top2_margin: float = float("nan")
    token_entropy: float = float("nan")
    normalized_token_entropy: float = float("nan")
    top_k_probability_mass: float = float("nan")
    token_surprisal: float = float("nan")
    sampling_probability: float = float("nan")


@dataclass
class ForcedBranch:
    branch_id: str
    branch_kind: str
    branch_step: int
    forced_tokens: List[int]
    initial_token_id: int
    initial_token_rank: int
    initial_token_probability: float
    initial_token_value: float
    continuation_rank: Optional[int]
    is_base_branch: bool
    top1_probability: float = float("nan")
    top2_probability: float = float("nan")
    top1_top2_margin: float = float("nan")
    token_entropy: float = float("nan")
    normalized_token_entropy: float = float("nan")
    top_k_probability_mass: float = float("nan")
    initial_token_surprisal: float = float("nan")


def _decoder_start_token_id(model, chronos_config) -> int:
    value = getattr(model.config, "decoder_start_token_id", None)
    if value is None:
        value = chronos_config.pad_token_id
    if value is None:
        raise ValueError("Could not resolve decoder_start_token_id.")
    return int(value)


def _mask_to_chronos_value_tokens(logits: torch.Tensor, chronos_config) -> torch.Tensor:
    """Mask logits so generation stays in Chronos value-token bins.

    Chronos generation is fixed-length for forecasting, so EOS/PAD and all
    special tokens are forbidden during FPA decoding.
    """
    masked = logits.clone()
    masked[..., : chronos_config.n_special_tokens] = -torch.inf
    if 0 <= int(chronos_config.pad_token_id) < masked.shape[-1]:
        masked[..., int(chronos_config.pad_token_id)] = -torch.inf
    if 0 <= int(chronos_config.eos_token_id) < masked.shape[-1]:
        masked[..., int(chronos_config.eos_token_id)] = -torch.inf
    return masked


def _sample_from_logits(
    logits: torch.Tensor,
    chronos_config,
    temperature: float = 1.0,
    top_k: Optional[int] = None,
    do_sample: bool = True,
    show_progress: bool = False,
    progress_desc: str | None = None,
    progress_leave: bool = False,
    generator: Optional[torch.Generator] = None,
) -> torch.Tensor:
    logits = _mask_to_chronos_value_tokens(logits, chronos_config)
    if not do_sample:
        return torch.argmax(logits, dim=-1)

    logits = _sampling_logits(logits, temperature, top_k)
    probs = torch.softmax(logits, dim=-1)
    return torch.multinomial(probs, num_samples=1, generator=generator).squeeze(-1)


def _sampling_logits(masked_logits, temperature, top_k):
    if temperature <= 0:
        raise ValueError("temperature must be strictly positive when do_sample=True.")
    logits = masked_logits / temperature
    if top_k is not None and 0 < top_k < logits.shape[-1]:
        threshold = torch.topk(logits, k=top_k, dim=-1).values[..., -1, None]
        logits = torch.where(logits >= threshold, logits, torch.full_like(logits, -torch.inf))
    return logits


def _ensemble_generator(model, seed, namespace, role):
    identity = json.dumps([int(seed), namespace, role], separators=(",", ":"))
    digest = hashlib.sha256(identity.encode()).hexdigest()
    derived_seed = int(digest[:16], 16) % (2**63)
    device = next(model.parameters()).device
    generator = torch.Generator(device=device).manual_seed(derived_seed)
    return generator, {"stream_id": digest, "seed": derived_seed, "root_seed": int(seed),
                       "namespace": namespace, "role": role, "device": str(device)}


def _next_token_logits(model, input_ids, attention_mask, decoder_input_ids) -> torch.Tensor:
    out = model(
        input_ids=input_ids,
        attention_mask=attention_mask,
        decoder_input_ids=decoder_input_ids,
        use_cache=False,
    )
    return out.logits[:, -1, :]


def _distribution_topology(probs: torch.Tensor, top_k_mass_k: int) -> dict:
    """Summarize the local next-token probability geometry."""
    probs = probs.detach()
    finite = probs[torch.isfinite(probs)]
    finite = finite[finite > 0]
    if finite.numel() == 0:
        return {
            "top1_probability": float("nan"),
            "top2_probability": float("nan"),
            "top1_top2_margin": float("nan"),
            "token_entropy": float("nan"),
            "normalized_token_entropy": float("nan"),
            "top_k_probability_mass": float("nan"),
        }

    sorted_probs, _ = torch.sort(finite, descending=True)
    top1 = float(sorted_probs[0].cpu())
    top2 = float(sorted_probs[1].cpu()) if sorted_probs.numel() > 1 else 0.0
    entropy = float((-(finite * torch.log(finite))).sum().cpu())
    normalized_entropy = 0.0 if finite.numel() <= 1 else entropy / math.log(float(finite.numel()))
    mass_k = int(max(1, min(top_k_mass_k, sorted_probs.numel())))
    return {
        "top1_probability": top1,
        "top2_probability": top2,
        "top1_top2_margin": float(top1 - top2),
        "token_entropy": entropy,
        "normalized_token_entropy": normalized_entropy,
        "top_k_probability_mass": float(sorted_probs[:mass_k].sum().cpu()),
    }


@torch.no_grad()
def decode_tokens_manual(
    model,
    chronos_config,
    input_ids: torch.Tensor,
    attention_mask: torch.Tensor,
    prediction_length: int,
    num_samples: int = 1,
    forced_prefix_tokens: Optional[Iterable[int]] = None,
    temperature: float = 1.0,
    top_k: Optional[int] = None,
    do_sample: bool = True,
    show_progress: bool = False,
    progress_desc: str | None = None,
    progress_leave: bool = False,
    generator: Optional[torch.Generator] = None,
) -> torch.Tensor:
    """Autoregressively decode Chronos value-token IDs.

    Parameters
    ----------
    forced_prefix_tokens:
        Forecast token IDs to force at the beginning of the generated future.
        Example: for branch step h, pass base_tokens[:h] + [alternative_token].

    Returns
    -------
    torch.Tensor
        Shape [num_samples, prediction_length].
    """
    if input_ids.shape[0] != 1:
        raise ValueError("This implementation currently expects one context series at a time.")
    if prediction_length <= 0:
        raise ValueError("prediction_length must be positive.")
    if num_samples <= 0:
        raise ValueError("num_samples must be positive.")

    device = next(model.parameters()).device
    input_ids = input_ids.to(device)
    attention_mask = attention_mask.to(device)
    input_ids = input_ids.repeat(num_samples, 1)
    attention_mask = attention_mask.repeat(num_samples, 1)

    start_id = _decoder_start_token_id(model, chronos_config)
    decoder_input_ids = torch.full((num_samples, 1), start_id, device=device, dtype=torch.long)

    forced_prefix = list(forced_prefix_tokens or [])
    if len(forced_prefix) > prediction_length:
        raise ValueError("forced_prefix_tokens cannot be longer than prediction_length.")
    if any(int(token) < chronos_config.n_special_tokens or int(token) >= chronos_config.n_tokens
           or int(token) in {chronos_config.pad_token_id, chronos_config.eos_token_id}
           for token in forced_prefix):
        raise ValueError("Forced forecast prefixes must contain only valid value tokens")

    generated: List[torch.Tensor] = []
    step_iter = _maybe_tqdm(
        range(prediction_length),
        enabled=show_progress,
        desc=progress_desc or "Chronos decoding",
        total=prediction_length,
        leave=progress_leave,
    )
    for step in step_iter:
        if step < len(forced_prefix):
            next_token = torch.full(
                (num_samples,),
                int(forced_prefix[step]),
                device=device,
                dtype=torch.long,
            )
        else:
            logits = _next_token_logits(model, input_ids, attention_mask, decoder_input_ids)
            next_token = _sample_from_logits(
                logits,
                chronos_config=chronos_config,
                temperature=temperature,
                top_k=top_k,
                do_sample=do_sample,
                generator=generator,
            )

        generated.append(next_token)
        decoder_input_ids = torch.cat([decoder_input_ids, next_token[:, None]], dim=-1)

    return torch.stack(generated, dim=-1).detach().cpu()


@torch.no_grad()
def top_k_tokens_at_step(
    model,
    tokenizer,
    chronos_config,
    input_ids: torch.Tensor,
    attention_mask: torch.Tensor,
    prefix_tokens: Iterable[int],
    k: int = 5,
    sampling_temperature: Optional[float] = None,
    sampling_top_k: Optional[int] = None,
) -> List[TokenAlternative]:
    """Return top-k probable Chronos value-token alternatives after a prefix."""
    if k <= 0:
        raise ValueError("k must be positive.")

    device = next(model.parameters()).device
    input_ids = input_ids.to(device)
    attention_mask = attention_mask.to(device)

    start_id = _decoder_start_token_id(model, chronos_config)
    prefix = [start_id] + [int(t) for t in prefix_tokens]
    decoder_input_ids = torch.tensor(prefix, dtype=torch.long, device=device).unsqueeze(0)

    logits = _next_token_logits(model, input_ids, attention_mask, decoder_input_ids)
    logits = _mask_to_chronos_value_tokens(logits, chronos_config)
    probs = torch.softmax(logits, dim=-1)[0]
    sampling_probs = (
        torch.softmax(_sampling_logits(logits, sampling_temperature, sampling_top_k), dim=-1)[0]
        if sampling_temperature is not None else None
    )
    valid_ids = torch.where(torch.isfinite(logits[0]))[0]
    if not len(valid_ids):
        raise ValueError("No valid forecast token logits")
    values, indices = torch.topk(probs[valid_ids], k=min(k, len(valid_ids)))
    ids = valid_ids[indices]
    topology = _distribution_topology(probs, top_k_mass_k=k)

    out = []
    for rank, (prob, token_id) in enumerate(zip(values, ids), start=1):
        tid = int(token_id.detach().cpu())
        prob_value = float(prob.detach().cpu())
        out.append(
            TokenAlternative(
                rank=rank,
                token_id=tid,
                probability=prob_value,
                value=tokenizer.token_to_value(tid, scale=1.0),
                is_base_token=False,
                top1_probability=topology["top1_probability"],
                top2_probability=topology["top2_probability"],
                top1_top2_margin=topology["top1_top2_margin"],
                token_entropy=topology["token_entropy"],
                normalized_token_entropy=topology["normalized_token_entropy"],
                top_k_probability_mass=topology["top_k_probability_mass"],
                token_surprisal=float(-math.log(max(prob_value, 1e-45))),
                sampling_probability=float(sampling_probs[tid].cpu()) if sampling_probs is not None else float("nan"),
            )
        )
    return out


def _copy_topology_to_alternative(
    alt: TokenAlternative,
    source: Optional[TokenAlternative],
) -> TokenAlternative:
    if source is None:
        return alt
    alt.top1_probability = source.top1_probability
    alt.top2_probability = source.top2_probability
    alt.top1_top2_margin = source.top1_top2_margin
    alt.token_entropy = source.token_entropy
    alt.normalized_token_entropy = source.normalized_token_entropy
    alt.top_k_probability_mass = source.top_k_probability_mass
    return alt


def decode_token_samples_to_values(tokenizer, token_samples: torch.Tensor, scale: torch.Tensor) -> torch.Tensor:
    """Decode token samples [S, H] into values [S, H]."""
    samples = token_samples.unsqueeze(0).long()
    values = tokenizer.output_transform(samples, scale.cpu()).squeeze(0)
    return values.detach().cpu()


def _quantiles_from_samples(
    samples: torch.Tensor,
    levels=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9),
) -> torch.Tensor:
    """samples [S, H] -> quantiles [H, Q]."""
    q = torch.quantile(samples, q=torch.tensor(levels, dtype=samples.dtype), dim=0)
    return q.permute(1, 0).contiguous()


def _pick_ranked_alternative(alternatives: List[TokenAlternative], rank: int) -> TokenAlternative:
    if rank <= 0:
        raise ValueError("rank must be positive.")
    if not alternatives:
        raise ValueError("Cannot pick from an empty alternative list.")
    if rank > len(alternatives):
        raise ValueError("Requested rank exceeds the available value-token alternatives")
    return alternatives[rank - 1]


@torch.no_grad()
def decode_with_token_bundle_intervention(
    model,
    tokenizer,
    chronos_config,
    context: torch.Tensor,
    prediction_length: int,
    branch_step: int,
    initial_top_k: int = 5,
    bundle_size: int = 3,
    continuation_ranks: Iterable[int] = (1, 5, 10),
    num_samples: int = 30,
    temperature: float = 1.0,
    sample_top_k: Optional[int] = None,
    include_base_branch: bool = True,
    show_progress: bool = True,
) -> Dict:
    """Chronos FPA where a short forced-token bundle starts at branch_step.

    The first token in the bundle is enumerated over the top-k alternatives.
    Later bundle tokens are selected deterministically by rank under the model
    distribution conditioned on the forced prefix built so far.
    """
    if branch_step < 0 or branch_step >= prediction_length:
        raise ValueError("branch_step must be in [0, prediction_length - 1].")
    if bundle_size <= 0:
        raise ValueError("bundle_size must be positive.")
    if branch_step + bundle_size > prediction_length:
        raise ValueError("branch_step + bundle_size cannot exceed prediction_length.")
    if initial_top_k <= 0:
        raise ValueError("initial_top_k must be positive.")
    if num_samples <= 0:
        raise ValueError("num_samples must be positive.")

    continuation_ranks = [int(rank) for rank in continuation_ranks]
    if any(rank <= 0 for rank in continuation_ranks):
        raise ValueError("continuation_ranks must contain positive integers.")

    token_ids, attention_mask, scale = tokenizer.context_input_transform(context.cpu())
    device = next(model.parameters()).device
    token_ids = token_ids.to(device)
    attention_mask = attention_mask.to(device)

    base_tokens = decode_tokens_manual(
        model=model,
        chronos_config=chronos_config,
        input_ids=token_ids,
        attention_mask=attention_mask,
        prediction_length=prediction_length,
        num_samples=1,
        forced_prefix_tokens=None,
        temperature=temperature,
        top_k=sample_top_k,
        do_sample=False,
        show_progress=show_progress,
        progress_desc="Chronos base greedy",
        progress_leave=False,
    )[0]

    prefix_before_branch = base_tokens[:branch_step].tolist()
    base_token_at_branch = int(base_tokens[branch_step])

    initial_alternatives = top_k_tokens_at_step(
        model=model,
        tokenizer=tokenizer,
        chronos_config=chronos_config,
        input_ids=token_ids,
        attention_mask=attention_mask,
        prefix_tokens=prefix_before_branch,
        k=initial_top_k,
    )
    for alt in initial_alternatives:
        alt.is_base_token = alt.token_id == base_token_at_branch

    base_alt = next(
        (alt for alt in initial_alternatives if alt.token_id == base_token_at_branch),
        None,
    )
    if base_alt is None:
        base_alt = TokenAlternative(
            rank=0,
            token_id=base_token_at_branch,
            probability=float("nan"),
            value=tokenizer.token_to_value(base_token_at_branch, scale=1.0),
            is_base_token=True,
        )
        base_alt = _copy_topology_to_alternative(
            base_alt,
            initial_alternatives[0] if initial_alternatives else None,
        )

    def build_forced_branch(
        initial_alt: TokenAlternative,
        continuation_rank: int,
        branch_id: str,
        is_base_branch: bool = False,
    ) -> ForcedBranch:
        forced_tokens = prefix_before_branch + [int(initial_alt.token_id)]
        for _ in range(1, bundle_size):
            alternatives = top_k_tokens_at_step(
                model=model,
                tokenizer=tokenizer,
                chronos_config=chronos_config,
                input_ids=token_ids,
                attention_mask=attention_mask,
                prefix_tokens=forced_tokens,
                k=continuation_rank,
            )
            forced_tokens.append(int(_pick_ranked_alternative(alternatives, continuation_rank).token_id))

        bundle_tokens = forced_tokens[branch_step : branch_step + bundle_size]
        return ForcedBranch(
            branch_id=branch_id,
            branch_kind="bundle",
            branch_step=branch_step,
            forced_tokens=bundle_tokens,
            initial_token_id=int(initial_alt.token_id),
            initial_token_rank=int(initial_alt.rank),
            initial_token_probability=float(initial_alt.probability),
            initial_token_value=float(initial_alt.value),
            continuation_rank=int(continuation_rank),
            is_base_branch=is_base_branch,
            top1_probability=float(initial_alt.top1_probability),
            top2_probability=float(initial_alt.top2_probability),
            top1_top2_margin=float(initial_alt.top1_top2_margin),
            token_entropy=float(initial_alt.token_entropy),
            normalized_token_entropy=float(initial_alt.normalized_token_entropy),
            top_k_probability_mass=float(initial_alt.top_k_probability_mass),
            initial_token_surprisal=float(initial_alt.token_surprisal),
        )

    branch_specs: List[ForcedBranch] = []
    base_branch_id = None
    if include_base_branch:
        base_branch_id = "base_initial_top1"
        branch_specs.append(
            build_forced_branch(
                base_alt,
                continuation_rank=1,
                branch_id=base_branch_id,
                is_base_branch=True,
            )
        )

    for initial_alt in initial_alternatives:
        for continuation_rank in continuation_ranks:
            if (
                include_base_branch
                and int(initial_alt.token_id) == base_token_at_branch
                and int(continuation_rank) == 1
            ):
                continue
            branch_id = (
                f"token_{int(initial_alt.token_id)}_rank{int(initial_alt.rank)}"
                f"_cont_top{int(continuation_rank)}"
            )
            branch_specs.append(
                build_forced_branch(
                    initial_alt,
                    continuation_rank=continuation_rank,
                    branch_id=branch_id,
                    is_base_branch=False,
                )
            )

    branch_outputs = {}
    branch_iter = _maybe_tqdm(
        branch_specs,
        enabled=show_progress,
        desc="Chronos forced token bundles",
        total=len(branch_specs),
        leave=True,
    )
    for spec in branch_iter:
        forced_prefix = prefix_before_branch + spec.forced_tokens
        sample_tokens = decode_tokens_manual(
            model=model,
            chronos_config=chronos_config,
            input_ids=token_ids,
            attention_mask=attention_mask,
            prediction_length=prediction_length,
            num_samples=num_samples,
            forced_prefix_tokens=forced_prefix,
            temperature=temperature,
            top_k=sample_top_k,
            do_sample=True,
            show_progress=show_progress,
            progress_desc=f"{spec.branch_id} continuation",
            progress_leave=False,
        )
        sample_values = decode_token_samples_to_values(tokenizer, sample_tokens, scale)
        q_values = _quantiles_from_samples(sample_values)
        branch_outputs[spec.branch_id] = {
            "branch": spec,
            "sample_tokens": sample_tokens,
            "sample_values": sample_values,
            "quantiles": q_values,
            "median": q_values[:, 4],
        }

    base_values = decode_token_samples_to_values(tokenizer, base_tokens.unsqueeze(0), scale)[0]

    return {
        "base_tokens": base_tokens,
        "base_values": base_values,
        "base_token_at_branch": base_token_at_branch,
        "branch_step": branch_step,
        "bundle_size": bundle_size,
        "initial_alternatives": initial_alternatives,
        "branches": branch_outputs,
        "base_branch_id": base_branch_id,
        "tokenizer_scale": scale.detach().cpu(),
        "context_token_ids": token_ids.detach().cpu(),
        "context_attention_mask": attention_mask.detach().cpu(),
        "metadata": {
            "model_type": "chronos-t5-token-bin",
            "branch_kind": "bundle",
            "prediction_length": prediction_length,
            "branch_step": branch_step,
            "bundle_size": bundle_size,
            "initial_top_k": initial_top_k,
            "continuation_ranks": continuation_ranks,
            "num_samples": num_samples,
            "temperature": temperature,
            "sample_top_k": sample_top_k,
        },
    }


@torch.no_grad()
def decode_with_token_bin_intervention(
    model,
    tokenizer,
    chronos_config,
    context: torch.Tensor,
    prediction_length: int,
    branch_step: int,
    top_k: int = 5,
    num_samples: int = 30,
    temperature: float = 1.0,
    sample_top_k: Optional[int] = None,
    include_base_token_branch: bool = True,
    show_progress: bool = True,
    sampling_seed: Optional[int] = None,
    rng_namespace: str = "",
) -> Dict:
    """Chronos v1 FPA with forced token-bin intervention.

    Procedure
    ---------
    1. Tokenize the context.
    2. Decode one greedy base future token path.
    3. At `branch_step`, get top-k likely next token bins conditional on the
       greedy prefix.
    4. For each selected token bin, force that token and sample the continuation.
    5. Decode token samples back to real-valued trajectories and return both
       token-level and value-level outputs.

    `branch_step` is zero-based over the forecast horizon: 0 means the first
    generated future value.
    """
    if branch_step < 0 or branch_step >= prediction_length:
        raise ValueError("branch_step must be in [0, prediction_length - 1].")
    if num_samples <= 0:
        raise ValueError("num_samples must be positive.")

    token_ids, attention_mask, scale = tokenizer.context_input_transform(context.cpu())
    device = next(model.parameters()).device
    token_ids = token_ids.to(device)
    attention_mask = attention_mask.to(device)

    base_tokens = decode_tokens_manual(
        model=model,
        chronos_config=chronos_config,
        input_ids=token_ids,
        attention_mask=attention_mask,
        prediction_length=prediction_length,
        num_samples=1,
        forced_prefix_tokens=None,
        temperature=temperature,
        top_k=sample_top_k,
        do_sample=False,
        show_progress=show_progress,
        progress_desc="Chronos base greedy",
        progress_leave=False,
    )[0]

    prefix_before_branch = base_tokens[:branch_step].tolist()
    base_token_at_branch = int(base_tokens[branch_step])

    alternatives = top_k_tokens_at_step(
        model=model,
        tokenizer=tokenizer,
        chronos_config=chronos_config,
        input_ids=token_ids,
        attention_mask=attention_mask,
        prefix_tokens=prefix_before_branch,
        k=top_k,
        sampling_temperature=temperature if sampling_seed is not None else None,
        sampling_top_k=sample_top_k,
    )
    for alt in alternatives:
        alt.is_base_token = alt.token_id == base_token_at_branch

    if include_base_token_branch and all(a.token_id != base_token_at_branch for a in alternatives):
        alternatives.insert(
            0,
            TokenAlternative(
                rank=0,
                token_id=base_token_at_branch,
                probability=float("nan"),
                value=tokenizer.token_to_value(base_token_at_branch, scale=1.0),
                is_base_token=True,
            ),
        )
        alternatives[0] = _copy_topology_to_alternative(
            alternatives[0],
            alternatives[1] if len(alternatives) > 1 else None,
        )
        if sampling_seed is not None:
            # A top-k tie can omit argmax's reference ID. Recover its actual
            # probabilities for the new manifest without changing legacy ranks.
            reference_alt = next(a for a in top_k_tokens_at_step(
                model, tokenizer, chronos_config, token_ids, attention_mask,
                prefix_before_branch, k=chronos_config.n_tokens,
                sampling_temperature=temperature, sampling_top_k=sample_top_k,
            ) if a.token_id == base_token_at_branch)
            alternatives[0].probability = reference_alt.probability
            alternatives[0].token_surprisal = reference_alt.token_surprisal
            alternatives[0].sampling_probability = reference_alt.sampling_probability

    if not include_base_token_branch:
        alternatives = [a for a in alternatives if a.token_id != base_token_at_branch]

    branch_outputs = {}
    alt_iter = _maybe_tqdm(
        alternatives,
        enabled=show_progress,
        desc="Chronos forced token branches",
        total=len(alternatives),
        leave=True,
    )
    for alt in alt_iter:
        forced_prefix = prefix_before_branch + [alt.token_id]
        generator, rng = (None, None) if sampling_seed is None else _ensemble_generator(
            model, sampling_seed, rng_namespace, f"b={branch_step}/token={alt.token_id}"
        )
        sample_tokens = decode_tokens_manual(
            model=model,
            chronos_config=chronos_config,
            input_ids=token_ids,
            attention_mask=attention_mask,
            prediction_length=prediction_length,
            num_samples=num_samples,
            forced_prefix_tokens=forced_prefix,
            temperature=temperature,
            top_k=sample_top_k,
            do_sample=True,
            show_progress=show_progress,
            progress_desc=f"token {alt.token_id} continuation",
            progress_leave=False,
            generator=generator,
        )
        sample_values = decode_token_samples_to_values(tokenizer, sample_tokens, scale)
        q_values = _quantiles_from_samples(sample_values)
        branch_outputs[alt.token_id] = {
            "alternative": alt,
            "sample_tokens": sample_tokens,
            "sample_values": sample_values,
            "quantiles": q_values,
            "median": q_values[:, 4],
        }
        if rng is not None:
            branch_outputs[alt.token_id]["rng"] = rng

    same_token_null = None
    if sampling_seed is not None:
        if not include_base_token_branch:
            raise ValueError("Independent same-token controls require the forced base branch")
        generator, rng = _ensemble_generator(model, sampling_seed, rng_namespace, f"b={branch_step}/same-token-null")
        null_tokens = decode_tokens_manual(
            model, chronos_config, token_ids, attention_mask, prediction_length,
            num_samples=num_samples, forced_prefix_tokens=prefix_before_branch + [base_token_at_branch],
            temperature=temperature, top_k=sample_top_k, do_sample=True,
            show_progress=show_progress, progress_desc="Chronos independent same-token control",
            generator=generator,
        )
        same_token_null = {"sample_values": decode_token_samples_to_values(tokenizer, null_tokens, scale), "rng": rng}

    base_values = decode_token_samples_to_values(tokenizer, base_tokens.unsqueeze(0), scale)[0]

    output = {
        "base_tokens": base_tokens,
        "base_values": base_values,
        "base_token_at_branch": base_token_at_branch,
        "branch_step": branch_step,
        "alternatives": alternatives,
        "branches": branch_outputs,
        "tokenizer_scale": scale.detach().cpu(),
        "context_token_ids": token_ids.detach().cpu(),
        "context_attention_mask": attention_mask.detach().cpu(),
        "metadata": {
            "model_type": "chronos-t5-token-bin",
            "prediction_length": prediction_length,
            "branch_step": branch_step,
            "top_k": top_k,
            "num_samples": num_samples,
            "temperature": temperature,
            "sample_top_k": sample_top_k,
        },
    }
    if same_token_null is not None:
        output["same_token_null"] = same_token_null
    return output

