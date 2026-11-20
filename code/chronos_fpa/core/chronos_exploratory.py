"""Opt-in q50 microbenchmark primitives; legacy scan decoding is unchanged."""
from __future__ import annotations

import copy
from dataclasses import dataclass
import time

import torch

from chronos_decoding import _decoder_start_token_id, _mask_to_chronos_value_tokens, _sampling_logits


POLICY_VERSION = "q50_mass90_cap8_greedy_first_v1"


def policy_probabilities(logits, config):
    masked = _mask_to_chronos_value_tokens(logits, config)
    if not torch.isfinite(masked).any(dim=-1).all():
        raise ValueError("No finite valid-token support")
    return torch.softmax(_sampling_logits(masked, 1.0, 50), dim=-1)


@dataclass(frozen=True)
class Candidates:
    token_ids: tuple[int, ...]
    weights: tuple[float, ...]
    residual_ids: tuple[int, ...]
    residual_mass: float
    selected_mass: float
    target_attained: bool


def select_candidates(probabilities, greedy_token, target_mass=.9, max_tokens=8):
    """Greedy first, then decreasing q50 with ascending ID for equal weights."""
    q = torch.as_tensor(probabilities, dtype=torch.float64).detach().cpu().reshape(-1)
    if not torch.isfinite(q).all() or (q < 0).any() or q.sum() <= 0:
        raise ValueError("Expected a finite nonnegative probability vector")
    if not 0 < target_mass <= 1 or not 1 <= max_tokens <= 8:
        raise ValueError("Invalid target or eight-token cap")
    q = q / q.sum()
    greedy_token = int(greedy_token)
    if not 0 <= greedy_token < len(q) or q[greedy_token] <= 0:
        raise ValueError("Greedy token must belong to q50 support")
    ordered = [greedy_token] + [int(i) for i in torch.argsort(q, descending=True, stable=True)
                               if int(i) != greedy_token and q[i] > 0]
    selected = []
    for token in ordered:
        selected.append(token)
        if float(q[selected].sum()) >= target_mass or len(selected) == max_tokens:
            break
    residual = tuple(i for i in range(len(q)) if q[i] > 0 and i not in selected)
    selected_mass = float(q[selected].sum())
    return Candidates(tuple(selected), tuple(float(q[t]) for t in selected), residual,
                      float(q[list(residual)].sum()) if residual else 0., selected_mass,
                      selected_mass >= target_mass)


@dataclass
class PrefixState:
    tokens: tuple[int, ...]
    logits: torch.Tensor
    cache: object


def fork_cache(cache, batch_count=1):
    """Copy mutable self-KV; share initialized cross-KV only for a single row."""
    fork = copy.copy(cache)
    fork.is_updated = dict(cache.is_updated)
    fork.self_attention_cache = copy.deepcopy(cache.self_attention_cache)
    if batch_count == 1 and cache.is_updated and all(cache.is_updated.values()):
        # T5 skips cross-cache updates for these initialized layers. Never batch
        # or mutate this shared object; repeated batches receive their own copy.
        fork.cross_attention_cache = cache.cross_attention_cache
    else:
        fork.cross_attention_cache = copy.deepcopy(cache.cross_attention_cache)
    if batch_count > 1:
        fork.batch_repeat_interleave(batch_count)
    return fork


class CachedDecoder:
    """One encoder per context; private cache copies for every branched batch."""

    @torch.no_grad()
    def __init__(self, model, config, input_ids, attention_mask):
        if model.training:
            raise ValueError("Cached decoding requires eval mode")
        if input_ids.shape[0] != 1:
            raise ValueError("Exactly one context is required")
        self.model, self.config = model, config
        self.device = next(model.parameters()).device
        self.input_ids, self.attention_mask = input_ids.to(self.device), attention_mask.to(self.device)
        started = time.perf_counter()
        self.encoder = model.get_encoder()(input_ids=self.input_ids, attention_mask=self.attention_mask,
                                           use_cache=False, return_dict=True)
        self.encoder_seconds = time.perf_counter() - started
        self.encoder_calls, self.decoder_calls = 1, 0
        self.states = {}
        self.start_id = _decoder_start_token_id(model, config)

    def _encoder_batch(self, count):
        from transformers.modeling_outputs import BaseModelOutput
        return BaseModelOutput(last_hidden_state=self.encoder.last_hidden_state.expand(count, -1, -1))

    @torch.no_grad()
    def prefix_state(self, prefix=()):
        prefix = tuple(int(t) for t in prefix)
        if prefix in self.states:
            return self.states[prefix]
        if any(t < self.config.n_special_tokens or t >= self.config.n_tokens
               or t in {self.config.pad_token_id, self.config.eos_token_id} for t in prefix):
            raise ValueError("Prefix contains a non-value token")
        if prefix:
            parent = self.prefix_state(prefix[:-1])
            cache = fork_cache(parent.cache)
            decoder_ids = torch.tensor([[prefix[-1]]], device=self.device)
        else:
            cache, decoder_ids = None, torch.tensor([[self.start_id]], device=self.device)
        out = self.model(encoder_outputs=self.encoder, attention_mask=self.attention_mask,
                         decoder_input_ids=decoder_ids, past_key_values=cache,
                         use_cache=True, return_dict=True)
        self.decoder_calls += 1
        state = PrefixState(prefix, out.logits[:, -1].detach(), out.past_key_values)
        self.states[prefix] = state
        return state

    @torch.no_grad()
    def greedy(self, horizon):
        if horizon <= 0:
            raise ValueError("Horizon must be positive")
        tokens = []
        for _ in range(horizon):
            logits = self.prefix_state(tokens).logits
            tokens.append(int(_mask_to_chronos_value_tokens(logits, self.config).argmax(-1)))
        return torch.tensor(tokens, dtype=torch.long)

    @torch.no_grad()
    def sample(self, prefix, horizon, count, generator, batch_size=None):
        prefix = tuple(int(t) for t in prefix)
        if horizon <= 0 or len(prefix) > horizon or count <= 0:
            raise ValueError("Invalid horizon/prefix/sample count")
        batch_size = count if batch_size is None else int(batch_size)
        if batch_size <= 0:
            raise ValueError("Batch size must be positive")
        state = self.prefix_state(prefix)
        batches = []
        for begin in range(0, count, batch_size):
            n = min(batch_size, count - begin)
            cache = fork_cache(state.cache, n)
            logits = state.logits.expand(n, -1)
            paths = torch.tensor(prefix, dtype=torch.long, device=self.device).repeat(n, 1)
            for step in range(len(prefix), horizon):
                q = policy_probabilities(logits, self.config)
                token = torch.multinomial(q, 1, generator=generator)
                paths = torch.cat((paths, token), dim=1)
                if step + 1 < horizon:
                    out = self.model(encoder_outputs=self._encoder_batch(n),
                                     attention_mask=self.attention_mask.expand(n, -1),
                                     decoder_input_ids=token, past_key_values=cache,
                                     use_cache=True, return_dict=True)
                    cache, logits = out.past_key_values, out.logits[:, -1]
                    self.decoder_calls += 1
            batches.append(paths.cpu())
        return torch.cat(batches)

    @torch.no_grad()
    def sample_residual(self, prefix, probabilities, candidates, horizon, count, generator):
        if not candidates.residual_ids or candidates.residual_mass <= 0:
            raise ValueError("Residual support is empty")
        q = torch.as_tensor(probabilities, device=self.device).clone().reshape(-1)
        mask = torch.zeros_like(q, dtype=torch.bool)
        mask[list(candidates.residual_ids)] = True
        conditional = torch.where(mask, q, 0.)
        conditional /= conditional.sum()
        first = torch.multinomial(conditional, count, replacement=True, generator=generator)
        result = torch.empty(count, horizon, dtype=torch.long)
        # Grouping preserves the conditional law; RNG ordering is part of this version.
        for token in torch.unique(first, sorted=True):
            rows = torch.where(first == token)[0].cpu()
            result[rows] = self.sample(tuple(prefix) + (int(token),), horizon, len(rows), generator)
        return result

    @torch.no_grad()
    def sample_encoder_only(self, prefix, horizon, count, generator):
        """Encoder reuse without KV, for matched decoder timing/parity checks."""
        if count <= 0 or horizon <= 0 or len(prefix) > horizon:
            raise ValueError("Invalid encoder-only sampling request")
        paths = torch.tensor(prefix, dtype=torch.long, device=self.device).repeat(count, 1)
        start = torch.full((count, 1), self.start_id, device=self.device, dtype=torch.long)
        for _ in range(len(prefix), horizon):
            out = self.model(encoder_outputs=self._encoder_batch(count),
                             attention_mask=self.attention_mask.expand(count, -1),
                             decoder_input_ids=torch.cat((start, paths), dim=1),
                             use_cache=False, return_dict=True)
            self.decoder_calls += 1
            token = torch.multinomial(policy_probabilities(out.logits[:, -1], self.config), 1, generator=generator)
            paths = torch.cat((paths, token), dim=1)
        return paths.cpu()

    @torch.no_grad()
    def replay(self, token_paths, capture=False):
        """Teacher forcing: column t predicts token t from start + tokens[:t]."""
        tokens = torch.as_tensor(token_paths, dtype=torch.long, device=self.device)
        if tokens.ndim != 2 or tokens.shape[1] == 0:
            raise ValueError("Replay requires complete [paths,horizon] tokens")
        start = torch.full((len(tokens), 1), self.start_id, device=self.device, dtype=torch.long)
        decoder = torch.cat((start, tokens[:, :-1]), dim=1)
        encoder = self.encoder
        arrays = {}
        if capture:
            encoder = self.model.get_encoder()(input_ids=self.input_ids, attention_mask=self.attention_mask,
                                               use_cache=False, output_hidden_states=True,
                                               output_attentions=True, return_dict=True)
            self.encoder_calls += 1
            if encoder.attentions is None or any(v is None for v in encoder.attentions):
                raise ValueError("Attention backend omitted encoder capture")
            for family, tensors in (("encoder_hidden", encoder.hidden_states),
                                    ("encoder_attention", encoder.attentions)):
                for layer, tensor in enumerate(tensors):
                    arrays[f"{family}_{layer}"] = tensor.detach().cpu().numpy()
        from transformers.modeling_outputs import BaseModelOutput
        expanded = BaseModelOutput(last_hidden_state=encoder.last_hidden_state.expand(len(tokens), -1, -1))
        out = self.model(encoder_outputs=expanded, attention_mask=self.attention_mask.expand(len(tokens), -1),
                         decoder_input_ids=decoder, use_cache=False, return_dict=True,
                         output_hidden_states=capture, output_attentions=capture)
        self.decoder_calls += 1
        if capture:
            for family, tensors in (("decoder_hidden", out.decoder_hidden_states),
                                    ("decoder_attention", out.decoder_attentions),
                                    ("cross_attention", out.cross_attentions)):
                if tensors is None or any(v is None for v in tensors):
                    raise ValueError(f"Attention backend omitted {family}")
                for layer, tensor in enumerate(tensors):
                    arrays[f"{family}_{layer}"] = tensor.detach().cpu().numpy()
        return out.logits.detach().cpu(), arrays
