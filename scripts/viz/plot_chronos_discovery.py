"""Standalone scientific figures for the bounded discovery iteration."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'code/chronos_fpa'),str(ROOT/'scripts/runs')]
import bootstrap  # noqa: E402,F401
from run_chronos_local_pilot import load,digest
from run_chronos_discovery import verify_extra


def short(dataset):return 'AUS' if 'australian' in dataset else 'LON'


def render(out):
    analysis=out/'analysis';windows={w['window_id']:w for w in load(out/'selection_manifest.json')['windows']}
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':120})
    pages=0
    def finish(pdf,fig,title,note):
        nonlocal pages
        fig.suptitle(title,fontsize=13);fig.text(.04,.018,note,fontsize=8);fig.tight_layout(rect=(.02,.055,.99,.94));pdf.savefig(fig)
        figures=analysis/'figures';figures.mkdir(exist_ok=True)
        fig.savefig(figures/f'page{pages+1:02d}.png')
        plt.close(fig);pages+=1
    path=analysis/'FPA_EXPLORATORY_FINDINGS.pdf'
    with PdfPages(path) as pdf:
        rank=pd.read_csv(analysis/'conventional_uncertainty_ranking.csv');r=rank[(rank.scope=='new_cohort')&(rank.point_forecast=='natural_mean')].sort_values('neaurc')
        point=pd.read_csv(analysis/'conventional_comparison_by_window.csv');point=point[point.point_forecast=='natural_mean']
        fig,axes=plt.subplots(1,3,figsize=(14,6),gridspec_kw={'width_ratios':[1.7,1,1]})
        axes[0].barh(r.indicator,r.neaurc);axes[0].axvline(1,color='black',ls='--');axes[0].set_xlabel('NEAURC (lower better; expected random=1)')
        for ax,indicator,title in zip(axes[1:],['interval80_iqr','dense_FPA_W1'],['Natural interval width','Dense FPA conditional separation']):
            for dataset,d in point.groupby('dataset'):
                ax.scatter(d[indicator],d.mase,label=short(dataset))
                for row in d.to_dict('records'):ax.annotate(row['series'],(row[indicator],row['mase']),fontsize=7)
            ax.set_xlabel(title);ax.set_ylabel('Forecast MASE');ax.legend()
        finish(pdf,fig,'Forecast-error ranking on six new sources',
            'Same natural-mean H32 forecast/target for every indicator. Small, dependent cohort; SGA = pinned-code H32/3xK20 adaptation. No generalization claim.')

        v=pd.read_csv(analysis/'fresh_N120_validation.csv');fig,axes=plt.subplots(1,2,figsize=(13,7),gridspec_kw={'width_ratios':[1.4,1]})
        labels=[]
        for index,row in enumerate(v.to_dict('records')):
            labels.append(f'{short(row["dataset"])} {row["series"]} b{row["b"]}/{row["token"]}\n{row["event_name"]} [{row["selection"]}]')
            axes[0].plot([row['fresh_gap_lo'],row['fresh_gap_hi']],[index,index],color='C0')
            axes[0].scatter(row['fresh_gap'],index,color='C0',marker='o' if row['holm']<=.05 else 'x')
            axes[0].scatter(row['block0_gap'],index,color='grey',marker='.',label='block0' if index==0 else None)
            axes[0].scatter(row['holdout40_gap'],index,color='C1',marker='s',label='holdout40' if index==0 else None)
        axes[0].set_yticks(range(len(labels)),labels);axes[0].axvline(0,color='black',ls='--');axes[0].set_xlabel('Frozen event probability difference A - reference');axes[0].legend()
        row=v.iloc[int(np.argmax(abs(v.fresh_gap)))];wid=row.window_id;_,snapshot=verify_extra(out,wid,'fresh_validation',32)
        lookup={m['task_id']:a for m,a in snapshot['records']};a=lookup[row.alternative_object_id];ref=lookup[row.reference_object_id];scale=windows[wid]['context_iqr'];c=a['context'];x=np.arange(32)
        for values,color,label in [(ref['values'],'C0','reference'),(a['values'],'C3','forced alternative')]:
            z=(values-c[-1])/scale;axes[1].plot(x,z.mean(0),color=color,label=label)
            axes[1].fill_between(x,np.quantile(z,.1,axis=0),np.quantile(z,.9,axis=0),color=color,alpha=.15)
            axes[1].plot(x,z[:5].T,color=color,alpha=.12,lw=.6)
        axes[1].axvline(row.b,color='black',ls='--');axes[1].set_title(f'{short(row.dataset)} {row.series}, b{row.b}/{row.token}\nlargest fixed-event contrast')
        axes[1].set_xlabel('Absolute H32 coordinate');axes[1].set_ylabel('(value - last context) / IQR');axes[1].legend()
        finish(pdf,fig,'Independent N120 consequences and representative trajectories',
            'Blue intervals: pointwise whole-path bootstrap; corrected tests are Holm8 (filled dots). Natural probability is not forced sample frequency.')

        d=pd.read_csv(analysis/'discovery_mass_coverage.csv');d=d[d.budget==40];d['source']=[short(ds)+' '+s for ds,s in zip(d.dataset,d.series)]
        fig,axes=plt.subplots(1,2,figsize=(13,7))
        for ax,column,title in zip(axes,['reference_recall','reference_observed_mass_covered'],['Fraction of observed scenario groups','Fraction of observed reference probability mass']):
            pivot=d.pivot(index='method',columns='source',values=column);im=ax.imshow(pivot,vmin=0,vmax=1,cmap='viridis',aspect='auto')
            ax.set_xticks(range(len(pivot.columns)),pivot.columns,rotation=60,ha='right');ax.set_yticks(range(len(pivot.index)),pivot.index);ax.set_title(title);fig.colorbar(im,ax=ax,shrink=.7)
        finish(pdf,fig,'Discovery at 40 paths per method against independent natural N120',
            'Exact offline subsets of observed tokens, held-out block1+2. Coarse context-defined groups, not proven trajectory modes. The reference is finite, not an oracle.')

        e=pd.read_csv(analysis/'exposure_by_lead_verified.csv');naive=pd.read_csv(analysis/'seasonal_naive_exposure_control.csv')
        fig,axes=plt.subplots(2,2,figsize=(13,7))
        for column,status in enumerate(['in_domain','zero_shot']):
            for wid,w in windows.items():
                if w['documented_pretraining_status']!=status:continue
                g=e[e.window_id==wid];n=naive[naive.window_id==wid];label=f'{w["series_id"]}, end offset {w["offset_from_end"]}'
                axes[0,column].plot(g.lead,g.error_iqr,label=label);axes[1,column].plot(n.lead,n.seasonal_naive_error_iqr,label=label)
            axes[0,column].set_title('London: documented in-domain' if status=='in_domain' else 'Australia: documented zero-shot')
            axes[0,column].set_ylabel('Chronos absolute error / context IQR');axes[1,column].set_ylabel('Seasonal-naive absolute error / IQR');axes[1,column].set_xlabel('Same forecast lead');axes[0,column].legend(fontsize=7)
        axes[0,0].axvline(16.5,color='grey',ls='--');axes[1,0].axvline(16.5,color='grey',ls='--')
        finish(pdf,fig,'Exposure and held-out evaluation at equal forecast leads',
            'London offsets80/64/32: potential32, potential16+heldout16, heldout32. Different source series/aggregation/regimes remain confounders; no memorization inference.')

        curves=pd.read_csv(analysis/'cpd_H64_event_curves.csv');trans=pd.read_csv(analysis/'cpd_H64_validation.csv')
        fig,axes=plt.subplots(3,2,figsize=(12,10))
        for index,wid in enumerate(load(out/'cpd_windows.json')['windows']):
            selected=load(out/'cpd_selections'/(wid+'.json'));event=selected['transitions'][0]['event'];g=curves[(curves.window_id==wid)&(curves.phase=='pool60')&(curves.event==event)].sort_values('prefix')
            axes[index,0].plot(g.prefix,g.probability);axes[index,0].fill_between(g.prefix.to_numpy(float),g.wilson_lo.to_numpy(float),g.wilson_hi.to_numpy(float),alpha=.2)
            axes[index,0].set_ylim(-.02,1.02);axes[index,0].set_title(f'{short(windows[wid]["dataset_id"])} {windows[wid]["series_id"]}: {g.event_name.iloc[0]}');axes[index,0].set_xlabel('Greedy prefix length');axes[index,0].set_ylabel('Fixed absolute future event probability')
            selected_rows=trans[trans.window_id==wid].to_dict('records')
            for j,r in enumerate(selected_rows):
                axes[index,0].axvspan(r['left'],r['right'],alpha=.12,color='grey' if r['selection']=='random_control' else 'C3')
                axes[index,1].plot([r['fresh_gap_lo'],r['fresh_gap_hi']],[j,j],color='C0');axes[index,1].scatter(r['fresh120_gap'],j,color='C0',marker='o' if r['holm']<=.05 else 'x');axes[index,1].scatter(r['holdout40_gap'],j,color='C1',marker='s')
            axes[index,1].set_yticks(range(len(selected_rows)),[f'P{r["left"]}->P{r["right"]} {r["selection"]}\n{r["event_name"]}' for r in selected_rows]);axes[index,1].axvline(0,color='black',ls='--');axes[index,1].set_xlabel('Probability difference: holdout40(square), fresh120(blue)')
        finish(pdf,fig,'CPD H64: direct prefixes P0..P30 and targeted validation',
            'Every curve uses the same absolute H64 outcome. Bands are pointwise Wilson; filled validation dots reject after Holm9. Conditional shifts are not structural change points.')

        profiles=pd.read_csv(out/'whitebox/representation_profiles.csv');cases=list(dict.fromkeys(profiles.case));fig,axes=plt.subplots(len(cases),3,figsize=(13,3*len(cases)),squeeze=False)
        for i,case in enumerate(cases):
            for j,family in enumerate(['hidden_RMS','self_attention_L1','cross_attention_L1']):
                g=profiles[(profiles.case==case)&(profiles.family==family)]
                for layer,l in g.groupby('layer'):axes[i,j].plot(l.relative_query,l.distance,label=f'layer{layer}',lw=.9)
                axes[i,j].axvline(1,color='grey',ls='--');axes[i,j].set_title(case+' / '+family);axes[i,j].set_xlabel('Query index minus forced-token position');axes[i,j].legend(fontsize=6,ncol=2)
        finish(pdf,fig,'White-box: paired-path differences after forced and same-token branches',
            'Query b is before seeing the forced token; b+1 is first post-token query. One path/pair, independent stochastic continuations: descriptive, not a causal mechanism.')
        fig,axes=plt.subplots(len(cases),1,figsize=(13,2.6*len(cases)),squeeze=False)
        plan={c['name']:c for c in load(out/'whitebox_plan.json')['cases']}
        for i,case in enumerate(cases):
            with np.load(out/'whitebox'/(case+'_pass1.npz')) as a:
                key=max([k for k in a.files if k.startswith('cross_attention_')],key=lambda k:int(k.rsplit('_',1)[1]));value=a[key]
                pattern=np.mean(abs(value[1]-value[0]),axis=0)
            im=axes[i,0].imshow(pattern,aspect='auto',origin='lower',cmap='magma');axes[i,0].axhline(plan[case]['b']+1,color='cyan',ls='--',lw=.7)
            axes[i,0].set_title(case+' / final decoder layer, mean absolute cross-attention difference across heads')
            axes[i,0].set_ylabel('Decoder query');axes[i,0].set_xlabel('Encoder token position (including any special token)');fig.colorbar(im,ax=axes[i,0],shrink=.7)
        finish(pdf,fig,'Attention patterns for the three replay cases',
            'Each map uses its own color scale. Encoder positions are token coordinates, not causal attributions; independent sampled suffixes also change attention.')
    (analysis/'figures_manifest.json').write_text(json.dumps({'pdf':path.name,'pages':pages,'sha256':digest(path),'plot_source_sha256':digest(Path(__file__))},indent=2),encoding='utf-8')
    print(json.dumps({'pdf':str(path),'pages':pages}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);render(p.parse_args().output)
