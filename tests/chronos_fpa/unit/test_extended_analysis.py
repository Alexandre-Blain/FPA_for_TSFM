import numpy as np
import pytest

from analyze_chronos_extended_batch import concatenate_arrays
from chronos_offline_precision import distances


def group(value):
    return {'context':np.arange(512,dtype=np.float32),'greedy_tokens':np.zeros(32,dtype=np.int64),
        'greedy_values':np.zeros(32,dtype=np.float32),'tokens':np.full((20,32),value,dtype=np.int64),
        'values':np.full((20,32),value,dtype=np.float32)}


def test_pool_is_a_distribution_not_an_average_of_distances():
    # Opposite signed shifts cancel in the pooled empirical law; averaging
    # block distances would be a different, incorrect estimator.
    reference=concatenate_arrays([group(0),group(2),group(0)])
    alternative=concatenate_arrays([group(2),group(0),group(0)])
    assert reference['values'].shape==(60,32)
    assert distances(reference['values'],alternative['values'])['w1']==0
    assert np.mean([distances(group(a)['values'],group(b)['values'])['w1'] for a,b in [(0,2),(2,0),(0,0)]])==pytest.approx(4/3)
    for i in range(60):assert np.all(reference['tokens'][i]==reference['values'][i])


def test_pool_rejects_different_contexts_and_greedy_paths():
    a,b=group(0),group(1);b['context'][0]=99
    with pytest.raises(AssertionError):concatenate_arrays([a,b])
    a,b=group(0),group(1);b['greedy_tokens'][3]=2
    with pytest.raises(AssertionError):concatenate_arrays([a,b])
