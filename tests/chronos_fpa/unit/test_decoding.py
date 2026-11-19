"""Decoder control flow with fixed logits, no pretrained weights or Transformers."""

import math
from types import SimpleNamespace

import pytest
import torch

from chronos_decoding import (
    _mask_to_chronos_value_tokens,
    _pick_ranked_alternative,
    decode_tokens_manual,
    decode_with_token_bundle_intervention,
    decode_with_token_bin_intervention,
    top_k_tokens_at_step,
)


class FixedLogitModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(()))
        self.config = SimpleNamespace(decoder_start_token_id=0)
        self.prefixes = []

    def forward(self, input_ids, attention_mask, decoder_input_ids, use_cache=False):
        self.prefixes.append(decoder_input_ids.detach().clone())
        # Specials dominate unless masked; legal value probabilities are .6, .3, .1.
        logits = torch.tensor([100.0, 99.0, 98.0, math.log(6), math.log(3), 0.0])
        batch, length = decoder_input_ids.shape
        return SimpleNamespace(logits=logits.expand(batch, length, -1))


class ToyTokenizer:
    def token_to_value(self, token_id, scale=1.0):
        return (token_id - 3) * float(scale)

    def context_input_transform(self, context):
        tokens = torch.tensor([[3, 4]])
        return tokens, torch.ones_like(tokens, dtype=torch.bool), torch.tensor([2.0])

    def output_transform(self, samples, scale):
        return (samples.float() - 3) * scale[:, None, None]


@pytest.fixture
def config():
    return SimpleNamespace(n_special_tokens=3, n_tokens=6, pad_token_id=0, eos_token_id=1)


def inputs():
    return dict(input_ids=torch.tensor([[3, 4]]), attention_mask=torch.tensor([[True, True]]))


def test_value_mask_forbids_specials_pad_and_eos_without_mutating_logits():
    # Pad and EOS deliberately live outside the contiguous special-token range.
    config = SimpleNamespace(n_special_tokens=2, pad_token_id=4, eos_token_id=5)
    logits = torch.tensor([[10.0, 11.0, 12.0, 13.0, 14.0, 15.0]])
    original = logits.clone()
    masked = _mask_to_chronos_value_tokens(logits, config)
    assert torch.isneginf(masked[0, [0, 1, 4, 5]]).all()
    torch.testing.assert_close(masked[0, [2, 3]], torch.tensor([12.0, 13.0]))
    torch.testing.assert_close(logits, original)


def test_manual_decode_keeps_forced_prefix_for_every_sample(config):
    model = FixedLogitModel()
    output = decode_tokens_manual(
        model, config, **inputs(), prediction_length=4, num_samples=3,
        forced_prefix_tokens=[5, 4], do_sample=False, show_progress=False,
    )
    torch.testing.assert_close(output, torch.tensor([[5, 4, 3, 3]]).repeat(3, 1))
    assert output.device.type == "cpu"
    assert len(model.prefixes) == 2
    torch.testing.assert_close(model.prefixes[0], torch.tensor([[0, 5, 4]]).repeat(3, 1))
    torch.testing.assert_close(model.prefixes[1], torch.tensor([[0, 5, 4, 3]]).repeat(3, 1))


def test_entirely_forced_forecast_never_calls_model(config):
    model = FixedLogitModel()
    output = decode_tokens_manual(
        model, config, **inputs(), prediction_length=3, num_samples=2,
        forced_prefix_tokens=[5, 4, 3], show_progress=False,
    )
    torch.testing.assert_close(output, torch.tensor([[5, 4, 3], [5, 4, 3]]))
    assert model.prefixes == []


@pytest.mark.parametrize("invalid_token", [-1, 0, 1, 2, 6, 100])
def test_forced_prefix_rejects_special_and_out_of_vocabulary_tokens(config, invalid_token):
    model = FixedLogitModel()
    with pytest.raises(ValueError, match="value tokens"):
        decode_tokens_manual(
            model, config, **inputs(), prediction_length=2,
            forced_prefix_tokens=[invalid_token], show_progress=False,
        )
    assert model.prefixes == []


@pytest.mark.parametrize("num_samples", [0, -1])
def test_manual_decode_rejects_nonpositive_sample_count(config, num_samples):
    with pytest.raises(ValueError, match="num_samples"):
        decode_tokens_manual(
            FixedLogitModel(), config, **inputs(), prediction_length=2,
            num_samples=num_samples, show_progress=False,
        )


def test_manual_decode_rejects_prefix_longer_than_horizon(config):
    with pytest.raises(ValueError, match="longer"):
        decode_tokens_manual(
            FixedLogitModel(), config, **inputs(), prediction_length=1,
            forced_prefix_tokens=[3, 4], show_progress=False,
        )


@pytest.mark.parametrize("k,token_ids,probabilities,mass", [
    (2, [3, 4], [0.6, 0.3], 0.9),
    (5, [3, 4, 5], [0.6, 0.3, 0.1], 1.0),
    (15, [3, 4, 5], [0.6, 0.3, 0.1], 1.0),
])
def test_topk_returns_only_legal_support_and_original_probabilities(config, k, token_ids, probabilities, mass):
    model = FixedLogitModel()
    alternatives = top_k_tokens_at_step(
        model, ToyTokenizer(), config, **inputs(), prefix_tokens=[5], k=k,
    )
    assert [alt.token_id for alt in alternatives] == token_ids
    assert [alt.rank for alt in alternatives] == list(range(1, len(token_ids) + 1))
    assert [alt.probability for alt in alternatives] == pytest.approx(probabilities)
    assert [alt.value for alt in alternatives] == [token_id - 3 for token_id in token_ids]
    entropy = -(0.6 * math.log(0.6) + 0.3 * math.log(0.3) + 0.1 * math.log(0.1))
    for alt in alternatives:
        assert alt.token_surprisal == pytest.approx(-math.log(alt.probability))
        assert alt.top1_probability == pytest.approx(0.6)
        assert alt.top2_probability == pytest.approx(0.3)
        assert alt.top1_top2_margin == pytest.approx(0.3)
        assert alt.token_entropy == pytest.approx(entropy)
        assert alt.normalized_token_entropy == pytest.approx(entropy / math.log(3))
        assert alt.top_k_probability_mass == pytest.approx(mass)
    torch.testing.assert_close(model.prefixes[0], torch.tensor([[0, 5]]))


@pytest.mark.parametrize("rank", [0, -1, 4, 15])
def test_rank_selection_rejects_outside_available_support(config, rank):
    alternatives = top_k_tokens_at_step(
        FixedLogitModel(), ToyTokenizer(), config, **inputs(), prefix_tokens=[], k=15,
    )
    with pytest.raises(ValueError, match="rank"):
        _pick_ranked_alternative(alternatives, rank)


def test_rank_selection_keeps_one_based_rank_and_rejects_empty(config):
    alternatives = top_k_tokens_at_step(
        FixedLogitModel(), ToyTokenizer(), config, **inputs(), prefix_tokens=[], k=3,
    )
    assert _pick_ranked_alternative(alternatives, 1).token_id == 3
    assert _pick_ranked_alternative(alternatives, 3).token_id == 5
    with pytest.raises(ValueError, match="empty"):
        _pick_ranked_alternative([], 1)


def test_bundle_base_mapping_and_forced_prefixes(config):
    # Force the entire remaining horizon so this test does not depend on RNG.
    result = decode_with_token_bundle_intervention(
        FixedLogitModel(), ToyTokenizer(), config, context=torch.tensor([[1.0, 2.0]]),
        prediction_length=3, branch_step=1, initial_top_k=2, bundle_size=2,
        continuation_ranks=[1, 2], num_samples=2, show_progress=False,
    )
    assert result["base_token_at_branch"] == 3
    base_id = result["base_branch_id"]
    assert base_id in result["branches"]
    specs = [entry["branch"] for entry in result["branches"].values()]
    assert len(specs) == 4
    assert sum(spec.is_base_branch for spec in specs) == 1
    base = result["branches"][base_id]
    assert base["branch"].is_base_branch
    assert base["branch"].initial_token_id == 3
    assert base["branch"].continuation_rank == 1
    expected = {
        (3, 1): [3, 3, 3], (3, 2): [3, 3, 4],
        (4, 1): [3, 4, 3], (4, 2): [3, 4, 4],
    }
    for entry in result["branches"].values():
        spec = entry["branch"]
        prefix = expected[(spec.initial_token_id, spec.continuation_rank)]
        assert spec.forced_tokens == prefix[1:]
        torch.testing.assert_close(entry["sample_tokens"], torch.tensor([prefix, prefix]))
        assert entry["quantiles"].shape == (3, 9)
        assert entry["median"].tolist() == [(token - 3) * 2.0 for token in prefix]


def test_seeded_same_token_control_uses_independent_reproducible_streams(config):
    model = FixedLogitModel()
    arguments = dict(model=model, tokenizer=ToyTokenizer(), chronos_config=config,
                     context=torch.tensor([[1., 2.]]), prediction_length=5, branch_step=1,
                     top_k=2, num_samples=30, show_progress=False, sampling_seed=123,
                     rng_namespace='series=001/window=0')
    state = torch.get_rng_state().clone()
    first = decode_with_token_bin_intervention(**arguments)
    assert torch.equal(state, torch.get_rng_state())
    torch.manual_seed(999)
    second = decode_with_token_bin_intervention(**arguments)
    base = first['branches'][first['base_token_at_branch']]
    null = first['same_token_null']
    assert base['rng']['stream_id'] != null['rng']['stream_id']
    assert base['rng']['seed'] != null['rng']['seed']
    assert not torch.equal(base['sample_values'][:, 2:], null['sample_values'][:, 2:])
    torch.testing.assert_close(base['sample_values'], second['branches'][first['base_token_at_branch']]['sample_values'])
    torch.testing.assert_close(null['sample_values'], second['same_token_null']['sample_values'])
    for entry in first['branches'].values():
        torch.testing.assert_close(entry['sample_tokens'][:, :1], first['base_tokens'][:1].expand(30, 1))
    # The new control cannot become a self-comparison by aliasing the base tensor.
    assert base['sample_values'].data_ptr() != null['sample_values'].data_ptr()


def test_selection_and_sampling_probabilities_are_separately_reported(config):
    alternatives = top_k_tokens_at_step(
        FixedLogitModel(), ToyTokenizer(), config, **inputs(), prefix_tokens=[], k=3,
        sampling_temperature=1., sampling_top_k=2,
    )
    assert [a.probability for a in alternatives] == pytest.approx([.6, .3, .1])
    assert [a.sampling_probability for a in alternatives] == pytest.approx([2/3, 1/3, 0.])


def test_manually_included_base_has_real_probabilities_in_new_mode(config, monkeypatch):
    import chronos_decoding
    original = chronos_decoding.top_k_tokens_at_step
    def omit_base(*args, **kwargs):
        if kwargs['k'] == 1:
            return original(*args, **{**kwargs, 'k': 2})[1:]
        return original(*args, **kwargs)
    monkeypatch.setattr(chronos_decoding, 'top_k_tokens_at_step', omit_base)
    result = decode_with_token_bin_intervention(
        FixedLogitModel(), ToyTokenizer(), config, context=torch.tensor([[1., 2.]]),
        prediction_length=2, branch_step=0, top_k=1, num_samples=2,
        sample_top_k=2, sampling_seed=9, show_progress=False,
    )
    base = result['branches'][result['base_token_at_branch']]['alternative']
    assert base.rank == 0
    assert base.probability == pytest.approx(.6)
    assert base.sampling_probability == pytest.approx(2/3)
