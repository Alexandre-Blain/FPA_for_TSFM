import hashlib
import json
import numpy as np
import pytest
import torch

from test_exploratory_window import FixedLawEngine, NumericTokenizer
from chronos_exploratory_window import collect_window
from chronos_pilot_validation import validate_cell
from chronos_extended_selection import planned_streams, stream_identity
from ensemble_store import isolated_window_store, read_snapshot
from run_chronos_microbenchmark import jsonable


def test_explicit_direct_blocks_have_predeclared_unique_rng_and_resume(tmp_path):
    context=np.arange(512,dtype=np.float32)
    base={'dataset_id':'fake','series_id':'A','forecast_origin':512,'context_sha256':hashlib.sha256(context.tobytes()).hexdigest(),
          'model_revision':'fake','grid_revision':'new','policy':'q50_mass90_cap8_greedy_first_v1'}
    streams=set()
    for seed in (3,4,5):
        scope={**base,'sampling_seed':seed};namespace,plan=planned_streams(scope,'wid',99)
        store=isolated_window_store(tmp_path,scope)
        result=collect_window(FixedLawEngine(),NumericTokenizer(),torch.tensor([1.]),context,store,scope,
            seed=seed,direct_samples=20,direct_block_mode=True,rng_namespace=namespace)
        with pytest.raises(ValueError):validate_cell(store.directory.parent,scope,jsonable(result))
        check=validate_cell(store.directory.parent,scope,jsonable(result),direct_samples=20)
        assert check['paths']==960
        for manifest,_ in check['records']:
            actual=manifest['metadata']['rng'];expected=plan[actual['role']]
            assert all(actual[k]==v for k,v in expected.items())
            assert actual['stream_id'] not in streams;streams.add(actual['stream_id'])
        if seed==3:
            engine=FixedLawEngine();engine.sample=lambda *a,**k:(_ for _ in ()).throw(AssertionError('resampling'))
            repeated=collect_window(engine,NumericTokenizer(),torch.tensor([1.]),context,store,scope,
                seed=seed,direct_samples=20,direct_block_mode=True,rng_namespace=namespace)
            assert repeated['accounting']['new_paths']==0
    assert len(streams)==144


def test_old_collection_rejects_direct20_without_explicit_batch_mode(tmp_path):
    from ensemble_store import EnsembleStore
    with pytest.raises(ValueError):
        collect_window(FixedLawEngine(),NumericTokenizer(),torch.tensor([1.]),np.arange(512,dtype=np.float32),
                       EnsembleStore(tmp_path/'objects'),{},direct_samples=20)
