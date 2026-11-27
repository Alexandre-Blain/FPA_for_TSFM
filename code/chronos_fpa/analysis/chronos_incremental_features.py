"""Small predeclared H1 feature family; accepts generated paths, never targets."""
from __future__ import annotations
import numpy as np

from chronos_discovery import uncertainty_features
from chronos_distances import empirical_w1_by_horizon, energy_distance_v
from chronos_incremental import future_events, decision_variance

FPA_FEATURES = (
    'F1_mean_W1', 'F1_mean_ED', 'F1_same_token_W1',
    'F2_prefix_q_weighted_W1', 'F2_prefix_q_weighted_ED',
    'F3_q90_W1', 'F3_max_W1',
    'F4_between_group_corrected', 'F4_between_token_crossblock', 'F4_within_token_crossblock',
    'F5_late8_W1', 'F5_early_minus_late_W1',
    'F6_weighted_event_sensitivity', 'F6_max_event_sensitivity',
)


def concatenate(records):
    return {name: np.concatenate([a[name] for _,a in records],axis=0)
            for name in ('tokens','values')}


def h1_features(context, greedy, forks, records, seasonal_lag):
    """Reference laws and residuals include both independent N20 blocks."""
    context = np.asarray(context,float); greedy = np.asarray(greedy,float)
    iqr = float(np.subtract(*np.percentile(context,[75,25])))
    seasonal = float(np.mean(abs(context[seasonal_lag:]-context[:-seasonal_lag])))
    naturals = [(m,a) for m,a in records if m['identity']['role']=='natural']
    natural = concatenate(naturals)['values']
    features = uncertainty_features(natural,context)
    features.update({'context_iqr':iqr, 'log_context_iqr':float(np.log(iqr)),
        'context_std_iqr':float(context.std()/iqr),
        'diff_std_iqr':float(np.diff(context).std()/iqr),
        'historical_variability':float(np.mean(abs(np.diff(context)))/iqr),
        'seasonal_scale':seasonal,'seasonal_over_iqr':seasonal/iqr,'iqr_over_seasonal':iqr/seasonal,
        'lag1':float(np.corrcoef(context[:-1],context[1:])[0,1]),
        'log_abs_context_level':float(np.log1p(abs(context.mean()))),
        'seasonal_lag':float(seasonal_lag)})
    selected = [f for f in forks if f['b'] in (0,4,9)]
    features.update({'local_entropy':float(np.mean([f['entropy_q50'] for f in selected])),
        'p_sel_entropy':float(np.mean([f['entropy_p_sel'] for f in selected])),
        'greedy_probability':float(np.mean([f['probabilities'][str(f['greedy'])] for f in selected])),
        'probability_margin':float(np.mean([f['margin'] for f in selected])),
        'candidate_count':float(sum(len(f['selected_tokens'])-1 for f in selected)),
        'mean_support_size':float(np.mean([len(f['probabilities']) for f in selected])),
        'mean_residual_mass':float(np.mean([f['residual_mass'] for f in selected])),
        'numeric_jump_mean':float(np.mean([abs(f['candidate_values'][str(t)]-greedy[f['b']])/iqr
             for f in selected for t in f['selected_tokens'] if t!=f['greedy']])) if any(len(f['selected_tokens'])>1 for f in selected) else 0.,
        'sga':float(np.mean([m['metadata']['sga_score'] for m,a in naturals]))})
    distances=[];energies=[];nulls=[];maxevents=[];profiles=[];between=[];weighted=[]
    for f in selected:
        b=f['b'];q={int(t):v for t,v in f['probabilities'].items()}
        groups=[];weights=[];tokens=[]
        for token in f['selected_tokens']+[None] if f['residual_mass']>0 else f['selected_tokens']:
            role='residual' if token is None else 'conditional'
            data=sorted([(m,a) for m,a in records if m['identity']['role']==role and m['identity']['position']==b and m['identity'].get('token')==token],key=lambda x:x[0]['identity']['block'])
            groups.append(concatenate(data));weights.append(f['residual_mass'] if token is None else q[token]);tokens.append(token)
        reference=groups[tokens.index(f['greedy'])]['values']
        ref_events=future_events(reference,context,greedy).mean(0)
        pw1=ped=pevent=0.
        for a,w,t in zip(groups,weights,tokens):
            if t==f['greedy']:
                continue
            profile=empirical_w1_by_horizon(reference[:,b+1:b+23],a['values'][:,b+1:b+23])/iqr
            w1=float(profile.mean());ed=energy_distance_v(reference[:,b+1:b+23],a['values'][:,b+1:b+23])/iqr
            event_gap=abs(future_events(a['values'],context,greedy).mean(0)-ref_events)
            pw1+=w*w1;ped+=w*ed;pevent+=w*float(event_gap.mean())
            if t is not None:
                distances.append(w1);energies.append(ed);profiles.append(profile);maxevents.append(float(event_gap.max()))
        null=concatenate([(m,a) for m,a in records if m['identity']['role']=='null' and m['identity']['position']==b])['values']
        nulls.append(float(empirical_w1_by_horizon(reference[:,b+1:b+23],null[:,b+1:b+23]).mean()/iqr))
        between.append(decision_variance(groups,weights,q,b,context))
        weighted.append((f['greedy_prefix_mass'],pw1,ped,pevent))
    denominator=sum(x[0] for x in weighted)
    if denominator<=0:raise ValueError('b0 prefix has probability one')
    features.update({'F1_mean_W1':float(np.mean(distances)) if distances else 0.,
        'F1_mean_ED':float(np.mean(energies)) if energies else 0.,'F1_same_token_W1':float(np.mean(nulls)),
        'F2_prefix_q_weighted_W1':sum(m*w for m,w,e,p in weighted)/denominator,
        'F2_prefix_q_weighted_ED':sum(m*e for m,w,e,p in weighted)/denominator,
        'F3_q90_W1':float(np.quantile(distances,.9)) if distances else 0.,
        'F3_max_W1':max(distances,default=0.),
        **{'F4_'+k:float(np.mean([v[k] for v in between])) for k in between[0]},
        'F5_late8_W1':float(np.mean([p[-8:].mean() for p in profiles])) if profiles else 0.,
        'F5_early_minus_late_W1':float(np.mean([p[:8].mean()-p[-8:].mean() for p in profiles])) if profiles else 0.,
        'F6_weighted_event_sensitivity':sum(m*p for m,w,e,p in weighted)/denominator,
        'F6_max_event_sensitivity':max(maxevents,default=0.)})
    if any(not np.isfinite(v) for v in features.values()):
        raise ValueError('Nonfinite feature; no test-dependent imputation')
    assert all(k in features for k in FPA_FEATURES)
    return features
