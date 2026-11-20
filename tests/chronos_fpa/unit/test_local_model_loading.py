from types import SimpleNamespace

import pytest
import torch


def test_pinned_offline_loader_applies_revision_before_model_access(monkeypatch):
    import chronos_io
    import transformers
    calls = []
    config = SimpleNamespace(model_type="seq2seq")
    model = torch.nn.Linear(1, 1)
    model.config = SimpleNamespace(_commit_hash="revision-a")
    monkeypatch.setattr(transformers.AutoConfig, "from_pretrained", lambda model_id, **kwargs: calls.append(("config", kwargs)) or object())
    monkeypatch.setattr(transformers.AutoModelForSeq2SeqLM, "from_pretrained", lambda model_id, **kwargs: calls.append(("model", kwargs)) or model)
    monkeypatch.setattr(chronos_io.ChronosConfigLite, "from_transformers_config", lambda _: config)
    monkeypatch.setattr(chronos_io, "create_tokenizer_from_config", lambda _: "tokenizer")
    loaded, tokenizer, _ = chronos_io.load_chronos_t5_raw("cached-model", device="cpu", revision="revision-a", local_files_only=True, attn_implementation="eager")
    assert loaded is model and not model.training and tokenizer == "tokenizer"
    assert all(options["revision"] == "revision-a" and options["local_files_only"] for _, options in calls)
    assert calls[1][1]["attn_implementation"] == "eager"
    with pytest.raises(ValueError, match="revision"):
        chronos_io.load_chronos_t5_raw("cached-model", device="cpu", revision="different", local_files_only=True)
