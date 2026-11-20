import copy
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from chronos_decoding import decode_tokens_manual
from chronos_exploratory import CachedDecoder, policy_probabilities, select_candidates
from chronos_outcomes import compare_fixed22_and_full, weighted_events, window_outcomes


@pytest.fixture
def tiny_decoder():
    from transformers import T5Config, T5ForConditionalGeneration
    with torch.random.fork_rng():
        torch.manual_seed(317)
        model = T5ForConditionalGeneration(T5Config(
            vocab_size=16, d_model=16, d_ff=32, d_kv=8, num_heads=2,
            num_layers=2, num_decoder_layers=2, dropout_rate=0.,
            decoder_start_token_id=0, pad_token_id=0, eos_token_id=1,
            attn_implementation="eager",
        )).eval()
    config = SimpleNamespace(n_special_tokens=2, n_tokens=16, pad_token_id=0, eos_token_id=1)
    inputs = torch.tensor([[2, 5, 7, 3]])
    mask = torch.ones_like(inputs)
    return model, config, inputs, mask, CachedDecoder(model, config, inputs, mask)


def test_mass_selection_covers_target_caps_and_preserves_greedy_ties():
    candidates = select_candidates(torch.tensor([.6, .3, .1], dtype=torch.float64), 0)
    assert candidates.token_ids == (0, 1) and candidates.residual_ids == (2,)
    assert candidates.residual_mass == pytest.approx(.1)
    assert sum(candidates.weights) + candidates.residual_mass == pytest.approx(1.)
    tied = select_candidates(torch.ones(60), 59)
    assert tied.token_ids == (59, 0, 1, 2, 3, 4, 5, 6)
    assert not tied.target_attained and len(tied.residual_ids) == 52


def test_q50_retains_threshold_ties_and_masks_special_tokens():
    config = SimpleNamespace(n_special_tokens=2, pad_token_id=0, eos_token_id=1)
    q = policy_probabilities(torch.ones(1, 62), config)
    assert (q > 0).sum() == 60 and q[0, :2].sum() == 0
    assert q.sum() == pytest.approx(1.)


def test_cached_logits_greedy_and_full_prefix_conditioning_match_reference(tiny_decoder):
    model, config, ids, mask, engine = tiny_decoder
    greedy = engine.greedy(32)
    reference = decode_tokens_manual(model, config, ids, mask, 32, do_sample=False, show_progress=False)[0]
    torch.testing.assert_close(greedy, reference, rtol=0, atol=0)
    for prefix in ([], [3], greedy[:9].tolist(), greedy[:15].tolist()):
        state = engine.prefix_state(prefix)
        with torch.no_grad():
            expected = model(input_ids=ids, attention_mask=mask,
                             decoder_input_ids=torch.tensor([[0] + prefix]), use_cache=False).logits[:, -1]
        torch.testing.assert_close(state.logits, expected, rtol=1e-4, atol=1e-5)
        torch.testing.assert_close(policy_probabilities(state.logits, config), policy_probabilities(expected, config), rtol=1e-4, atol=1e-6)
    assert engine.encoder_calls == 1


def test_branched_cache_isolation_and_residual_first_token_support(tiny_decoder):
    _, config, _, _, engine = tiny_decoder
    state = engine.prefix_state([3, 5])
    before = copy.deepcopy(state.cache)
    paths = engine.sample([3, 5], 32, 20, torch.Generator().manual_seed(88), batch_size=4)
    torch.testing.assert_close(paths[:, :2], torch.tensor([[3, 5]]).repeat(20, 1))
    assert state.cache.get_seq_length() == before.get_seq_length() == 3
    for actual, saved in zip(state.cache.self_attention_cache.layers, before.self_attention_cache.layers):
        torch.testing.assert_close(actual.keys, saved.keys, rtol=0, atol=0)
    q = policy_probabilities(engine.prefix_state([3]).logits, config)[0]
    selected = select_candidates(q, int(q.argmax()), max_tokens=1)
    residual = engine.sample_residual([3], q, selected, 8, 20, torch.Generator().manual_seed(112))
    assert set(residual[:, 1].tolist()).issubset(set(selected.residual_ids))
    assert not set(residual[:, 1].tolist()).intersection(selected.token_ids)
    # Later steps use ordinary q50 and may return to the selected first-token set.
    assert torch.equal(residual[:, 0], torch.full((20,), 3))


def test_replay_captures_every_layer_head_and_keeps_token_alignment(tiny_decoder):
    _, _, _, _, engine = tiny_decoder
    tokens = engine.sample([3, 7], 8, 2, torch.Generator().manual_seed(17))
    plain, _ = engine.replay(tokens)
    captured, tensors = engine.replay(tokens, capture=True)
    torch.testing.assert_close(captured, plain, atol=1e-5, rtol=1e-4)
    assert len([k for k in tensors if k.startswith("encoder_hidden_")]) == 3
    assert len([k for k in tensors if k.startswith("decoder_hidden_")]) == 3
    assert tensors["encoder_attention_1"].shape == (1, 2, 4, 4)
    assert tensors["decoder_attention_1"].shape == (2, 2, 8, 8)
    assert tensors["cross_attention_1"].shape == (2, 2, 8, 4)
    # At t=2, logits condition on the two forced tokens, not on token t.
    torch.testing.assert_close(captured[:1, 2], engine.prefix_state([3, 7]).logits, atol=1e-5, rtol=1e-4)


def test_fixed22_and_full_have_distinct_support_and_signed_jump():
    context = np.array([0., 1., 2., 3.])
    reference = np.zeros((2, 32))
    alternative = reference.copy()
    alternative[:, 0] = -7
    alternative[:, 23:] = 2
    metrics, profile = compare_fixed22_and_full(reference, alternative, 0, context)
    assert metrics["signed_direct_token_jump"] == -7
    assert metrics["direct_token_jump"] == 7
    assert metrics["w1_fixed22"] == metrics["ed_fixed22"] == 0
    assert metrics["w1_post"] == pytest.approx(18 / 31)
    assert len(profile) == 31
    alternative[:, 0] = 0
    metrics, _ = compare_fixed22_and_full(reference, alternative, 9, context)
    assert metrics["w1_fixed22"] == metrics["w1_post"]


def test_greedy_conditioned_law_is_next_prefix_law_without_finite_sample_equality(tiny_decoder):
    _, config, _, _, engine = tiny_decoder
    greedy = engine.greedy(32)
    for t in (0, 9, 10, 14):
        forced_greedy = engine.prefix_state(greedy[:t].tolist() + [int(greedy[t])])
        next_prefix = engine.prefix_state(greedy[:t + 1].tolist())
        assert forced_greedy.tokens == next_prefix.tokens
        torch.testing.assert_close(policy_probabilities(forced_greedy.logits, config),
                                   policy_probabilities(next_prefix.logits, config), atol=0, rtol=0)


def test_fixed_outcome_reconstruction_and_weighted_mixture_known_answer():
    greedy = np.zeros(32)
    a, b = np.zeros((2, 32)), np.ones((4, 32))
    events_a, events_b = window_outcomes(a, greedy, 1)["events"], window_outcomes(b, greedy, 1)["events"]
    weighted = weighted_events([events_a, events_b], [.7, .3])
    np.testing.assert_allclose(weighted["event_probability"][:, :4], .3)
    np.testing.assert_allclose(weighted["event_probability"][:, 4], 0)
    # The last-eight outcome uses the full fixed coordinates 24..31.
    a[:, 31] = 8
    outcome = window_outcomes(a, greedy, 1)
    np.testing.assert_allclose(outcome["last8_mean_abs_delta_iqr"], 1.)
    with pytest.raises(ValueError, match="sum to one"):
        weighted_events([events_a], [.7])
    with pytest.raises(ValueError, match="IQR"):
        window_outcomes(a, greedy, 0)
