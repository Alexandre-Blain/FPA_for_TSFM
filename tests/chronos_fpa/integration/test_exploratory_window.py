from types import SimpleNamespace

import numpy as np
import pytest
import torch

from chronos_exploratory import CachedDecoder
from chronos_exploratory_window import collect_window
from ensemble_store import EnsembleStore, isolated_window_store, read_fork_snapshot, read_snapshot


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


def test_interleaved_windows_same_tokens_seed_and_campaign_are_isolated(tmp_path, monkeypatch):
    import hashlib
    import shutil
    context_a = np.arange(512, dtype=np.float32)
    context_b = context_a + 10
    base = {"dataset_id": "fake", "forecast_origin": 512, "model_revision": "fake",
            "grid_revision": "pilot_v1", "policy": "q50_mass90_cap8_greedy_first_v1",
            "sampling_seed": 77}
    a = {**base, "series_id": "A", "context_sha256": hashlib.sha256(context_a.tobytes()).hexdigest()}
    b = {**base, "series_id": "B", "context_sha256": hashlib.sha256(context_b.tobytes()).hexdigest()}
    sa, sb = isolated_window_store(tmp_path, a), isolated_window_store(tmp_path, b)
    assert sa.directory != sb.directory
    put, calls = sa.put, []

    def interleave(identity, arrays, metadata):
        result = put(identity, arrays, metadata)
        calls.append(identity)
        if len(calls) == 3:
            collect_window(FixedLawEngine(), NumericTokenizer(), torch.tensor([1.]), context_b, sb, b,
                           seed=77, samples_per_group=2)
            raise KeyboardInterrupt("A interrupted while B completed")
        return result

    monkeypatch.setattr(sa, "put", interleave)
    with pytest.raises(KeyboardInterrupt):
        collect_window(FixedLawEngine(), NumericTokenizer(), torch.tensor([1.]), context_a, sa, a,
                       seed=77, samples_per_group=2)
    assert len(read_fork_snapshot(sb.directory.parent / "forks", expected_scope=b)["forks"]) == 10
    assert read_fork_snapshot(sa.directory.parent / "forks", expected_scope=a)["forks"] == []
    monkeypatch.setattr(sa, "put", put)
    resumed = collect_window(FixedLawEngine(), NumericTokenizer(), torch.tensor([1.]), context_a, sa, a,
                             seed=77, samples_per_group=2)
    assert resumed["accounting"]["reused_ensembles"] == 3
    assert len(read_fork_snapshot(sa.directory.parent / "forks", expected_scope=a)["forks"]) == 10
    before = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in tmp_path.rglob("*") if p.is_file()}
    snap_a, snap_b = read_snapshot(sa.directory, expected_scope=a), read_snapshot(sb.directory, expected_scope=b)
    assert set(snap_a["object_ids"]).isdisjoint(snap_b["object_ids"])
    assert before == {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in before}
    with pytest.raises(ValueError, match="another window"):
        read_snapshot(sa.directory, expected_scope=b)
    with pytest.raises(ValueError, match="another window"):
        read_fork_snapshot(sb.directory.parent / "forks", expected_scope=a)
    foreign_manifest = snap_b["records"][0][0]
    with pytest.raises(ValueError, match="another window"):
        sa.get(foreign_manifest["identity"])
    pending = sa.directory / ".pending-foreign"
    shutil.copytree(sb.directory / foreign_manifest["task_id"], pending)
    with pytest.raises(ValueError, match="another window"):
        sa.recover_pending(pending)
    assert pending.is_dir()  # rejected evidence is preserved
    shutil.copytree(sb.directory / foreign_manifest["task_id"], sa.directory / foreign_manifest["task_id"])
    with pytest.raises(ValueError, match="Foreign window"):
        read_snapshot(sa.directory)


def test_full_collection_with_cap_eight_and_large_residual(tmp_path):
    class UniformLaw(FixedLawEngine):
        def __init__(self):
            super().__init__()
            self.config.n_tokens = 52

        def prefix_state(self, prefix):
            return SimpleNamespace(logits=torch.tensor([[-float("inf")] * 2 + [0.] * 50]))

        def sample(self, prefix, horizon, count, generator, batch_size=None):
            suffix = torch.randint(2, 52, (count, horizon - len(prefix)), generator=generator)
            return torch.cat((torch.tensor(prefix).long().repeat(count, 1), suffix), dim=1)

    store = EnsembleStore(tmp_path / "ensembles")
    report = collect_window(UniformLaw(), NumericTokenizer(), torch.tensor([1.]),
                            np.arange(512, dtype=np.float32), store, {"model_revision": "fake"},
                            samples_per_group=2)
    for fork in report["forks"]:
        assert len(fork["selected_tokens"]) == 8 and not fork["target_attained"]
        assert fork["selected_mass"] == pytest.approx(.16)
        assert fork["residual_mass"] == pytest.approx(.84)
        assert len(fork["residual_ids"]) == 42
    assert len(read_fork_snapshot(tmp_path / "forks")["forks"]) == 10
    residuals = [(m, a) for m, a in read_snapshot(store.directory)["records"] if m["identity"]["role"] == "residual"]
    for manifest, arrays in residuals:
        b = manifest["identity"]["position"]
        assert set(arrays["tokens"][:, b]).issubset(set(report["forks"][b]["residual_ids"]))
