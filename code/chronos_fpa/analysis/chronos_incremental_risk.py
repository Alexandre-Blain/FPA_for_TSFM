"""Small, equally calibrated risk models and source-level evaluation.

The fitting interface cannot consume test targets. Targets here are realized
forecast errors, never probabilities; regression calibration is not TSFM event
calibration. Feature definitions and the alpha grid are prospectively fixed.
"""
from __future__ import annotations

import itertools
import numpy as np
from chronos_discovery import rankdata


def ridge_calibrate(x_train,y_train,x_validation,y_validation,x_predict,alphas=(.1,1.,10.,100.)):
    train,validation,predict=map(lambda a:np.asarray(a,float),(x_train,x_validation,x_predict))
    y,yv=map(lambda a:np.log1p(np.asarray(a,float)),(y_train,y_validation))
    if not all(np.isfinite(a).all() for a in (train,validation,predict,y,yv)):
        raise ValueError('Finite training/validation features and losses required')
    if min(len(train),len(validation))<2 or (np.asarray(y_train)<0).any() or (np.asarray(y_validation)<0).any():
        raise ValueError('At least two training/validation losses required')
    mean=train.mean(0);scale=train.std(0);scale=np.where(scale>1e-12,scale,1.)
    z=(train-mean)/scale;zv=(validation-mean)/scale;zp=(predict-mean)/scale
    center=y.mean();gram=z.T@z;rhs=z.T@(y-center);candidates=[]
    for alpha in alphas:
        coef=np.linalg.solve(gram+float(alpha)*np.eye(gram.shape[0]),rhs)
        mse=float(np.mean((center+zv@coef-yv)**2))
        candidates.append((mse,-float(alpha),coef))
    mse,negative_alpha,coef=min(candidates,key=lambda a:(a[0],a[1]))
    return {'log_prediction':center+zp@coef,'mean':mean,'scale':scale,'coefficient':coef,
        'intercept':float(center),'alpha':-negative_alpha,'validation_log_MSE':mse,
        'grid':[{'alpha':-a,'validation_log_MSE':m} for m,a,_ in candidates]}


def risk_curve(score,loss):
    score,loss=np.asarray(score,float),np.asarray(loss,float)
    if len(score)!=len(loss) or len(loss)<2 or not np.isfinite(score).all() or not np.isfinite(loss).all():
        raise ValueError('At least two finite original-series risk pairs required')
    order=np.argsort(score,kind='stable');u=score[order];y=loss[order].copy()
    for v in np.unique(u):y[u==v]=y[u==v].mean()
    coverage=np.arange(1,len(y)+1)/len(y);risk=np.cumsum(y)/np.arange(1,len(y)+1)
    return coverage,risk


def risk_metrics(score,loss,log_prediction=None):
    loss=np.asarray(loss,float);score=np.asarray(score,float)
    coverage,risk=risk_curve(score,loss)
    aurc=float(np.trapezoid(risk,coverage));n=len(loss)
    oracle=float(np.trapezoid(np.cumsum(np.sort(loss))/np.arange(1,n+1),coverage))
    random=float(loss.mean()*(1-1/n));denominator=random-oracle
    result={'N':n,'AURC':aurc,'NEAURC':(aurc-oracle)/denominator if denominator>1e-12 else np.nan,
        'Spearman':float(np.corrcoef(rankdata(score),rankdata(loss))[0,1]) if np.ptp(score)>0 and np.ptp(loss)>0 else np.nan,
        'mean_loss':float(loss.mean()),'oracle_AURC':oracle,'random_AURC':random}
    for fraction in (.25,.5,.75,1.):
        k=max(1,int(np.ceil(fraction*n)))
        result[f'risk_at_{fraction:g}']=float(risk[k-1])
        result[f'actual_coverage_at_{fraction:g}']=float(coverage[k-1])
    if log_prediction is not None:
        pred=np.asarray(log_prediction,float)
        result['log_MSE']=float(np.mean((pred-np.log1p(loss))**2))
        result['loss_MSE']=float(np.mean((np.expm1(np.clip(pred,0,30))-loss)**2))
    return result


def hierarchical_indices(groups,rng):
    """Datasets, then original sources. Within-dataset channels may correlate.

    Repeated resampling does not create independent model trajectories. For one
    held-out dataset this is a source-only conditional interval, not evidence
    of generalization to a population of new datasets.
    """
    groups=np.asarray(groups);unique=np.unique(groups);pieces=[]
    for group in rng.choice(unique,len(unique),replace=True):
        indices=np.flatnonzero(groups==group)
        pieces.append(rng.choice(indices,len(indices),replace=True))
    return np.concatenate(pieces)


def bootstrap_delta(score_a,score_b,loss,groups,seed=2026112631,repeats=999):
    a,b,y=np.asarray(score_a),np.asarray(score_b),np.asarray(loss)
    rng=np.random.default_rng(seed);deltas=[]
    for _ in range(repeats):
        ix=hierarchical_indices(groups,rng)
        left=risk_metrics(a[ix],y[ix]);right=risk_metrics(b[ix],y[ix])
        deltas.append([left['NEAURC']-right['NEAURC'],left['AURC']-right['AURC']])
    d=np.asarray(deltas)
    return {'delta_NEAURC_CI95':np.nanquantile(d[:,0],[.025,.975]),
        'delta_AURC_CI95':np.nanquantile(d[:,1],[.025,.975]),'replicates':repeats,
        'bootstrap':'datasets then original IDs; fitted risk models held fixed; unmodeled within-dataset channel dependence remains'}


def paired_block_randomization(score_a,score_b,loss,groups,seed=2026112632,draws=9999):
    """One-sided sharp exchangeability test: lower AURC for A than B.

    Swap the entire pair of prediction vectors by dataset, or by original ID
    when evaluating a single dataset. Dataset-cluster tests are deliberately
    coarse with only four clusters. The source-level version is conditional on
    assuming independent identities, not independent physical weather stations.
    """
    a,b,y=np.asarray(score_a),np.asarray(score_b),np.asarray(loss)
    groups=np.asarray(groups);unique=np.unique(groups)
    if len(unique)==1:groups=np.arange(len(y));unique=np.unique(groups);unit='original_id_conditional'
    else:unit='dataset'
    lookup=np.searchsorted(unique,groups)
    def statistic(first,second):
        return risk_metrics(first,y)['AURC']-risk_metrics(second,y)['AURC']
    observed=statistic(a,b)
    if len(unique)<=12:
        choices=np.array(list(itertools.product([False,True],repeat=len(unique))))
        exhaustive=True
    else:
        choices=np.random.default_rng(seed).integers(0,2,size=(draws,len(unique))).astype(bool)
        exhaustive=False
    count=0
    for choice in choices:
        mask=choice[lookup]
        count+=statistic(np.where(mask,b,a),np.where(mask,a,b))<=observed+1e-15
    p=count/len(choices) if exhaustive else (count+1)/(len(choices)+1)
    return {'one_sided_p':float(p),'unit':unit,'clusters':len(unique),
        'exhaustive':exhaustive,'randomizations':len(choices),'delta_AURC':observed,
        'assumption':'paired method exchangeability by block under sharp null; source independence unresolved for correlated channels'}


def holm(pvalues):
    p=np.asarray(pvalues,float);order=np.argsort(p);out=np.empty(len(p));previous=0.
    for rank,index in enumerate(order):
        previous=max(previous,min(1.,(len(p)-rank)*p[index]));out[index]=previous
    return out
