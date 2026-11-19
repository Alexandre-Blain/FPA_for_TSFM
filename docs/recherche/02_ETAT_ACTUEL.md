# Etat actuel

## Pipeline disponible

La pipeline actuelle sait :

1. charger des series depuis un export local des datasets Chronos benchmark,
2. decouper les series en fenetres glissantes,
3. lancer Chronos v1 en decodage token-level,
4. forcer des tokens alternatifs a certains `branch_step`,
5. sampler des continuations futures,
6. comparer les distributions par quantiles,
7. produire des scores de shift,
8. sauvegarder les CSV apres chaque groupe de branche,
9. reprendre un run depuis un checkpoint,
10. generer des figures globales, par dataset et recherche.

## Scripts principaux

```text
scripts/data/download_chronos_benchmark_datasets.py
scripts/runs/run_chronos_benchmark_scan.py
scripts/runs/run_chronos_targeted_refinement.py
scripts/viz/plot_chronos_benchmark_scan.py
scripts/presentations/create_chronos_findings_ppt.py
```

`run_chronos_benchmark_scan.py` peut lancer automatiquement le refinement cible
avec :

```powershell
--auto-refinement
```

Le refinement selectionne les fenetres les plus sensibles du scan principal,
puis les rerun avec une grille plus fine de `branch_step` et plus de rangs de
tokens forces.

## Modes de branching

`single` :

```text
a un branch_step donne,
tester les top-k tokens candidats,
puis sampler la continuation.
```

`bundle` :

```text
forcer un petit paquet de tokens consecutifs,
avec scenarios de continuation top-1 / top-5 / top-10.
```

Les derniers resultats propres sont surtout en `single`. Les bundles existent
mais coutent beaucoup plus cher.

## Score principal recommande

Pour les nouveaux runs, le ranking global doit utiliser :

```text
context_iqr_scaled_progressive_token_bin_forking_score
```

Unite :

```text
context_iqr = q75(context) - q25(context)
```

Principe :

> Toutes les comparaisons globales doivent utiliser une seule unite de
> normalisation a la fois.

Les autres normalisations sont sauvegardees pour audit ou fallback :

```text
context_std
context_range
gt_iqr
gt_std
gt_range
window_scale
```

## Checkpoint et reprise

Les CSV suivants sont ecrits apres chaque groupe `branch_mode + branch_step`
termine :

```text
chronos_scan_steps.csv
chronos_scan_summary.csv
chronos_scan_errors.csv
checkpoint.json
```

Reprise scan large :

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_benchmark_scan.py `
  --resume-from result\NOM_DU_RUN
```

Reprise refinement :

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_targeted_refinement.py `
  --config configs\chronos_targeted_refinement\default.json `
  --source-run result\NOM_DU_SCAN_SOURCE `
  --benchmark-folder data\raw\chronos_benchmark `
  --resume-from result\NOM_DU_REFINEMENT
```

Correction recente :

```text
en reprise refinement, selected_refinement_windows.csv n'est plus reecrit s'il
existe deja
```

et :

```text
les append CSV sont alignes sur le schema deja present
```

Cela evite de melanger silencieusement des colonnes anciennes et nouvelles.

Les anciens runs partiellement corrompus par un append de schema incompatible
sont relus avec un warning et les lignes incompatibles sont ignorees. Cela sert
a recuperer ce qui est exploitable, pas a rendre ces runs aussi fiables qu'un
run propre relance avec le schema actuel.
