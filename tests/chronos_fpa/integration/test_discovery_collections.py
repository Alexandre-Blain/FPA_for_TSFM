import hashlib
import json
import numpy as np
import pytest
from chronos_extended_selection import stream_identity
from ensemble_store import EnsembleStore,read_snapshot
from run_chronos_discovery import extra_scope,verify_extra,expected_extra_keys


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')


@pytest.mark.parametrize('wrong_conditioning',[False,True])
def test_H64_complete_blocks_preserve_prefixes_counts_and_rng(tmp_path,wrong_conditioning):
    context=np.linspace(1,2,512,dtype=np.float32);wid='test_window';scope={'dataset_id':'test','series_id':'original',
        'forecast_origin':512,'context_sha256':hashlib.sha256(context.tobytes()).hexdigest(),'model_revision':'pinned',
        'grid_revision':'grid','policy':'q50_mass90_cap8_greedy_first_v1','sampling_seed':11}
    save(tmp_path/'selection_manifest.json',{'config':{'natural_seed':12,'validation_seed':13,'cpd_seed':14,'cpd_validation_seed':15}})
    save(tmp_path/'cell_plan.json',[{'scope':scope,'window_id':wid,'cell_id':'c','block_index':0,'rng_namespace':'namespace'}])
    phase_scope,_=extra_scope(tmp_path,wid,'cpd',64);directory=tmp_path/'cpd'/wid;store=EnsembleStore(directory/'ensembles',scope=phase_scope);plan={}
    for block in range(3):
        for position in range(31):
            label=f'cpd_block{block}_P{position:02d}';rng=stream_identity(14+block,'namespace',label);plan[label]=rng
            prefix=[101 if wrong_conditioning and block==0 and position==15 else 100]*position
            tokens=np.full((20,64),100,dtype=np.int64);tokens[:,:position]=prefix
            identity={**phase_scope,'position':position,'role':'direct_cpd','token':None,'prefix':prefix,'block':block,'sample_count':20}
            store.put(identity,{'tokens':tokens,'values':np.zeros((20,64),dtype=np.float32),'context':context,'greedy_tokens':np.full(64,100,dtype=np.int64)}, {'rng':rng})
    save(tmp_path/'rng_plan.json',{'extra_'+wid:plan});snapshot=read_snapshot(store.directory,expected_scope=phase_scope)
    save(directory/'complete.json',{'files':{},'selection_file':None,'snapshot_id':snapshot['snapshot_id'],
        'manifest_sha256':snapshot['manifest_sha256'],'paths':1860,'ensembles':93})
    if wrong_conditioning:
        with pytest.raises(ValueError,match='greedy conditioning'):verify_extra(tmp_path,wid,'cpd',64)
    else:
        marker,actual=verify_extra(tmp_path,wid,'cpd',64)
        assert marker['paths']==1860 and len(actual['records'])==93


def test_N120_same_position_reference_and_null_are_shared(tmp_path):
    rows=[{'window_id':f'w{i//2}','b':0,'token':101+i,'selection':'random_control' if i<2 else 'scientific'} for i in range(8)]
    save(tmp_path/'validation_plan.json',{'contrasts':rows})
    save(tmp_path/'cell_plan.json',[{'window_id':'w0','cell_id':'c','block_index':0}])
    save(tmp_path/'cells/c/results.json',{'greedy_tokens':[100]*32})
    expected=expected_extra_keys(tmp_path,'w0','fresh_validation')
    assert expected=={(0,'reference',100,0,120),(0,'null',100,0,120),(0,'alternative',101,0,120),(0,'alternative',102,0,120)}
