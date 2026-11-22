"""Offline scientific review of saved complete pilot paths; never runs Chronos.

Writes only to the explicitly named new analysis directory. Original analysis,
ensembles, complete markers and frozen manifests remain read-only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault("MPLBACKEND", "Agg")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code/chronos_fpa"))
import bootstrap  # noqa: E402,F401
import numpy as np
import pandas as pd

from chronos_distances import empirical_w1_by_horizon
from chronos_offline_precision import (
    assert_pool_compatible, bootstrap_distances, counts, distances,
    event_contributions, holm, permutation_distances, pool_designs,
    supports, transform, variance_partition, weighted_w1,
)
from chronos_outcomes import window_outcomes
from chronos_pilot_validation import read_complete_cell


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    def default(x):
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, np.generic):
            return x.item()
        raise TypeError(type(x))
    Path(path).write_text(json.dumps(value, indent=2, default=default), encoding="utf-8")


def csv(out, name, rows):
    frame = pd.DataFrame(rows)
    frame.to_csv(out / (name + ".csv"), index=False)
    return frame


def corr(a, b):
    a, b = pd.Series(np.asarray(a, dtype=float)), pd.Series(np.asarray(b, dtype=float))
    return a.rank().corr(b.rank()) if a.nunique() > 1 and b.nunique() > 1 else np.nan


def interval(x):
    return {"lo": float(np.quantile(x, .025)), "hi": float(np.quantile(x, .975)),
            "sd": float(np.std(x, ddof=1))}


def common(cell):
    p = cell["plan"]
    return {"window_id": p["window_id"], "series": p["scope"]["series_id"],
            "dataset": p["scope"]["dataset_id"], "seed": p["scope"]["sampling_seed"],
            "primary": p["primary"]}


def paths(cell, b, role, token=None):
    if role in {"reference", "null"}:
        token = cell["result"]["greedy_tokens"][b]
    return cell["validation"]["lookup"][(b, role, token)][1]["values"].astype(float)


def read_data(run, out):
    frozen, complete = load(run / "frozen.json"), load(run / "pilot_complete.json")
    for name, sha in frozen["files"].items():
        if digest(run / name) != sha:
            raise ValueError("Frozen input changed: " + name)
    panel = {w["window_id"]: w for w in load(run / "selection_manifest.json")["windows"]}
    cells, streams, seeds = [], set(), set()
    for plan in load(run / "cell_plan.json"):
        directory = run / "cells" / plan["cell_id"]
        if digest(directory / "complete.json") != complete["complete_sha256"][plan["cell_id"]]:
            raise ValueError("Aggregate completed checkpoint changed")
        marker, result, validation = read_complete_cell(directory, plan["scope"])
        for m, _ in validation["records"]:
            stream, seed = m["metadata"]["rng"]["stream_id"], m["metadata"]["rng"]["seed"]
            if stream in streams or seed in seeds:
                raise ValueError("RNG stream or derived seed reused")
            streams.add(stream); seeds.add(seed)
        cells.append({"plan": plan, "result": result, "validation": validation,
                      "window": panel[plan["window_id"]]})
        print("validated", plan["scope"]["series_id"], plan["scope"]["sampling_seed"], flush=True)
    for wid in panel:
        repeated = [c for c in cells if c["plan"]["window_id"] == wid]
        if len(repeated) == 1:
            continue
        first = repeated[0]
        for c in repeated[1:]:
            if c["result"]["forks"] != first["result"]["forks"]:
                raise ValueError("Candidate policy/weights changed across seeds")
        for key in first["validation"]["lookup"]:
            assert_pool_compatible([c["validation"]["lookup"][key][0] for c in repeated])
    provenance = {"analysis_head": load(out / "preservation_before.json")["head"],
                  "analysis_source_sha256": digest(__file__),
                  "primitives_sha256": digest(ROOT / "code/chronos_fpa/analysis/chronos_offline_precision.py"),
                  "pilot_complete_sha256": digest(run / "pilot_complete.json"),
                  "frozen_sha256": digest(run / "frozen.json"), "freeze": frozen,
                  "cells": len(cells), "ensembles": sum(c["validation"]["ensembles"] for c in cells),
                  "paths": sum(c["validation"]["paths"] for c in cells),
                  "unique_rng_streams": len(streams), "unique_derived_seeds": len(seeds),
                  "new_model_draws": 0, "pool_identity_check": "all immutable identity fields except sampling_seed identical",
                  "completed_checkpoint_hashes": complete["complete_sha256"]}
    dump(out / "provenance.json", provenance)
    return cells


def baseline_and_propagation(cells, run, out):
    branches, profiles, nulls, splits, scaling = [], [], [], [], []
    max_metric_error = 0.
    for cell in cells:
        co, result = common(cell), cell["result"]
        iqr = result["context_iqr"]
        for fork in result["forks"]:
            b = fork["b"]
            r, n = paths(cell, b, "reference"), paths(cell, b, "null")
            sn, sr = n[:, b+1:], r[:, b+1:]
            wn = empirical_w1_by_horizon(sr, sn)
            dn = distances(sr, sn)
            nulls.append({**co, "b": b, **dn, "iqr": iqr,
                          "early8_w1": wn[:8].mean(), "late8_w1": wn[-8:].mean()})
            for original in [v for v in result["distances"] if v["b"] == b]:
                token = original["token"]
                a = paths(cell, b, "alternative", token)
                sa = a[:, b+1:]
                w = empirical_w1_by_horizon(sr, sa)
                df, d22 = distances(sr, sa), distances(sr[:, :22], sa[:, :22])
                j = a[0, b] - r[0, b]
                for key, value in (("w1_post", df["w1"]), ("ed_post", df["ed"]),
                                   ("w1_fixed22", d22["w1"]), ("ed_fixed22", d22["ed"])):
                    max_metric_error = max(max_metric_error, abs(value-original[key]) / max(1., abs(value)))
                row = {**co, "b": b, "token": token, "J": j, "iqr": iqr,
                       "w1": df["w1"], "ed": df["ed"], "w1_22": d22["w1"], "ed_22": d22["ed"],
                       "null_w1": dn["w1"], "null_ed": dn["ed"],
                       "q50": original["q50"], "p_sel": original["p_sel"],
                       "entropy_q50": fork["entropy_q50_nats"], "entropy_p_sel": fork["entropy_p_sel_nats"]}
                context = cell["validation"]["records"][0][1]["context"].astype(float)
                min_jump = max(.01*iqr, 1e-12*max(1., np.abs(context).max()))
                mean = sa.mean(axis=0)-sr.mean(axis=0)
                null_mean = sn.mean(axis=0)-sr.mean(axis=0)
                for h in range(len(w)):
                    profiles.append({**co, "b": b, "token": token, "h": h+1, "coordinate": b+h+1,
                        "iqr": iqr, "J": j, "w1": w[h], "null_w1": wn[h], "w1_minus_null": w[h]-wn[h],
                        "delta_mean": mean[h], "null_delta_mean": null_mean[h],
                        "reference_sd": sr[:, h].std(ddof=1),
                        "delta_variance": sa[:, h].var(ddof=1)-sr[:, h].var(ddof=1),
                        "null_delta_variance": sn[:, h].var(ddof=1)-sr[:, h].var(ddof=1),
                        "gain": mean[h]/j if abs(j)>min_jump else np.nan,
                        "gain_eligible": abs(j)>min_jump,
                        "persistent_mean": j, "ar1_mean": j*cell["window"]["lag1"]**(h+1)})
                for name, early, late in (("first8_last8", slice(0, 8), slice(-8, None)),
                                          ("first10_last10", slice(0, 10), slice(-10, None)),
                                          ("relative22_halves", slice(0, 11), slice(11, 22))):
                    splits.append({**co, "b": b, "token": token, "split": name,
                        "alt_increase": w[late].mean()>w[early].mean(),
                        "null_increase": wn[late].mean()>wn[early].mean(),
                        "excess_increase": (w-wn)[late].mean()>(w-wn)[early].mean(),
                        "early_abs_mean": abs(mean[early].mean())/iqr, "late_abs_mean": abs(mean[late].mean())/iqr,
                        "sign_reversal": mean[early].mean()*mean[late].mean()<0,
                        "gain_eligible": abs(j)>min_jump,
                        "early_gain": mean[early].mean()/j if abs(j)>min_jump else np.nan,
                        "late_gain": mean[late].mean()/j if abs(j)>min_jump else np.nan})
                for label, response in (("persistent", np.ones(sa.shape[1])),
                                        ("ar1", cell["window"]["lag1"]**np.arange(1, sa.shape[1]+1))):
                    db = distances(sr[:, :22], (sn+j*response)[:, :22])
                    row[label+"_w1_22"], row[label+"_ed_22"] = db["w1"], db["ed"]
                branches.append(row)
        if co["primary"]:
            context = cell["validation"]["records"][0][1]["context"].astype(float)
            window_rows = [r for r in branches if r["window_id"] == co["window_id"] and r["primary"]]
            for name, denominator in (("protocol_context_iqr", iqr), ("sensitivity_context_std", context.std()),
                                      ("sensitivity_context_range", np.ptp(context)),
                                      ("sensitivity_recent128_iqr", np.quantile(context[-128:], .75)-np.quantile(context[-128:], .25))):
                scaling.append({**co, "normalization": name, "scale": denominator,
                    "median_w1_scaled": np.median([r["w1"] for r in window_rows])/denominator,
                    "median_null_scaled": np.median([r["null_w1"] for r in window_rows])/denominator,
                    "median_ed_scaled": np.median([r["ed"] for r in window_rows])/denominator})
    frame = csv(out, "baseline_branches", branches)
    csv(out, "propagation_profiles", profiles); ns=csv(out, "same_token_nulls", nulls)
    sf=csv(out, "propagation_splits", splits); csv(out, "normalization_sensitivity", scaling)
    original = pd.read_csv(run / "analysis/branches.csv")
    merged = frame.merge(original, on=["window_id", "seed", "b", "token"], suffixes=("", "_old"))
    if len(merged)!=len(frame):
        raise ValueError("Historical CSV identities mismatch")
    csv_errors = {new: float((merged[new]-merged[old]).abs().max()) for new, old in
                  (("w1", "w1_post"), ("ed", "ed_post"), ("w1_22", "w1_fixed22"), ("ed_22", "ed_fixed22"))}
    primary=frame[frame.primary]
    split_counts=[]
    for name, g in sf[sf.primary].groupby("split"):
        split_counts.append({"split": name, "alternatives": len(g), "increasing_alt": int(g.alt_increase.sum()),
            "nulls": len(g.drop_duplicates(["window_id", "b"])),
            "increasing_null": int(g.drop_duplicates(["window_id", "b"]).null_increase.sum()),
            "increasing_excess": int(g.excess_increase.sum())})
    summary={"max_relative_error_vs_saved_raw_reconstruction": max_metric_error,
        "max_absolute_errors_vs_historical_csv": csv_errors,
        "primary_alternatives":len(primary),"primary_nulls":len(ns[ns.primary]),
        "alt_w1_le_null": int((primary.w1<=primary.null_w1).sum()),
        "alt_le_persistent22": int((primary.w1_22<=primary.persistent_w1_22).sum()),
        "alt_le_ar1_22": int((primary.w1_22<=primary.ar1_w1_22).sum()),"split_counts":split_counts,
        "primary_medians":primary.groupby("series")[["w1","ed","null_w1"]].median().reset_index().to_dict("records")}
    dump(out/"baseline_summary.json",summary)
    print("baseline and propagation complete", json.dumps(summary["split_counts"]), flush=True)


def precision(cells, out, reps, permutations, seed):
    designs = pool_designs()
    canonical = ["N20_s0", "N30_s0_s1first10", "N40_s0_s1", "N60_all", "N40_s1_s2"]
    rng = np.random.default_rng(seed)
    estimates, uncertainty, matched, tests, rankrows, selections, bootstrap_ranks = [], [], [], [], [], [], []
    for wid in sorted({c["plan"]["window_id"] for c in cells if not c["plan"]["primary"]}):
        repeated=sorted([c for c in cells if c["plan"]["window_id"]==wid], key=lambda c:common(c)["seed"])
        first=repeated[0]; co={k:v for k,v in common(first).items() if k not in {"seed","primary"}}
        iqr=first["result"]["context_iqr"]
        boots, points = {d:{} for d in canonical}, {d:{} for d in designs}
        jumps={}
        for fork in first["result"]["forks"]:
            b, g = fork["b"], fork["greedy_token"]
            r=np.concatenate([paths(c,b,"reference") for c in repeated])[:,b+1:b+23]/iqr
            n=np.concatenate([paths(c,b,"null") for c in repeated])[:,b+1:b+23]/iqr
            resamples={}
            nullboots={}
            for d in canonical:
                ix=designs[d]; size=len(ix)
                ir=rng.integers(size,size=(reps,size)); inn=rng.integers(size,size=(reps,size))
                resamples[d]=ir
                nullboots[d]=bootstrap_distances(r[ix],n[ix],ir,inn)
                nullpoint=distances(r[ix],n[ix])
                for metric in ("w1","ed","ed_u"):
                    uncertainty.append({**co,"b":b,"token":g,"role":"same_token_null","design":d,"N":size,
                        "metric":metric,"estimate":nullpoint[metric],**interval(nullboots[d][metric])})
            for d, ix in designs.items():
                null=distances(r[ix],n[ix])
                estimates.append({**co,"b":b,"token":g,"role":"same_token_null","design":d,"N":len(ix),**null})
            for token in fork["selected_tokens"][1:]:
                key=(b,token)
                a=np.concatenate([paths(c,b,"alternative",token) for c in repeated])[:,b+1:b+23]/iqr
                jumps[key]=(paths(first,b,"alternative",token)[0,b]-paths(first,b,"reference")[0,b])/iqr
                for d, ix in designs.items():
                    point=distances(r[ix],a[ix]); null=distances(r[ix],n[ix])
                    points[d][key]=point
                    estimates.append({**co,"b":b,"token":token,"role":"alternative","design":d,"N":len(ix),
                        **point,**{"excess_"+m:point[m]-null[m] for m in ("w1","ed","ed_u")}})
                for d in canonical:
                    ix=designs[d]; size=len(ix)
                    ia=rng.integers(size,size=(reps,size))
                    boot=bootstrap_distances(r[ix],a[ix],resamples[d],ia)
                    boots[d][key]=boot
                    for metric in ("w1","ed","ed_u"):
                        ci=interval(boot[metric]); diff=interval(boot[metric]-nullboots[d][metric])
                        uncertainty.append({**co,"b":b,"token":token,"role":"alternative","design":d,"N":size,"metric":metric,
                            "estimate":points[d][key][metric],**ci,
                            "excess_estimate":points[d][key][metric]-distances(r[ix],n[ix])[metric],
                            **{"excess_"+k:v for k,v in diff.items()}})
                p=permutation_distances(r,a,permutations,rng)
                tests.append({**co,"b":b,"token":token,"role":"alternative","N":60,**p})
            tests.append({**co,"b":b,"token":g,"role":"same_token_null","N":60,
                          **permutation_distances(r,n,permutations,rng)})
            # Matched token distances, opposite signs, shared bootstrap reference.
            for down in fork["selected_tokens"][1:]:
                up=2*g-down
                if down>=g or up not in fork["selected_tokens"]:
                    continue
                for d in designs:
                    for metric in ("w1","ed"):
                        row={**co,"b":b,"down_token":down,"up_token":up,"design":d,"N":len(designs[d]),
                             "metric":metric,"contrast_up_minus_down":points[d][(b,up)][metric]-points[d][(b,down)][metric],
                             "down_J":jumps[(b,down)],"up_J":jumps[(b,up)]}
                        if d in canonical:
                            row.update(interval(boots[d][(b,up)][metric]-boots[d][(b,down)][metric]))
                        matched.append(row)
            print("precision", co["series"], "b", b, flush=True)
        keys=sorted(points["N60_all"])
        for d1,d2 in itertools.combinations(designs,2):
            independent=not bool(set(designs[d1]) & set(designs[d2]))
            for metric in ("w1","ed"):
                a=np.array([points[d1][k][metric] for k in keys]); bvals=np.array([points[d2][k][metric] for k in keys])
                for k in (5,10):
                    overlap=len(set(np.argsort(a)[-k:]) & set(np.argsort(bvals)[-k:]))/k
                    rankrows.append({**co,"design1":d1,"design2":d2,"N1":len(designs[d1]),"N2":len(designs[d2]),
                        "independent_draw_sets":independent,"metric":metric,"top_k":k,"overlap_fraction":overlap,
                        "spearman":corr(a,bvals),"median_absolute_difference":np.median(abs(a-bvals))})
        for d in canonical:
            for metric in ("w1","ed"):
                observed=np.array([points[d][k][metric] for k in keys])
                bs=np.stack([boots[d][k][metric] for k in keys],axis=1)
                for rep in range(reps):
                    bootstrap_ranks.append({**co,"design":d,"N":len(designs[d]),"metric":metric,"replicate":rep,
                        "spearman_to_observed":corr(observed,bs[rep]),
                        "top5_overlap":len(set(np.argsort(observed)[-5:]) & set(np.argsort(bs[rep])[-5:]))/5})
        # Freeze seed0 selection, evaluate disjoint seed1+seed2 pool; no selection on validation.
        validation_keys=set()
        for metric in ("w1","ed"):
            order=sorted(keys,key=lambda k:points["N20_s0"][k][metric],reverse=True)
            for k in order[:5]:
                validation_keys.add(k)
                selections.append({**co,"b":k[0],"token":k[1],"metric":metric,
                    "selection_design":"N20_s0","validation_design":"N40_s1_s2",
                    "selected_estimate":points["N20_s0"][k][metric],
                    "validation_estimate":points["N40_s1_s2"][k][metric],
                    "validation_rank":1+sum(points["N40_s1_s2"][j][metric]>points["N40_s1_s2"][k][metric] for j in keys)})
        for b,token in sorted(validation_keys):
            coords=supports(b)["relative22"]
            r=np.concatenate([paths(c,b,"reference") for c in repeated[1:]])[:,coords]/iqr
            a=np.concatenate([paths(c,b,"alternative",token) for c in repeated[1:]])[:,coords]/iqr
            tests.append({**co,"b":b,"token":token,"role":"independent_validation","N":40,
                          **permutation_distances(r,a,permutations,rng)})
    ef=csv(out,"precision_estimates",estimates); uf=csv(out,"precision_uncertainty",uncertainty)
    csv(out,"precision_matched_contrasts",matched); csv(out,"precision_rank_comparisons",rankrows)
    csv(out,"precision_bootstrap_ranks",bootstrap_ranks); csv(out,"precision_holdout_top5",selections)
    tf=pd.DataFrame(tests)
    for metric in ("w1","ed"):
        # Alternatives form one fixed family across the 69 calibrated branches, per metric.
        for role in tf.role.unique():
            mask=tf.role.eq(role)
            tf.loc[mask,"holm_"+metric]=holm(tf.loc[mask,"p_"+metric])
    tf.to_csv(out/"precision_permutation_diagnostics.csv",index=False)
    dump(out/"precision_pool_designs.json",{d:{"indices_in_concatenated_3x20":ix,"N":len(ix),
        "draw_identity":"per role: ordered seed stream + row; same row indices denote different draws in different roles"} for d,ix in designs.items()})
    print("precision complete",len(ef),"estimates",len(uf),"intervals",flush=True)


def morphology(cells,out):
    rows=[]
    for cell in cells:
        co=common(cell); iqr=cell["result"]["context_iqr"]
        for fork in cell["result"]["forks"]:
            b=fork["b"]
            r,n=paths(cell,b,"reference"),paths(cell,b,"null")
            for support, coords in supports(b).items():
                for mode in ("raw","centered","differenced"):
                    sr,sn=transform(r[:,coords],mode),transform(n[:,coords],mode)
                    null=distances(sr,sn)
                    for token in fork["selected_tokens"][1:]:
                        a=paths(cell,b,"alternative",token)
                        sa=transform(a[:,coords],mode)
                        d=distances(sr,sa)
                        rows.append({**co,"b":b,"token":token,"support":support,"transform":mode,
                            "start":int(coords[0]),"end":int(coords[-1]),"dimensions":sr.shape[1],"iqr":iqr,
                            **d,**{"null_"+k:v for k,v in null.items()},
                            "mean_profile_rms":np.sqrt(np.mean((sa.mean(axis=0)-sr.mean(axis=0))**2)),
                            "mean_profile_abs":np.abs(sa.mean(axis=0)-sr.mean(axis=0)).mean(),
                            "null_mean_profile_rms":np.sqrt(np.mean((sn.mean(axis=0)-sr.mean(axis=0))**2))})
    frame=csv(out,"temporal_support_distances",rows)
    rankings=[]
    for (wid,series,support,mode),g in frame[frame.primary].groupby(["window_id","series","support","transform"]):
        rankings.append({"window_id":wid,"series":series,"support":support,"transform":mode,
            "comparison":"W1_vs_ED","spearman":corr(g.w1,g.ed),"branches":len(g),
            "top5_overlap":len(set(g.nlargest(5,"w1").token.astype(str)+"_"+g.nlargest(5,"w1").b.astype(str)) &
                               set(g.nlargest(5,"ed").token.astype(str)+"_"+g.nlargest(5,"ed").b.astype(str)))/5})
    for (wid,series,mode),g in frame[frame.primary].groupby(["window_id","series","transform"]):
        for metric in ("w1","ed"):
            pivot=g.pivot(index=["b","token"],columns="support",values=metric)
            for s1,s2 in itertools.combinations(pivot.columns,2):
                rankings.append({"window_id":wid,"series":series,"transform":mode,
                    "comparison":metric+":"+s1+"_vs_"+s2,"spearman":corr(pivot[s1],pivot[s2]),"branches":len(pivot)})
    csv(out,"temporal_rank_comparisons",rankings)
    print("morphology complete",len(frame),flush=True)


OUTCOMES=("terminal_value","terminal_signed_delta","terminal_abs_delta", "final8_mean_value", "final8_mean_signed_delta", "final8_mean_abs_delta")


def continuous(paths,greedy):
    delta=paths-greedy
    return np.column_stack((paths[:,31],delta[:,31],abs(delta[:,31]),paths[:,24:].mean(axis=1),
                            delta[:,24:].mean(axis=1),abs(delta[:,24:]).mean(axis=1)))


def cpd_and_variance(cells,out,reps,seed):
    rng=np.random.default_rng(seed+1)
    drift,overlap,local,contributions,varrows,groupvar,identity_rows,event_curves=[],[],[],[],[],[],[],[]
    max_identity_error=0.
    for cell in cells:
        co=common(cell); result=cell["result"]; greedy=np.array(result["greedy_values"],dtype=float); iqr=result["context_iqr"]
        lookup=cell["validation"]["lookup"]
        # All object resampling is shared wherever that object is reused in a CPD contrast.
        objects={}
        for key,(manifest,arrays) in lookup.items():
            p=arrays["values"].astype(float); n=len(p)
            ix=rng.integers(n,size=(reps,n)); bw=counts(ix,n)
            objects[key]={"x":continuous(p,greedy),"w":np.ones(n)/n,"bw":bw,
                          "e":window_outcomes(p,greedy,iqr)["events"].reshape(n,10),"paths":p}
        def mixture(keys,weights):
            os_=[objects[k] for k in keys]
            return {"x":np.concatenate([o["x"] for o in os_]),
                    "w":np.concatenate([o["w"]*w for o,w in zip(os_,weights)]),
                    "bw":np.concatenate([o["bw"]*w for o,w in zip(os_,weights)],axis=1),
                    "keys":keys,"weights":weights}
        distributions=[]
        for t in range(16):
            if t<10:
                fork=result["forks"][t]; g=fork["greedy_token"]
                keys=[(t,"reference" if token==g else "alternative",token) for token in fork["selected_tokens"]]
                weights=list(fork["selected_weights"])
                if fork["residual_mass"]>0:
                    keys.append((t,"residual",None));weights.append(fork["residual_mass"])
            else:
                keys=[(9,"reference",result["greedy_tokens"][9])] if t==10 else [(t,"direct_cpd",None)]
                weights=[1.]
            distributions.append(mixture(keys,weights))
            groups=[objects[k]["e"] for k in keys]
            means=np.stack([g.mean(axis=0) for g in groups]);p=np.array(weights)@means
            variance=sum(w*w*g.var(axis=0,ddof=1)/len(g) for w,g in zip(weights,groups))
            radius=np.sqrt(np.log(40)/2*sum(w*w/len(g) for w,g in zip(weights,groups)))
            for e in range(10):
                event_curves.append({**co,"position":t,"event":e,"probability":p[e],"mc_se":np.sqrt(variance[e]),
                    "hoeffding_radius":radius,"method":"mixture" if t<10 else "reuse20" if t==10 else "direct60"})
        def comparison(a,b,metric):
            point=weighted_w1(a["x"][:,metric],a["w"],b["x"][:,metric],b["w"])
            boot=weighted_w1(a["x"][:,metric],a["bw"],b["x"][:,metric],b["bw"])
            return {"w1_raw":float(point),"w1_iqr":float(point/iqr),
                    **{"w1_iqr_"+k:v/iqr for k,v in interval(boot).items()}}
        for t in range(16):
            for metric,name in enumerate(OUTCOMES):
                for label,other in (("cumulative",0),("adjacent",t-1)):
                    if other<0:
                        continue
                    drift.append({**co,"kind":label,"from_position":other,"to_position":t,"outcome":name,
                        "method_boundary":other==10 and t==11,**comparison(distributions[other],distributions[t],metric)})
        for t in (0,9,10):
            direct=mixture([(t,"overlap_direct",None)],[1.])
            for metric,name in enumerate(OUTCOMES):
                overlap.append({**co,"position":t,"outcome":name,**comparison(distributions[t],direct,metric)})
        for fork in result["forks"]:
            t,g=fork["b"],fork["greedy_token"]
            d=distributions[t]; keys,weights=d["keys"],d["weights"]
            groups=[objects[k]["e"] for k in keys]
            lhs,contrib=event_contributions(groups,weights)
            max_identity_error=max(max_identity_error,float(abs(lhs-contrib.sum(axis=0)).max()))
            bootmeans=np.stack([objects[k]["bw"]@objects[k]["e"] for k in keys],axis=1)
            bootc=np.asarray(weights)[None,1:,None]*(bootmeans[:,1:]-bootmeans[:,:1])
            for e in range(10):
                c=contrib[:,e];totalabs=abs(c).sum(); net=c.sum()
                netboot=bootc[:,:,e].sum(axis=1)
                ci=interval(netboot)
                local.append({**co,"b":t,"event":e,"local_mix_minus_greedy":lhs[e],
                    "next_independent_estimate_minus_greedy":sum(w*objects[k]["e"][:,e].mean() for k,w in zip(distributions[t+1]["keys"],distributions[t+1]["weights"]))-groups[0][:,e].mean(),
                    "sum_abs_contributions":totalabs,"cancellation":1-abs(net)/totalabs if totalabs else np.nan,
                    "max_abs_contribution_share":abs(c).max()/totalabs if totalabs else np.nan,
                    "residual_contribution":c[-1] if keys[-1][1]=="residual" else 0.,
                    "identity_error":lhs[e]-net,**{"net_"+k:v for k,v in ci.items()}})
                for j,key in enumerate(keys[1:]):
                    contributions.append({**co,"b":t,"event":e,"role":key[1],"token":key[2],"q50_group_weight":weights[j+1],
                                          "signed_contribution":c[j],**interval(bootc[:,j,e])})
            ref=mixture([keys[0]],[1.])
            # This is the same theoretical next-prefix law but an independently constructed mixture at b+1.
            # At b9, next is literally reused; paired bootstrap gives exactly zero discrepancy.
            for metric,name in enumerate(OUTCOMES):
                identity_rows.append({**co,"b":t,"outcome":name,"literal_reuse":t==9,
                                      **comparison(ref,distributions[t+1],metric)})
            groups_paths=[objects[k]["paths"] for k in keys]
            variance=variance_partition(groups_paths,weights)
            means=np.stack([p.mean(axis=0) for p in groups_paths]);grand=np.array(weights)@means
            for h in range(t,32):
                varrows.append({**co,"b":t,"coordinate":h,"strict_post_fork":h>t,"iqr":iqr,
                    "entropy_q50":fork["entropy_q50_nats"],"entropy_p_sel":fork["entropy_p_sel_nats"],
                    **{k:v[h] for k,v in variance.items()}})
                for j,key in enumerate(keys):
                    groupvar.append({**co,"b":t,"coordinate":h,"role":key[1],"token":key[2],"q50_group_weight":weights[j],
                        "numerical_J_mean":means[j,t]-means[0,t],
                        "within_contribution":weights[j]*groups_paths[j][:,h].var(ddof=1),
                        "between_plugin_contribution":weights[j]*(means[j,h]-grand[h])**2})
        print("CPD/variance",co["series"],co["seed"],flush=True)
    csv(out,"continuous_cpd_drift",drift);csv(out,"continuous_direct_overlap",overlap)
    csv(out,"binary_event_curves",event_curves);csv(out,"local_cancellation",local)
    csv(out,"local_signed_contributions",contributions);csv(out,"independent_prefix_identity",identity_rows)
    vf=csv(out,"future_variance_partition",varrows);csv(out,"variance_group_contributions",groupvar)
    vr=[]
    for (wid,series),g in vf[vf.primary & vf.strict_post_fork & (vf.coordinate>=24)].groupby(["window_id","series"]):
        fork=g.groupby("b").mean(numeric_only=True)
        fraction=fork.between_corrected/fork.total_corrected
        for predictor in ("entropy_q50","entropy_p_sel"):
            vr.append({"window_id":wid,"series":series,"predictor":predictor,
                "spearman_final8_corrected_between_fraction":corr(fork[predictor],fraction),"forks":len(fork)})
    csv(out,"variance_entropy_associations",vr)
    dump(out/"cpd_checks.json",{"max_empirical_identity_error":max_identity_error,"negative_between_not_clipped":True,
        "bootstrap":"whole paths within independent groups; same object resampled identically on reuse; q50 weights fixed"})


def plots(out):
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    e=pd.read_csv(out/"precision_estimates.csv"); u=pd.read_csv(out/"precision_uncertainty.csv")
    p=pd.read_csv(out/"propagation_profiles.csv"); d=pd.read_csv(out/"continuous_cpd_drift.csv")
    with PdfPages(out/"OFFLINE_REVIEW_FIGURES.pdf") as pdf:
        fig,axes=plt.subplots(2,2,figsize=(12,8))
        for i,series in enumerate(e.series.unique()):
            for j,metric in enumerate(("w1","ed")):
                ax=axes[i,j]
                v=e[(e.series==series)&e.role.eq("alternative")]
                ns=v.groupby("N")[metric].median();null=e[(e.series==series)&e.role.eq("same_token_null")].groupby("N")[metric].median()
                ax.plot(ns.index,ns,"o-",label="alternative median, dependent pools")
                ax.plot(null.index,null,"o--",label="same-token null median")
                unc=u[(u.series==series)&u.metric.eq(metric)&u.role.eq("alternative")].copy();unc["width"]=unc.hi-unc.lo
                width=unc.groupby("N").width.median();ax.plot(width.index,width,"x-",label="median pointwise bootstrap width")
                ax.set(title=f"{series}: {metric.upper()} / context IQR",xlabel="saved draws per law")
                ax.legend(fontsize=7)
        fig.tight_layout();pdf.savefig(fig);plt.close(fig)
        fig,axes=plt.subplots(3,2,figsize=(12,10))
        for ax,(series,g) in zip(axes.flat,p[p.primary].groupby("series",sort=False)):
            g=g.copy()
            for c in ("w1","null_w1","reference_sd"):
                g[c]=g[c]/g.iqr
            med=g.groupby("h")[["w1","null_w1","reference_sd"]].median()
            for c in med:
                ax.plot(med.index,med[c],label=c)
            ax.set(title=series,xlabel="strict relative horizon; composition changes after22",ylabel="context IQR units")
            ax.legend(fontsize=7)
        fig.tight_layout();pdf.savefig(fig);plt.close(fig)
        fig,axes=plt.subplots(3,2,figsize=(12,10))
        for ax,(series,g) in zip(axes.flat,d[d.primary & d.kind.eq("cumulative") & d.outcome.eq("terminal_value")].groupby("series",sort=False)):
            ax.plot(g.to_position,g.w1_iqr,"o-",label="P0 vs Pt terminal W1")
            ax.fill_between(g.to_position,g.w1_iqr_lo,g.w1_iqr_hi,alpha=.2,label="pointwise finite-pool bootstrap")
            ax.axvline(10.5,ls="--",color="gray");ax.set(title=series,xlabel="prefix t",ylabel="W1 / context IQR")
            ax.legend(fontsize=7)
        fig.tight_layout();pdf.savefig(fig);plt.close(fig)


def review_tables(cells,out):
    """Compact review tables; all pooled/selected dependencies remain labeled."""
    estimates=pd.read_csv(out/"precision_estimates.csv")
    uncertainty=pd.read_csv(out/"precision_uncertainty.csv")
    uncertainty["width"]=uncertainty.hi-uncertainty.lo
    canonical=["N20_s0","N30_s0_s1first10","N40_s0_s1","N60_all"]
    summary=[]
    for (series,role,n),g in estimates.groupby(["series","role","N"]):
        for metric in ("w1","ed","ed_u"):
            u=uncertainty[(uncertainty.series==series)&(uncertainty.role==role)&(uncertainty.N==n)&
                          uncertainty.metric.eq(metric)&uncertainty.design.isin(canonical)]
            summary.append({"series":series,"role":role,"N":n,"metric":metric,
                "median_over_available_pool_estimates":g[metric].median(),
                "pool_estimate_q10":g[metric].quantile(.1),"pool_estimate_q90":g[metric].quantile(.9),
                "median_bootstrap_width_canonical_pool":u.width.median(),
                "median_bootstrap_sd_canonical_pool":u.sd.median(),
                "pool_estimates_dependent":True,"pool_combinations":g.design.nunique()})
    csv(out,"precision_review_summary",summary)
    classifications=[]
    for (series,metric),g in uncertainty[uncertainty.role.eq("alternative")&uncertainty.design.isin(canonical)].groupby(["series","metric"]):
        for n,v in g.groupby("N"):
            classifications.append({"series":series,"metric":metric,"N":n,"branches":len(v),
                "positive_descriptive_excess":int((v.excess_estimate>0).sum()),
                "pointwise_excess_bootstrap_lo_positive":int((v.excess_lo>0).sum()),
                "pointwise_excess_bootstrap_hi_negative":int((v.excess_hi<0).sum()),
                "unresolved_by_descriptive_interval":int(((v.excess_lo<=0)&(v.excess_hi>=0)).sum()),
                "interpretation":"conditional empirical bootstrap, not significance or equivalence"})
    alt=estimates[estimates.role.eq("alternative")]
    for series,g in alt.groupby("series"):
        for metric in ("w1","ed"):
            pivot=g.pivot(index=["b","token"],columns="design",values="excess_"+metric)
            classifications.append({"series":series,"metric":metric,"N":20,"branches":len(pivot),
                "positive_all_three_independent_seeds":int((pivot[["N20_s0","N20_s1","N20_s2"]]>0).all(axis=1).sum()),
                "negative_all_three_independent_seeds":int((pivot[["N20_s0","N20_s1","N20_s2"]]<=0).all(axis=1).sum()),
                "interpretation":"same-token excess sign consistency, not independent series"})
    csv(out,"precision_conclusion_stability",classifications)
    matched=pd.read_csv(out/"precision_matched_contrasts.csv")
    mr=[]
    for (series,metric),g in matched.groupby(["series","metric"]):
        pivot=g.pivot(index=["b","down_token","up_token"],columns="design",values="contrast_up_minus_down")
        for a,b in (("N20_s0","N20_s1"),("N20_s0","N20_s2"),("N20_s1","N20_s2"),
                    ("N30_s0_s1first10","N30_disjointB"),("N20_s0","N40_s1_s2")):
            mr.append({"series":series,"metric":metric,"design1":a,"design2":b,"matched_pairs":len(pivot),
                "same_contrast_sign":int((pivot[a]*pivot[b]>0).sum()),"contrast_spearman":corr(pivot[a],pivot[b]),
                "median_abs_contrast_difference":np.median(abs(pivot[a]-pivot[b]))})
    csv(out,"matched_contrast_stability",mr)
    # Seed0 chose these cases; only other streams supply the holdout estimates.
    cases=[("SOUTHERN",0,2229),("T000063",3,2152)]
    case_rows=[]
    for series,b,token in cases:
        repeated=sorted([c for c in cells if common(c)["series"]==series],key=lambda c:common(c)["seed"])
        iqr=repeated[0]["result"]["context_iqr"]
        for support,coords in supports(b).items():
            for mode in ("raw","centered","differenced"):
                r,a,n=[transform(np.concatenate([paths(c,b,role,token) for c in repeated[1:]])[:,coords],mode)/iqr
                       for role in ("reference","alternative","null")]
                case_rows.append({"series":series,"b":b,"token":token,"support":support,"transform":mode,
                    "N":40,"selection":"seed0 top5; holdout seeds1+2","J_iqr":
                    (paths(repeated[0],b,"alternative",token)[0,b]-paths(repeated[0],b,"reference")[0,b])/iqr,
                    **distances(r,a),**{"null_"+k:v for k,v in distances(r,n).items()},
                    "mean_profile_rms_iqr":np.sqrt(np.mean((r.mean(axis=0)-a.mean(axis=0))**2))})
    csv(out,"independent_case_supports",case_rows)
    # Bounded binary contrast uncertainty: reference coefficient is -(1-w_g).
    local=pd.read_csv(out/"local_cancellation.csv");local_bounds=[]
    boundaries=[];group_relations=[]
    for cell in cells:
        co=common(cell);result=cell["result"]
        greedy=np.array(result["greedy_values"],dtype=float);iqr=result["context_iqr"]
        for fork in result["forks"]:
            b=fork["b"];groups,weights=cell["validation"]["groups_by_position"][b]
            proxy=(1-weights[0])**2/len(groups[0]["values"])+sum(w*w/len(g["values"]) for w,g in zip(weights[1:],groups[1:]))
            radius=np.sqrt(np.log(40)/2*proxy)
            l=local[(local.window_id==co["window_id"])&(local.seed==co["seed"])&(local.b==b)]
            for _,row in l.iterrows():
                local_bounds.append({**co,"b":b,"event":row.event,"net":row.local_mix_minus_greedy,
                    "sum_abs_contributions":row.sum_abs_contributions,"cancellation":row.cancellation,
                    "hoeffding_radius":radius,"pointwise_bound_excludes_zero":abs(row.local_mix_minus_greedy)>radius})
            means=np.stack([g["values"].astype(float).mean(axis=0) for g in groups])
            for j,g in enumerate(groups[1:],1):
                delta=means[j]-means[0]
                is_residual=fork["residual_mass"]>0 and j==len(groups)-1
                group_relations.append({**co,"b":b,"role":"residual" if is_residual else "alternative",
                    "q50_group_weight":weights[j],"J_mean":delta[b],"iqr":iqr,
                    "final8_mean_response":delta[24:].mean(),
                    "final8_mean_squared_response":np.mean(delta[24:]**2),
                    "next_token_singleton":not is_residual})
        # At fixed outcome, compare P10 with P11 full60 and three disjoint N20 blocks.
        ref=paths(cell,9,"reference")
        direct=paths(cell,11,"direct_cpd")
        for name,ix in (("N60_full",np.arange(60)),("N20_block0",np.arange(20)),
                        ("N20_block1",np.arange(20,40)),("N20_block2",np.arange(40,60))):
            a,bv=continuous(ref,greedy),continuous(direct[ix],greedy)
            for j,outcome in enumerate(OUTCOMES):
                boundaries.append({**co,"outcome":outcome,"P11_subset":name,"P10_N":20,"P11_N":len(ix),
                    "w1_iqr":float(weighted_w1(a[:,j],np.ones(20)/20,bv[:,j],np.ones(len(ix))/len(ix))/iqr),
                    "interpretation":"same saved P11 law; blocks disjoint, shared P10 reference"})
    csv(out,"local_contribution_bounds",local_bounds);csv(out,"cpd_boundary_subsampling",boundaries)
    gr=csv(out,"group_response_predictors",group_relations)
    assoc=[]
    for series,g in gr[gr.primary&gr.next_token_singleton].groupby("series"):
        for pred in ("q50_group_weight","abs_J","signed_J"):
            x=g.q50_group_weight if pred=="q50_group_weight" else abs(g.J_mean) if pred=="abs_J" else g.J_mean
            assoc.append({"series":series,"predictor":pred,"response":"final8_mean_squared_response",
                "spearman":corr(x,g.final8_mean_squared_response),"groups":len(g),"independent_series":1})
    csv(out,"group_response_associations",assoc)
    print("review tables complete",flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run",type=Path);parser.add_argument("output",type=Path)
    parser.add_argument("--stage",choices=["all","baseline","precision","morphology","cpd","plots","review"],default="all")
    args=parser.parse_args();run,out=args.run.resolve(),args.output.resolve()
    if not out.is_relative_to(run) or out==run or out.name=="analysis" or not (out/"analysis_plan.json").is_file():
        raise ValueError("Require a new named pilot subdirectory with a predefined analysis_plan.json")
    plan=load(out/"analysis_plan.json");start=time.perf_counter()
    if args.stage!="plots":
        cells=read_data(run,out)
        if args.stage in {"all","baseline"}: baseline_and_propagation(cells,run,out)
        if args.stage in {"all","precision"}: precision(cells,out,plan["bootstrap_replicates"],plan["permutations"],plan["seed"])
        if args.stage in {"all","morphology"}: morphology(cells,out)
        if args.stage in {"all","cpd"}: cpd_and_variance(cells,out,plan["bootstrap_replicates"],plan["seed"])
        if args.stage in {"all","review"}: review_tables(cells,out)
    if args.stage in {"all","plots"}: plots(out)
    dump(out/("execution_"+args.stage+".json"),{"status":"complete","elapsed_seconds":time.perf_counter()-start,
        "utc":datetime.now(timezone.utc).isoformat(),"analysis_script_sha256":digest(__file__),"new_model_draws":0})
    print("offline stage complete",args.stage,flush=True)


if __name__=="__main__":
    main()
