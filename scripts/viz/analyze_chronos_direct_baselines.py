"""Stage A: compare alternatives directly with numerical pushforward laws."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code/chronos_fpa'))
import bootstrap  # noqa: F401,E402
import numpy as np
import pandas as pd
from chronos_pilot_validation import read_complete_cell
from chronos_offline_precision import distances, supports, permutation_distances, holm, bootstrap_distances, assert_pool_compatible
from chronos_propagation_baselines import predicted_paths


def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,indent=2),encoding='utf-8')


def stage_a(pilot,output,permutations=19999,bootstrap_reps=399):
    output.mkdir(exist_ok=True,parents=True);start=time.perf_counter()
    analysis_plan={'primary_support':'relative22','supports':list(supports(0)),
        'test_family':'all69 calibrated alternatives x2 baselines x2 metrics =276, pooled Holm; other supports descriptive',
        'independent_validation':'seed20261121+20261122 N40; first seed excluded',
        'prediction_source':'independent same-token null; transformation fixed by forced J and context lag1',
        'MC_control':'T(reference) vs T(null), same statistic as untranslated reference/null',
        'permutations':permutations,'bootstrap_replicates':bootstrap_reps,'seed':2026112301,
        'alternative_difference':'D(A,T(null))-D(A,reference) paired bootstrap; not an unbiased effect'}
    if (output/'plan.json').exists() and load(output/'plan.json')!=analysis_plan:raise ValueError('Stage A plan changed')
    save(output/'plan.json',analysis_plan)
    complete=load(pilot/'pilot_complete.json');frozen=load(pilot/'frozen.json')
    for name,digest in frozen['files'].items():assert sha(pilot/name)==digest
    windows={w['window_id']:w for w in load(pilot/'selection_manifest.json')['windows']}
    cells=[];rng_ids=set();derived_seeds=set();maxerror=0.
    for cell in load(pilot/'cell_plan.json'):
        directory=pilot/'cells'/cell['cell_id']
        assert sha(directory/'complete.json')==complete['complete_sha256'][cell['cell_id']]
        _,r,v=read_complete_cell(directory,cell['scope']);cells.append((cell,r,v))
        for m,_ in v['records']:
            rid=m['metadata']['rng']['stream_id'];rs=m['metadata']['rng']['seed']
            assert rid not in rng_ids and rs not in derived_seeds
            rng_ids.add(rid);derived_seeds.add(rs)
        for row in r['distances']:
            b,t=row['b'],row['token'];g=r['greedy_tokens'][b]
            ref=v['lookup'][(b,'reference',g)][1]['values'];a=v['lookup'][(b,'alternative',t)][1]['values']
            for support,suffix in [('full','post'),('relative22','fixed22')]:
                coords=supports(b)[support];d=distances(ref[:,coords],a[:,coords])
                for metric in ['w1','ed']:
                    maxerror=max(maxerror,abs(d[metric]-row[metric+'_'+suffix])/max(1,abs(d[metric])))
    rows=[];matched=[];perms=[];uncertainty=[];rng=np.random.default_rng(2026112301)
    for wid,w in windows.items():
        repeated=sorted([c for c in cells if c[0]['window_id']==wid],key=lambda c:c[0]['scope']['sampling_seed'])
        if len(repeated)>1:
            assert len(repeated)==3
            for key in repeated[0][2]['lookup']:
                assert_pool_compatible([c[2]['lookup'][key][0] for c in repeated])
            assert all(c[1]['forks']==repeated[0][1]['forks'] for c in repeated)
        designs={f'seed{c[0]["scope"]["sampling_seed"]}':[c] for c in repeated}
        if len(repeated)==3:designs.update(holdout40=repeated[1:],pooled60=repeated)
        for design,chosen in designs.items():
            result=chosen[0][1];iqr=result['context_iqr'];predpoints={};bootpoints={}
            for fork in result['forks']:
                b,g=fork['b'],fork['greedy_token']
                def p(role,token):return np.concatenate([c[2]['lookup'][(b,role,token)][1]['values'].astype(float) for c in chosen])
                r,n=p('reference',g),p('null',g);size=len(r)
                ir=rng.integers(size,size=(bootstrap_reps,size));inn=rng.integers(size,size=(bootstrap_reps,size))
                for t in fork['selected_tokens'][1:]:
                    a=p('alternative',t);jump=a[0,b]-r[0,b]
                    ia=rng.integers(size,size=(bootstrap_reps,size))
                    for support,coords in supports(b).items():
                        raw=distances(a[:,coords],r[:,coords]);null=distances(r[:,coords],n[:,coords])
                        for model in ['persistent','ar1']:
                            prediction=predicted_paths(n,b,jump,w['lag1'],coords,model)
                            fitted=distances(a[:,coords],prediction)
                            old_magnitude=distances(r[:,coords],prediction)
                            co={'window_id':wid,'series':w['series_id'],'dataset':w['dataset_id'],
                                'design':design,'N':size,'b':b,'token':t,'support':support,'model':model,
                                'J_raw':jump,'phi':w['lag1'],'iqr':iqr}
                            for metric in ['w1','ed']:
                                rows.append({**co,'metric':metric,'residual_raw':fitted[metric],'residual_iqr':fitted[metric]/iqr,
                                    'untransformed_raw':raw[metric],'untransformed_iqr':raw[metric]/iqr,
                                    'same_law_MC_raw':null[metric],'same_law_MC_iqr':null[metric]/iqr,
                                    'old_reference_to_prediction_raw':old_magnitude[metric]})
                                predpoints[(b,t,support,model,metric)]=fitted[metric]/iqr
                            if design=='holdout40' and support=='relative22':
                                pp=permutation_distances(a[:,coords]/iqr,prediction/iqr,permutations,rng)
                                for metric in ['w1','ed']:
                                    perms.append({**co,'metric':metric,'p':pp['p_'+metric]})
                                ba=bootstrap_distances(a[:,coords]/iqr,prediction/iqr,ia,inn)
                                bu=bootstrap_distances(a[:,coords]/iqr,r[:,coords]/iqr,ia,ir)
                                bn=bootstrap_distances(r[:,coords]/iqr,n[:,coords]/iqr,ir,inn)
                                for metric in ['w1','ed']:
                                    contrast=ba[metric]-bu[metric];excess=ba[metric]-bn[metric]
                                    uncertainty.append({**co,'metric':metric,
                                        'residual_ci_lo':float(np.quantile(ba[metric],.025)),
                                        'residual_ci_hi':float(np.quantile(ba[metric],.975)),
                                        'paired_residual_minus_untransformed_lo':float(np.quantile(contrast,.025)),
                                        'paired_residual_minus_untransformed_hi':float(np.quantile(contrast,.975)),
                                        'residual_minus_null_lo':float(np.quantile(excess,.025)),
                                        'residual_minus_null_hi':float(np.quantile(excess,.975))})
                                    bootpoints[(b,t,model,metric)]=ba[metric]
                for t in fork['selected_tokens'][1:]:
                    up=2*g-t
                    if t>=g or up not in fork['selected_tokens']:continue
                    for model,metric,support in itertools.product(['persistent','ar1'],['w1','ed'],supports(b)):
                        contrast=predpoints[(b,up,support,model,metric)]-predpoints[(b,t,support,model,metric)]
                        row={'window_id':wid,'series':w['series_id'],'dataset':w['dataset_id'],'design':design,
                            'N':size,'b':b,'down_token':t,'up_token':up,'model':model,'metric':metric,
                            'support':support,'residual_up_minus_down_iqr':contrast}
                        if design=='holdout40' and support=='relative22':
                            bc=bootpoints[(b,up,model,metric)]-bootpoints[(b,t,model,metric)]
                            row.update(lo=float(np.quantile(bc,.025)),hi=float(np.quantile(bc,.975)))
                        matched.append(row)
            print('Direct baselines',w['series_id'],design,flush=True)
    pd.DataFrame(rows).to_csv(output/'direct_baseline_distances.csv',index=False)
    pd.DataFrame(matched).to_csv(output/'matched_baseline_residuals.csv',index=False)
    pf=pd.DataFrame(perms);pf['holm276']=holm(pf.p)
    pf.to_csv(output/'independent_baseline_tests.csv',index=False)
    pd.DataFrame(uncertainty).to_csv(output/'paired_baseline_uncertainty.csv',index=False)
    assert len(pf)==276 and maxerror<1e-10
    save(output/'stage_a_results.json',{'status':'complete','historical_metrics_reproduced':True,
        'max_relative_metric_error':maxerror,'complete_checkpoint_hashes_verified':True,
        'pool_identity_and_rng_checks':True,'distinct_RNG_streams':len(rng_ids),
        'correctness_problem_invalidating_sampling':False,'new_model_draws':0,
        'family_size':len(pf),'rejections_holm':int((pf.holm276<=.05).sum()),
        'source_sha256':sha(__file__),'elapsed_seconds':time.perf_counter()-start,
        'pilot_complete_sha256':sha(pilot/'pilot_complete.json')})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('pilot',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();stage_a(args.pilot.resolve(),args.output.resolve())
