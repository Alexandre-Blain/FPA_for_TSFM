from types import SimpleNamespace

import numpy as np
import pytest
import torch

from chronos_exploratory import CachedDecoder
from chronos_exploratory_window import collect_window
from ensemble_store import EnsembleStore, read_fork_snapshot, read_snapshot


class FixedLawEngine:
    device = torch.device("cpu")
    sample_residual = CachedDecoder.sample_residual

    def __init__(self):
        self.config = SimpleNamespace(n_special_tokens=2, n_tokens=5, pad_token_id=0, eos_token_id=1)
        self.model = torch.nn.Linear(1, 1).eval()
        self.calls = 0

    def greedy(self, horizon):
        return torch.full((horizon,), 2)

    def prefix_state(self, prefix):
        return SimpleNamespace(logits=torch.tensor([[-float("inf"), -float("inf"), np.log(.8), np.log(.15), np.log(.05)]], dtype=torch.float32))

    def sample(self, prefix, horizon, count, generator, batch_size=None):
        self.calls += 1
        paths = torch.tensor(prefix, dtype=torch.long).repeat(count, 1)
        suffix = torch.multinomial(torch.tensor([.8, .15, .05]), count * (horizon - len(prefix)),
                                   replacement=True, generator=generator).reshape(count, -1) + 2
        return torch.cat((paths, suffix), dim=1)


class NumericTokenizer:
    def output_transform(self, tokens, scale):
        return tokens.float()


def test_dense_mixture_direct_laws_and_interrupted_ensemble_resume(tmp_path, monkeypatch):
    store = EnsembleStore(tmp_path / "ensembles")
    original_put = store.put
    saved = []

    def interrupt(identity, arrays, metadata):
        result = original_put(identity, arrays, metadata)
        saved.append(identity)
        if len(saved) == 3:
            raise KeyboardInterrupt("three ensembles durable")
        return result

    monkeypatch.setattr(store, "put", interrupt)
    kwargs = dict(samples_per_group=2, overlap_positions=(0, 9, 10))
    context = np.arange(512, dtype=np.float32)
    with pytest.raises(KeyboardInterrupt):
        collect_window(FixedLawEngine(), NumericTokenizer(), torch.tensor([1.]), context, store, {"model_revision": "fake"}, **kwargs)
    assert len(read_snapshot(store.directory)["records"]) == 3
    assert read_fork_snapshot(tmp_path / "forks")["forks"] == []
    monkeypatch.setattr(store, "put", original_put)
    report = collect_window(FixedLawEngine(), NumericTokenizer(), torch.tensor([1.]), context, store, {"model_revision": "fake"}, **kwargs)
    assert report["accounting"]["reused_ensembles"] == 3
    assert len(report["forks"]) == 10 and set(report["outcome_distributions"]) == {str(t) for t in range(16)}
    assert all(row["selected_mass"] + row["residual_mass"] == pytest.approx(1.) for row in report["forks"])
    assert all(row["residual_mass"] > 0 for row in report["forks"])
    assert len(read_fork_snapshot(tmp_path / "forks")["forks"]) == 10
    direct = [m for m, _ in read_snapshot(store.directory)["records"] if m["identity"]["role"] == "direct_cpd"]
    assert {m["identity"]["position"] for m in direct} == set(range(11, 16))
    assert all(m["identity"]["sample_count"] == 60 for m in direct)
    completed = FixedLawEngine()
    completed.sample = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must reuse saved ensembles"))
    repeated = collect_window(completed, NumericTokenizer(), torch.tensor([1.]), context, store, {"model_revision": "fake"}, **kwargs)
    assert repeated["accounting"]["new_paths"] == 0
    np.testing.assert_array_equal(report["outcome_distributions"]["10"]["event_probability"],
                                  repeated["outcome_distributions"]["10"]["event_probability"])
