import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import analyze_chronos_incremental as analysis
from chronos_incremental_features import FPA_FEATURES


def test_reference_plot_accepts_zero_and_full_success_wilson_roundoff():
    import matplotlib.pyplot as plt
    probability=np.array([0.,1.]);lo,hi=analysis.wilson(np.array([0,2000]),2000)
    errors=analysis.plotting_interval_errors(probability,lo,hi)
    assert (errors>=0).all()
    np.testing.assert_allclose(errors[0],probability-lo,atol=1e-15,rtol=0)
    np.testing.assert_allclose(errors[1],hi-probability,atol=1e-15,rtol=0)
    fig,ax=plt.subplots();ax.errorbar([0,1],probability,yerr=errors)
    fig.canvas.draw();plt.close(fig)
    with pytest.raises(ValueError,match='beyond numerical roundoff'):
        analysis.plotting_interval_errors([.5],[.6],[.8])


def test_full_h1_analysis_test_labels_cannot_change_fitted_models(tmp_path,monkeypatch):
    """End-to-end synthetic source data, including the matched-MC training.

    Replacing every test target changes measured errors but must leave every
    model's coefficients, validation choice and predicted risks unchanged.
    """
    windows=[];targets={};snapshots={};rng=np.random.default_rng(351)
    for ds in ['a','b','c','d','monash_weather']:
        splits=['ood_test']*4 if ds=='monash_weather' else ['train']*4+['validation']*2+['test']*2
        for index,split in enumerate(splits):
            wid=ds+str(index);matched=index%2==0
            w={'window_id':wid,'dataset_id':ds,'series_id':str(index),'split':split,
                'frequency':'1D' if ds=='monash_weather' else '1h','domain':'weather' if ds=='monash_weather' else 'energy',
                'exposure':'zero_shot','forecast_origin':512,'lag':1,'documented_temporal_boundary':512,
                'matched_cost_member':matched}
            windows.append(w);context=np.tile([0.,1.],256).astype(np.float32);greedy=np.ones(32)
            targets[wid]=rng.normal(size=32)*(.5+index)+1
            features={key:float(rng.uniform(.01,1)) for key in FPA_FEATURES}
            features.update(context_iqr=1.,seasonal_scale=1.,sga=float(rng.uniform()),
                mean_sd_iqr=1.,interval80_iqr=2.,trajectory_rms_diversity_iqr=1.,
                scenario_entropy=.5,scenario_groups=3.,seasonal_over_iqr=1.,iqr_over_seasonal=1.)
            directory=tmp_path/'H1'/wid;directory.mkdir(parents=True)
            (directory/'features.json').write_text(json.dumps(features))
            (directory/'forks.json').write_text(json.dumps([{'b':b,'selected_tokens':[10,11,12],
                'candidate_values':{'10':1.,'11':-1.,'12':3.},
                'probabilities':{'10':.6,'11':.3,'12':.1}} for b in (0,4,9)]))
            (directory/'feature_cost.json').write_text(json.dumps({'all_feature_seconds':.01}))
            records=[]
            for block in range(3):
                arrays={'values':rng.normal(size=(20,32))+1,'context':context,'greedy_values':greedy}
                records.append(({'identity':{'role':'natural','block':block},
                    'metadata':{'generation_seconds':.1,'sga_replay_seconds':.01,'sga_graph_seconds':.01}},arrays))
            if matched:records.append(({'identity':{'role':'matched_natural'},'metadata':{'generation_seconds':.1}},
                {'values':rng.normal(size=(32,32))+1}))
            snapshots[wid]=({'worker_model_loading_seconds':.01,'window_seconds':1.,'setup_seconds':.1},{'records':records})
    monkeypatch.setattr(analysis,'verify_complete',lambda run,phase,wid:snapshots[wid])
    out1=tmp_path/'analysis1';out1.mkdir();out2=tmp_path/'analysis2';out2.mkdir()
    config={'risk_ridge_alphas':[.1,1.,10.,100.],'bootstrap_replicates':5}
    first=analysis.evaluate_h1(tmp_path,windows,targets,out1,config)
    changed={w['window_id']:targets[w['window_id']]+(1000 if w['split'] in ('test','ood_test') else 0) for w in windows}
    second=analysis.evaluate_h1(tmp_path,windows,changed,out2,config)
    a=json.loads((out1/'H1_fitted_models.json').read_text());b=json.loads((out2/'H1_fitted_models.json').read_text())
    assert a==b
    p1=pd.read_csv(out1/'H1_out_of_sample_predictions.csv');p2=pd.read_csv(out2/'H1_out_of_sample_predictions.csv')
    np.testing.assert_array_equal(p1.score_log_loss,p2.score_log_loss)
    assert not np.array_equal(first['frame'].MASE,second['frame'].MASE)
    assert set(p1.method)=={'M0','M1','M2','M3','scale_metadata','M1_extra_MC','M1_cheap','M3_cheap'}
    matched=p1[p1.population=='matched_subset']
    assert matched.groupby(['target','method']).size().nunique()==1


def test_h2_analysis_counts_originals_and_keeps_taskA_IS_unclipped(tmp_path,monkeypatch):
    from chronos_incremental import EVENT_NAMES
    windows=[];targets={};snapshots={};attempts=tmp_path/'attempts';attempts.mkdir()
    methods=['MC','first_token_proportional','first_deviation_uniform',
        'first_deviation_proportional','first_deviation_neyman_cost','stratum_mixture_IS']
    p=np.array([.2,.4,.3,.5]);rng=np.random.default_rng(99)
    for ds in ('a','b','c','d'):
        wid=ds+'0';windows.append({'window_id':wid,'dataset_id':ds,'series_id':'0'})
        targets[wid]=rng.normal(size=32);context=np.tile([0.,1.],256);greedy=np.ones(32)
        directory=tmp_path/'H2'/wid;directory.mkdir(parents=True)
        marker={'setup_seconds':.1,'window_seconds':30.,'worker_model_loading_seconds':.1,
            'h2_repetitions':2,'paths':9999,'ensembles':20}
        snapshots[wid]=(marker,{'records':[({'identity':{'role':'h2_reference'}},
            {'context':context,'greedy_values':greedy,'values':rng.normal(size=(20,32))})]})
        (attempts/(wid+'.json')).write_text(json.dumps({'phase':'H2','exit_code':0,'windows':[wid],'elapsed_seconds':31.}))
        rows=[]
        for rep in range(2):
            for anchor in (60,120,240,480):
                for method in methods:
                    estimate=np.clip(p+rng.normal(0,.03,size=4),0,1)
                    if method=='stratum_mixture_IS' and ds=='a':estimate[3]=1.1
                    row={'window_id':wid,'dataset_id':ds,'series_id':'0','rep':rep,
                        'method':method,'anchor':anchor,'feasible':True,'N':anchor,
                        'probability':estimate.tolist(),'variance':(p*(1-p)/anchor).tolist(),
                        'lo':np.clip(estimate-.2,0,1).tolist(),'hi':np.clip(estimate+.2,0,1).tolist(),
                        'production_seconds':anchor*.01,'pilot_seconds_charged':0.,
                        'variable_seconds':anchor*.01,'common_setup_seconds':.1}
                    rows.append(row)
                    if method!='MC':rows.append({**row,'method':'matched_MC','matched_to':method,
                        'probability':np.clip(p+rng.normal(0,.03,size=4),0,1).tolist(),
                        'actual_cost_ratio_to_method':1.,'within_25pct_actual_cost':True,'matching_capped':False})
        d={'reference':{'probability':p.tolist()},'reference_N':2000,
            'reference_block_counts':[(p*1000).astype(int).tolist()]*2,'reference_block_N':[1000,1000],
            'reference_seconds':20.,'rows':rows}
        (directory/'event_estimates.json').write_text(json.dumps(d))
    monkeypatch.setattr(analysis,'verify_complete',lambda run,phase,wid:snapshots[wid])
    out=tmp_path/'analysis';out.mkdir()
    config={'h2_methods':methods,'h2_budget_anchors':[60,120,240,480],'bootstrap_replicates':9}
    result=analysis.evaluate_h2(tmp_path,windows,targets,out,config)
    assert result['primary']['N_sources']==4
    assert result['formal']['clusters']==4
    assert result['source'].groupby(['method','anchor','matched_to'],dropna=False).size().eq(4).all()
    assert result['frame']['estimate'].max()==1.1
    assert result['taskb']['probability'].max()<=1.
    assert result['taskb'].loc[result['taskb'].clipped_for_TaskB,'method'].eq('stratum_mixture_IS').all()
    assert result['taskb'].query("method=='MC'").groupby(['anchor','event']).size().eq(4).all()
    assert set(result['references'].event)==set(EVENT_NAMES)
    plot_frame=pd.DataFrame({'target_available':[True]*12,'split':['test']*8+['ood_test']*4,
        'dataset_id':['a']*8+['monash_weather']*4,'MASE':np.arange(1,13)/10,
        'MAE_IQR':np.arange(1,13)/20})
    scores={('full',target,method):rng.normal(size=12) for target in ('MASE','MAE_IQR') for method in ('M0','M1','M2','M3')}
    comparisons=[{'population':'full','target':target,'comparison':'M3-M1','group':group,
        'delta_NEAURC':-.05,'delta_NEAURC_CI95':[-.2,.1]}
        for target in ('MASE','MAE_IQR') for group in ('within_test','OOD_weather')]
    analysis.make_figures(tmp_path,out,{'frame':plot_frame,'scores':scores,'comparisons':comparisons},result)
    assert (out/'FPA_incremental_scientific_figures.pdf').read_bytes().startswith(b'%PDF')
    assert len(list(out.glob('*.png')))==6


def test_context_and_future_are_exactly_aligned_to_original_source(tmp_path,monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq
    values=np.arange(600,dtype=np.float32)/10
    dates=np.datetime64('2020-01-01T00:00:00','ns')+np.arange(600)*np.timedelta64(1,'h')
    table=pa.table({'id':['original0'],
        'target':pa.ListArray.from_arrays(pa.array([0,600]),pa.array(values)),
        'timestamp':pa.ListArray.from_arrays(pa.array([0,600]),pa.array(dates))})
    source=tmp_path/'source.parquet';pq.write_table(table,source)
    origin=520;context=values[origin-512:origin].copy();future=values[origin:origin+32].copy()
    np.savez_compressed(tmp_path/'contexts.npz',window0=context)
    window={'source_file':'source.parquet','source_sha256':analysis.digest(source),
        'series_id':'original0','window_id':'window0','forecast_origin':origin,
        'target_start_ns':int(dates[origin].astype(np.int64)),
        'target_end_ns':int(dates[origin+31].astype(np.int64))}
    monkeypatch.setattr(analysis,'ROOT',tmp_path)
    analysis.verify_selected_source_alignment(tmp_path,[window],{'window0':future})
    assert json.loads((tmp_path/'target_source_alignment.json').read_text())['checked_original_windows']==1
    wrong=future.copy();wrong[0]+=1
    with pytest.raises(AssertionError):analysis.verify_selected_source_alignment(tmp_path,[window],{'window0':wrong})
