import numpy as np
import pytest

from chronos_offline_precision import distances, supports
from chronos_propagation_baselines import predicted_paths, choose_contrasts


def test_absolute_support_uses_forecast_coordinate_minus_branch():
    x=np.zeros((3,32));b=4;j=8.;phi=.5
    for name,coords in supports(b).items():
        p=predicted_paths(x,b,j,phi,coords,'ar1')
        np.testing.assert_allclose(p[0],j*phi**(coords-b))
        assert p[0,0]==pytest.approx(j*phi**(int(coords[0])-b))
    with pytest.raises(ValueError):predicted_paths(x,b,j,phi,[4,5],'persistent')


def test_equal_reference_distances_do_not_imply_baseline_fit():
    reference=np.zeros((4,32));alternative=-np.ones((4,22))
    prediction=predicted_paths(reference,0,1,.5,np.arange(1,23),'persistent')
    assert distances(reference[:,:22],alternative)['w1']==1
    assert distances(reference[:,:22],prediction)['w1']==1
    assert distances(alternative,prediction)['w1']==2
    assert distances(alternative,prediction)['ed']==4


def test_shift_preserves_same_law_mc_distance_and_negative_ar1_signs():
    rng=np.random.default_rng(7);a=rng.normal(size=(7,32));b=rng.normal(size=(7,32))
    coords=supports(2)['final8']
    for model in ('persistent','ar1'):
        pa=predicted_paths(a,2,3,-.5,coords,model);pb=predicted_paths(b,2,3,-.5,coords,model)
        assert distances(pa,pb)['w1']==pytest.approx(distances(a[:,coords],b[:,coords])['w1'])
        assert distances(pa,pb)['ed']==pytest.approx(distances(a[:,coords],b[:,coords])['ed'])


def test_selection_uses_fixed_metric_order_and_random_control_is_distinct():
    rows=[{'b':0,'token':i,'w1_fixed22':v,'ed_fixed22':e} for i,v,e in [(1,10,1),(2,2,9),(3,3,2),(4,1,1)]]
    chosen=choose_contrasts(rows,4,'window')
    assert chosen['selected']==[[0,2],[0,1]]
    assert chosen['random_control'] not in chosen['selected']
    assert chosen==choose_contrasts(list(reversed(rows)),4,'window')


def test_extended_cohort_excludes_legacy_series_and_ignores_future_values(tmp_path):
    import json
    from chronos_extended_selection import select_extended
    folder=tmp_path/'data/raw/chronos_benchmark';folder.mkdir(parents=True)
    old=tmp_path/'result/legacy';old.mkdir(parents=True)
    old.joinpath('chronos_scan_summary.csv').write_text('dataset_name,series_id\n'+''.join(f'm4_daily,T{i:06d}\n' for i in range(5))+
        ''.join(f'ercot,{s}\n' for s in ['COAST','EAST','FAR_WEST','NORTH','NORTH_C'])+
        ''.join(f'exchange_rate,currency_{i}\n' for i in range(1,6)),encoding='utf-8')
    pilot=tmp_path/'result/local_pilot_20261120T184035Z';pilot.mkdir()
    pilot.joinpath('selection_manifest.json').write_text(json.dumps({'windows':[{'dataset_id':'ercot','series_id':'SOUTHERN'}]}))
    ids={'m4_daily':[f'T{i:06d}' for i in range(9)],'ercot':['COAST','EAST','FAR_WEST','NORTH','NORTH_C','SOUTHERN','SOUTH_C','WEST'],
         'exchange_rate':[f'currency_{i}' for i in range(1,9)]}
    rows={}
    for ds,series in ids.items():
        rows[ds]=[{'series_id':s,'target':(np.arange(600,dtype=float)**(1+i/20)+np.sin(np.arange(600))).tolist()} for i,s in enumerate(series)]
        (folder/f'autogluon_chronos_datasets__{ds}__train.jsonl').write_text('\n'.join(json.dumps(r) for r in rows[ds]),encoding='utf-8')
    config={'cohort_counts':{'m4_daily':4,'ercot':2,'exchange_rate':2},'selection_seed':5}
    a,_=select_extended(tmp_path,config)
    assert len(a['windows'])==8
    assert {w['series_id'] for w in a['windows'] if w['dataset_id']=='ercot'}=={'SOUTH_C','WEST'}
    assert {w['series_id'] for w in a['windows'] if w['dataset_id']=='m4_daily'}=={f'T{i:06d}' for i in range(5,9)}
    for ds in ids:
        for r in rows[ds]:r['target'][-32:]=[1e12]*32
        (folder/f'autogluon_chronos_datasets__{ds}__train.jsonl').write_text('\n'.join(json.dumps(r) for r in rows[ds]),encoding='utf-8')
    b,_=select_extended(tmp_path,config)
    fields=('dataset_id','series_id','stratum','forecast_origin','context_sha256')
    assert [{k:w[k] for k in fields} for w in a['windows']]==[{k:w[k] for k in fields} for w in b['windows']]
