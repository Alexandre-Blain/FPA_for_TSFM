# Chronos FPA - Guide Pratique

La FPA mesure comment les continuations changent quand on force un token de
prevision. Elle ne mesure pas directement la qualite de prediction.

Le [statut scientifique courant](docs/research/FPA_STATUS.md) et le
[workflow versionne](docs/research/README_WORKFLOW_V2.md) donnent les prochaines
autorisations et le handoff. Le prototype opt-in de Prompt 2 est distinct des
launchers historiques : `scripts/runs/run_chronos_microbenchmark.py`, avec
`configs/chronos_microbenchmark/prompt02.json`. Sa configuration fige une
autorisation datee et ses plafonds; ne pas la reutiliser comme autorisation
permanente de nouvelle inference.

## Points D'Entree

- [Parametres du scan](configs/chronos_benchmark_scan/README.md) : chaque cle JSON.
- [Parametres du refinement](configs/chronos_targeted_refinement/README.md).
- [Metriques et equations](docs/CHRONOS_METRICS.md).
- [Paper 1 : W1, Energy Distance et samples individuels](docs/CHRONOS_PHASE1.md).
- [Paper 1 : bilan du pilote Phase 2 termine](docs/CHRONOS_PHASE2.md).
- [Paper 1 : controles offline et proposition Phase 3, non lancee](docs/CHRONOS_PHASE3_DESIGN.md).
- [Guide des figures](docs/graphes/CHRONOS_FIGURES_GUIDE.md).
- [Recherche, resultats et limites](docs/recherche/README.md).
- [Tests](tests/README.md).
- [Audit et nettoyage](docs/maintenance/CLEANUP_REPORT.md).

Le code est organise en modules Python simples. Aucun package recherche a
installer. Utiliser le Python de l'environnement evite de reconstruire TimesFM
a chaque commande.

## 1. Donnees Locales

Telecharger une fois, independamment des experiences :

```powershell
uv run --no-project --with datasets python scripts\data\download_chronos_benchmark_datasets.py `
  --output-dir data\raw\chronos_benchmark
```

Les exports JSONL restent dans ce dossier. Relancer un scan ne les telecharge
pas. Voir les options de selection avec `--help` sur le script de download.

## 2. Choisir Un Run

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_benchmark_scan.py `
  --config configs\chronos_benchmark_scan\smoke.json
```

- `smoke.json` : une fenetre, un step, verification courte.
- `default.json` : scan borne, sans refinement automatique.
- `broad_with_refinement.json` : scan suivi d'un refinement cible.

Copier et adapter un JSON pour une nouvelle experience. Les options CLI
explicites remplacent les valeurs du JSON :

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_benchmark_scan.py `
  --config configs\chronos_benchmark_scan\default.json `
  --datasets ercot,exchange_rate,m4_daily `
  --run-name comparaison_tokens
```

Les limites `max_datasets`, `max_series_per_dataset`,
`max_windows_per_series` et `max_total_windows` sont cumulatives. Leur choix
controle la couverture et le cout, pas seulement la duree.

### Branches Et Sampling

- `branch_steps` : positions dans la prevision, indexees depuis zero.
- `top_k` : nombre de tokens candidats au point de branchement, base comprise
  quand elle est deja dans le top-k. Aucun seuil minimal de probabilite implicite.
- `sample_top_k` : troncature du sampling de continuation, **pas** nombre de
  branches. Zero desactive cette troncature.
- `num_samples` : continuations par branche, puis quantiles point par point.
- `branch_modes = single` : un token impose.
- `branch_modes = bundle` : plusieurs tokens imposes. Avec top-k=5 et rangs
  1,5,10, tester les cinq tokens initiaux puis trois chemins deterministes
  pour les tokens suivants. Le nombre exact est enregistre dans les sorties.

Pour les smoke tests : `num_samples = 5`. Pour une estimation plus stable :
augmenter vers 40 ou 100, au prix d'un calcul plus long.

Le refinement est une seconde phase, executee **apres** le scan. Ses valeurs
par defaut sont steps `0,2,4,6,8,10,12,16`, top-k 15, 40 samples,
selection top 20 globale + top 5 par dataset (union sans doublons).

## 3. Sauvegarde Et Reprise

Nouveaux runs : chaque **groupe mode/step d'une fenetre** est publie dans
`branch_groups/` apres validation des tables steps et summary. Les CSV globaux
sont des exports reconstruisibles. Une coupure pendant leur ecriture ne fait
pas perdre les groupes deja publies.

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_benchmark_scan.py `
  --resume-from result\MON_RUN
```

Ne pas repasser toute la configuration : les parametres sauvegardes sont
restaures. Les changements scientifiques incompatibles sont refuses. Les options
d'affichage peuvent changer. `input_config.json` n'est pas ecrase.

Pour reprendre un refinement :

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_targeted_refinement.py `
  --resume-from result\MON_REFINEMENT
```

La selection des fenetres est figee dans
`selected_refinement_windows.csv` ; elle ne sera pas recalculee a la reprise.
`checkpoint_every_branch_groups` controle la frequence des metadonnees,
pas la sauvegarde des groupes, qui reste systematique.

**Historique :** les anciens runs CSV-only ne sont pas migres automatiquement.
Ils restent analysables et scientifiquement utiles, y compris partiels.
Un checkpoint incompatible provoque un diagnostic ; ne pas supprimer ses donnees.

## 4. Refinement Independant

Modifier `source_run` dans le JSON puis lancer :

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_targeted_refinement.py `
  --config configs\chronos_targeted_refinement\default.json
```

Les parametres de fenetrage doivent retrouver les memes contextes. Le score de
selection doit exister dans le run source et rester le meme pour les comparaisons.

## 5. Analyses Sans Nouvelle Inference

Figures generales :

```powershell
.\.venv\Scripts\python.exe scripts\viz\plot_chronos_benchmark_scan.py result\MON_RUN
```

Incertitude interne vs FPA :

```powershell
.\.venv\Scripts\python.exe scripts\viz\analyze_chronos_uncertainty_alignment.py result\MON_RUN
```

Scenarios (branches simples) :

```powershell
.\.venv\Scripts\python.exe scripts\viz\analyze_chronos_scenario_sensitivity.py result\MON_RUN
```

Sensibilite au seuil de probabilite, branches simples uniquement :

```powershell
.\.venv\Scripts\python.exe scripts\viz\analyze_chronos_probability_thresholds.py result\MON_RUN
```

Cette derniere analyse compare sans filtre, p >= 0.1%, 1% et 5%, sans modifier les
scores ni le sampling historique. Elle inclut les points de branchement communs
pour separer filtrage des tokens et selection des contextes. Les tokens non
testes initialement ne peuvent pas etre recuperes apres coup.

**Normalisation :** une seule colonne par analyse, `context_iqr` par defaut.
Changer explicitement la colonne pour l'ensemble de l'analyse si necessaire.
Aucun changement automatique par dataset ou par ligne. Une echelle invalide
reste indefinie et doit etre signalee. Les colonnes utilisant le futur (GT,
ancien `window_scale`) sont diagnostiques, pas utilisables en selection prospective.

Pour les scenarios, `--scale-column context_std` choisit aussi le score FPA
normalise par `context_std` si `--score-column` est omis. Une combinaison explicite
de deux normalisations differentes est refusee.

Les commandes d'analyse peuvent produire des fichiers dans le run donne.
Pour conserver des figures historiques, analyser une copie ou choisir une
destination separee quand l'option est disponible. Le nettoyage du projet ne
regenere pas les sorties historiques.

## 6. Lire Les Sorties

- `input_config.json` : configuration initiale.
- `run_state.json` : parametres et version du nouveau format de reprise.
- `config.json` : bilan et parametres resolus.
- `checkpoint.json` : progression ; statut partiel distinct de termine.
- `branch_groups/` : tables et empreintes des groupes publies.
- `chronos_scan_summary.csv` : une ligne par branche.
- `chronos_scan_steps.csv` : une ligne par branche et pas de prevision.
- `chronos_scan_ranking.csv` : classement selon une colonne explicite.
- `chronos_scan_errors.csv` : erreurs de calcul.
- `chronos_base_quality_warnings.csv` : alertes MAE greedy / IQR du contexte.
- `figures/`, `recherche/` : visualisations et analyses derivees.

La base pour la **FPA** est une continuation echantillonnee apres token de base
force. `base_mae` evalue la trajectoire **greedy** : ce ne sont pas les memes objets.

## 7. Verifier Avant Une Experience Longue

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\maintenance\audit_research_runs.py --help
```

Les tests sont hors ligne, avec petits modeles factices. Ils ne mesurent pas
la performance predictive de Chronos. L'audit distingue couverture, completion
et integrite ; un run partiel n'est pas une experience a jeter.

Les correlations restent descriptives : fenetres chevauchantes, alternatives
partageant une base et biais de top-k. Un grand score n'est ni une erreur
predictive certaine, ni une preuve d'incertitude independante.


