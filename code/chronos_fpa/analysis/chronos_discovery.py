"""Target-free scenario descriptors and bounded exploratory comparisons.

SGA is an independent port of the authors' public implementation, commit
03d8133912c4e5c813cae084ca5f5358d7e5a206, MIT. The source is archived with
the experiment. Its code conventions differ from the paper's equations:
seasonal-error scaling, DTW/length, first-match merging and 1+entropy weights.
"""
from __future__ import annotations

import numpy as np


def rankdata(values):
    values=np.asarray(values,float)
    _,inverse,counts=np.unique(values,return_inverse=True,return_counts=True)
    return (np.cumsum(counts)-(counts+1)/2+1)[inverse]


EVENT_NAMES = ('excursion_up', 'excursion_down', 'terminal_up', 'terminal_down',
               'persistent_up', 'persistent_down', 'direction_reversal', 'late_reconvergence')


def scenario_events(paths, context, greedy):
    """Absolute, fixed-window events. Neither targets nor samples set thresholds."""
    paths, context, greedy = map(lambda x: np.asarray(x, dtype=float), (paths, context, greedy))
    scale = float(np.subtract(*np.percentile(context, [75, 25])))
    if scale <= 0 or not np.isfinite(scale):
        raise ValueError('A positive context IQR is required')
    z = (paths - context[-1]) / scale
    early = z[:, :8].mean(axis=1)
    late = z[:, -8:].mean(axis=1)
    delta = (paths-greedy) / scale
    return np.column_stack((z.max(axis=1) > 1, z.min(axis=1) < -1,
        z[:, -1] > .5, z[:, -1] < -.5,
        np.mean(z[:, -8:] > .5, axis=1) >= .75,
        np.mean(z[:, -8:] < -.5, axis=1) >= .75,
        ((early > .25) & (late < -.25)) | ((early < -.25) & (late > .25)),
        (np.mean(abs(delta[:, :8]), axis=1) > .5) & (np.mean(abs(delta[:, -8:]), axis=1) < .1)))


def behaviour_codes(paths, context):
    """Context-defined coarse scenario grouping, NOT SGA or learned true modes."""
    a=np.asarray(paths, dtype=float);c=np.asarray(context,dtype=float)
    scale=np.subtract(*np.percentile(c,[75,25]))
    if scale<=0:raise ValueError('Invalid context IQR')
    z=(a-c[-1])/scale
    terminal=np.digitize(z[:,-1],[-1,-.25,.25,1])
    slope=np.digitize(z[:,-8:].mean(1)-z[:,:8].mean(1),[-.25,.25])
    excursion=(z.max(1)>1).astype(int)+2*(z.min(1)<-1).astype(int)
    return terminal+5*slope+15*excursion


def coverage(discovered, reference):
    a,b=set(map(int,discovered)),set(map(int,reference))
    return {'discovered_groups':len(a),'reference_groups':len(b),'shared_groups':len(a&b),
            'reference_recall':len(a&b)/len(b) if b else np.nan,
            'unobserved_in_reference':len(a-b),'missed_reference_groups':len(b-a)}


def uncertainty_features(paths, context):
    a=np.asarray(paths,dtype=float);c=np.asarray(context,dtype=float)
    scale=np.subtract(*np.percentile(c,[75,25]))
    if scale<=0:raise ValueError('Invalid context IQR')
    codes,counts=np.unique(behaviour_codes(a,c),return_counts=True)
    p=counts/counts.sum()
    return {'mean_sd_iqr':float(np.mean(a.std(0,ddof=1))/scale),
            'interval80_iqr':float(np.mean(np.quantile(a,.9,axis=0)-np.quantile(a,.1,axis=0))/scale),
            'trajectory_rms_diversity_iqr':float(np.mean(np.linalg.norm(a[:,None]-a[None,:],axis=2))/np.sqrt(a.shape[1])/scale),
            'scenario_entropy':float(-np.sum(p*np.log(p))), 'scenario_groups':len(codes)}


def risk_ranking(uncertainty, losses):
    """Authors' trapezoidal AURC, with expected tied ranks (no ID tie advantage).

    NEAURC is undefined if oracle and random risk curves coincide.
    Ground truth is consumed ONLY by this evaluation function.
    """
    u,y=np.asarray(uncertainty,float),np.asarray(losses,float)
    if u.ndim!=1 or len(u)!=len(y) or len(u)<2 or not np.isfinite(u).all() or not np.isfinite(y).all():
        raise ValueError('Need at least two finite uncertainty/loss pairs')
    order=np.argsort(u,kind='stable');v=y[order].copy();us=u[order]
    for x in np.unique(us):v[us==x]=v[us==x].mean()
    x=np.arange(1,len(y)+1)/len(y)
    def area(v):return float(np.trapezoid(np.cumsum(v)/np.arange(1,len(v)+1),x))
    a,o,r=area(v),area(np.sort(y)),float(y.mean()*(1-1/len(y)))
    rho=float(np.corrcoef(rankdata(u),rankdata(y))[0,1]) if np.ptp(u)>0 and np.ptp(y)>0 else np.nan
    return {'aurc':a,'oracle_aurc':o,'random_aurc':r,'neaurc':(a-o)/(r-o) if r-o>1e-12 else np.nan,'spearman':rho,'windows':len(y)}


def dtw_distance(a,b):
    """Unconstrained squared-local-cost DTW with sqrt, like dtaidistance."""
    a,b=np.asarray(a,float),np.asarray(b,float)
    d=np.full((len(a)+1,len(b)+1),np.inf);d[0,0]=0
    for i in range(1,len(a)+1):
        for j in range(1,len(b)+1):d[i,j]=(a[i-1]-b[j-1])**2+min(d[i-1,j],d[i,j-1],d[i-1,j-1])
    return float(np.sqrt(d[-1,-1]))


def sga_author_code(paths, top20_entropy, seasonal_error, slice_length=4, threshold=.25, alpha=.1):
    """Exact graph/scoring conventions of the pinned author code, no resampling.

    Inputs: K numerical paths and their matching generation-policy top20
    renormalized entropies [K,H]. Target-free seasonal scale from context.
    This is an H32/q50 adaptation, not the original multi-dataset evaluation.
    """
    a,e=np.asarray(paths,float),np.asarray(top20_entropy,float)
    if a.shape!=e.shape or a.ndim!=2 or not np.isfinite(e).all():raise ValueError('Matching path entropies required')
    scale=max(abs(float(seasonal_error)),1e-4)
    nodes=[{'slice':None,'layer':-1,'entropy':[],'parents':set()}]
    for path,ent in zip(a,e):
        previous=0
        for layer,start in enumerate(range(0,a.shape[1],slice_length)):
            sl=path[start:start+slice_length]/scale;score=float(ent[start:start+slice_length].mean())
            found=next((i for i,n in enumerate(nodes) if n['layer']==layer and dtw_distance(n['slice'],sl)/len(sl)<=threshold),None)
            if found is None:
                found=len(nodes);nodes.append({'slice':sl,'layer':layer,'entropy':[],'parents':set()})
            nodes[found]['entropy'].append(score);nodes[found]['parents'].add(previous);previous=found
    centrality={}
    for i in sorted(range(len(nodes)),key=lambda i:nodes[i]['layer']):
        n=nodes[i];w=1+np.mean(n['entropy']) if n['entropy'] else 1.
        centrality[i]=max(float(w),0.)+alpha*sum(centrality[j] for j in n['parents'])
    return {'sga_author_code':sum(centrality.values()),'graph_nodes':len(nodes),
            'graph_edges':sum(len(n['parents']) for n in nodes),'K':len(a),'slice_length':slice_length,
            'seasonal_error':float(seasonal_error),'scale_floor':1e-4}


def choose_validation(candidates, seed=2026112491, maximum=8):
    """<=6 mechanisms plus >=2 random controls, <=2/window; no targets/reference.

    Scientific slots cycle datasets/mechanisms, maximizing block0-only event
    probability contrast, persistence, transient response and sparse misses.
    The random controls are sampled first, then excluded from scientific slots.
    """
    rows=sorted(candidates,key=lambda r:(r['window_id'],r['b'],r['token']))
    if not rows:return []
    rng=np.random.default_rng(seed);counts={};chosen=[];used=set()
    datasets=sorted({r['dataset'] for r in rows})
    for ds in datasets[:2]:
        pool=[r for r in rows if r['dataset']==ds and counts.get(r['window_id'],0)<2]
        if not pool:continue
        r=pool[int(rng.integers(len(pool)))];key=(r['window_id'],r['b'],r['token']);used.add(key);counts[r['window_id']]=counts.get(r['window_id'],0)+1
        chosen.append({**r,'selection':'random_control','hypothesis':'fixed event probability difference','validation_outcome':r['event']})
    for slot in range(maximum-len(chosen)):
        mechanism=('event_gap','persistent_score','transient_score','sparse_miss_score')[slot%4]
        ds=datasets[slot%len(datasets)]
        pool=[r for r in rows if r['dataset']==ds and (r['window_id'],r['b'],r['token']) not in used and counts.get(r['window_id'],0)<2]
        if not pool:pool=[r for r in rows if (r['window_id'],r['b'],r['token']) not in used and counts.get(r['window_id'],0)<2]
        if not pool:break
        r=max(pool,key=lambda r:(r[mechanism],-r['b'],-r['token']));used.add((r['window_id'],r['b'],r['token']));counts[r['window_id']]=counts.get(r['window_id'],0)+1
        chosen.append({**r,'selection':mechanism,'hypothesis':'fixed event probability difference','validation_outcome':r['event']})
    assert len(chosen)<=8 and max(counts.values())<=2
    return chosen
