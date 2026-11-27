import numpy as np
import pytest

from chronos_incremental_risk import ridge_calibrate,risk_metrics,risk_curve,holm


def test_risk_fit_never_scales_on_validation_or_predict_features():
    x=np.arange(40,dtype=float).reshape(20,2);y=np.linspace(.1,2.,20)
    validation=np.arange(16,dtype=float).reshape(8,2)+100
    predict=np.array([[1.,2.],[1e8,-1e8]])
    a=ridge_calibrate(x,y,validation,np.linspace(.2,1.,8),predict)
    b=ridge_calibrate(x,y,validation,np.linspace(.2,1.,8),predict[:1])
    np.testing.assert_array_equal(a['mean'],x.mean(0))
    np.testing.assert_array_equal(a['scale'],x.std(0))
    assert a['alpha']==b['alpha']
    assert a['log_prediction'][0]==pytest.approx(b['log_prediction'][0])
    np.testing.assert_array_equal(a['coefficient'],b['coefficient'])
    assert set(g['alpha'] for g in a['grid'])=={.1,1.,10.,100.}


def test_risk_ties_have_no_identity_order_advantage_and_normalization_matches():
    score=[0.,0.,1.,1.];loss=np.array([1.,3.,2.,8.])
    c,r=risk_curve(score,loss)
    np.testing.assert_allclose(r,[2.,2.,3.,3.5])
    a=risk_metrics(score,loss);b=risk_metrics(score,loss[[1,0,3,2]])
    assert a['NEAURC']==pytest.approx(b['NEAURC'])
    assert a['risk_at_0.5']==2.
    assert risk_metrics(loss,loss)['NEAURC']==pytest.approx(0.)
    assert risk_metrics(np.ones(4),loss)['NEAURC']==pytest.approx(1.)
    np.testing.assert_allclose(holm([.01,.04,.03]),[.03,.06,.06])
