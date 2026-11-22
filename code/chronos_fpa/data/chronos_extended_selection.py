"""Bounded cohort and prospectively named RNG streams, using pilot selectors."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path

from chronos_pilot_selection import choose_pair, eligible_row
from ensemble_store import task_id


def documented_exclusions(root):
    root=Path(root);known={ds:set() for ds in ('m4_daily','ercot','exchange_rate')};evidence={}
    # DictReader preserves the identity fields even in a legacy variable-width CSV.
    for path in sorted((root/'result').rglob('chronos_scan_summary.csv')):
        pairs=set()
        with path.open(encoding='utf-8-sig',newline='') as stream:
            for row in csv.DictReader(stream):
                ds,s=row.get('dataset_name'),row.get('series_id')
                if ds in known and s:
                    known[ds].add(s);pairs.add((ds,s))
        if pairs:evidence[path.relative_to(root).as_posix()]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'studied_identities':sorted(pairs)}
    pilot=root/'result/local_pilot_20261120T184035Z/selection_manifest.json'
    for w in json.loads(pilot.read_text(encoding='utf-8'))['windows']:known[w['dataset_id']].add(w['series_id'])
    evidence[pilot.relative_to(root).as_posix()]={'sha256':hashlib.sha256(pilot.read_bytes()).hexdigest(),'source':'windows only, eligible population is not evidence of prior execution'}
    known['m4_daily'].add('T000001');known['ercot'].add('EAST');known['exchange_rate'].add('currency_3')
    return {ds:sorted(ids) for ds,ids in known.items()},evidence


def select_extended(root,config):
    root=Path(root);excluded,evidence=documented_exclusions(root)
    selected=[];population=[];rejections=[];arrays={};hashes={};shortfalls=[]
    for ds,wanted in config['cohort_counts'].items():
        source=Path('data/raw/chronos_benchmark')/f'autogluon_chronos_datasets__{ds}__train.jsonl'
        digest=hashlib.sha256((root/source).read_bytes()).hexdigest();hashes[source.as_posix()]=digest
        records=[];contexts={};seen=set()
        for rownum,line in enumerate((root/source).open(encoding='utf-8')):
            row=json.loads(line);s=str(row['series_id'])
            try:
                if s in seen:raise ValueError('duplicate_original_series_id')
                seen.add(s);record,context=eligible_row(row,ds,excluded[ds])
                record.update(source_file=source.as_posix(),source_sha256=digest,source_row=rownum)
                records.append(record);contexts[s]=context
            except ValueError as error:rejections.append({'dataset_id':ds,'series_id':s,'reason':str(error)})
        remaining=list(records);chosen=[]
        for round_ in range((wanted+1)//2):
            if len(remaining)<2:
                if remaining:chosen.append({**remaining[0],'stratum':'representative','selection_shortfall':True})
                break
            pair=choose_pair(remaining,ds,config['selection_seed']+round_)
            for w in pair:w['selection_round']=round_
            chosen+=pair;ids={w['series_id'] for w in pair};remaining=[r for r in remaining if r['series_id'] not in ids]
        chosen=chosen[:wanted]
        if len(chosen)<wanted:shortfalls.append({'dataset':ds,'requested':wanted,'available_new_identities':len(chosen)})
        for w in chosen:
            w['window_id']=task_id({k:w[k] for k in ('dataset_id','series_id','forecast_origin','context_sha256','source_sha256')})
            arrays[w['window_id']]=contexts[w['series_id']]
        selected+=chosen
        population +=[{**r,'selection_status':'selected' if any(w['series_id']==r['series_id'] for w in chosen) else 'eligible_not_selected'} for r in records]
    assert len(selected)<=8 and len({(w['dataset_id'],w['series_id']) for w in selected})==len(selected)
    core={'schema':'chronos_extended_batch_v1','config':config,'windows':selected,'source_hashes':hashes,
          'eligible_population':population,'rejections':rejections,'known_studied_series':excluded,
          'exclusion_evidence':evidence,'shortfalls':shortfalls}
    core['grid_revision']=task_id(core)
    return core,arrays


def stream_identity(seed,namespace,label):
    digest=hashlib.sha256(json.dumps([int(seed),namespace,label],separators=(',',':')).encode()).hexdigest()
    return {'stream_id':digest,'seed':int(digest[:16],16)%(2**63),'root_seed':seed,'namespace':namespace,'role':label}


def planned_streams(scope,window_id,validation_seed):
    namespace=task_id({'window_id':window_id,'grid_revision':scope['grid_revision'],'version':'extended_rng_v1'})
    labels=[f'dense_b{b:02d}_slot{s}' for b in range(10) for s in range(8)]
    labels +=[f'dense_b{b:02d}_{role}' for b in range(10) for role in ('null','residual')]
    labels +=[f'direct_t{t:02d}' for t in range(11,16)]+[f'overlap_t{t:02d}' for t in (0,9,10)]
    return namespace,{label:stream_identity(scope['sampling_seed'],namespace,label) for label in labels}
