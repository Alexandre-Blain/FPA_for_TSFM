# Analyse - refinement_faster_global_20260728_125930

Run analyse :

```text
result/refinement_faster_global_20260728_125930
```

Date de lecture : 2026-07-31.

## Etat du run

Le run n'est pas termine. Le checkpoint indique :

```text
status = running
completed_branch_groups = 98
completed_windows = 12
last_event = exchange_rate / currency_4 / window 2 / branch_step 2
```

Resume :

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_targeted_refinement.py `
  --config configs\chronos_targeted_refinement\default.json `
  --source-run result\topology_temporal_single_20260724_175602 `
  --benchmark-folder data\raw\chronos_benchmark `
  --resume-from result\refinement_faster_global_20260728_125930
```

## Configuration observee

Le refinement courant teste :

```text
branch_mode = single
branch_steps = 0,2,4,6,8,10,12,16
top_k = 15
num_samples = 40
horizon = 64
```

Chaque groupe termine contient :

```text
1 branche base forcee
14 branches alternatives
```

Donc les analyses ci-dessous filtrent les alternatives avec :

```text
is_base_token = False
```

## Attention normalisation

Ce run a ete lance avant la bascule propre vers la normalisation par
`context_iqr`. Il ne contient pas :

```text
context_iqr_scaled_progressive_token_bin_forking_score
context_iqr
```

La colonne utilisee pour l'analyse actuelle est donc :

```text
window_scaled_progressive_token_bin_forking_score
```

Interpretation :

> Les conclusions sont utiles pour la topologie et la dynamique du refinement,
> mais elles doivent etre confirmees dans un run recent avec `context_iqr` comme
> unite de comparaison par defaut.

## Couverture actuelle

Etat des CSV :

```text
chronos_scan_summary.csv = 1470 lignes
branches alternatives = 1372 lignes
branches base = 98 lignes
chronos_scan_steps.csv = 94080 lignes
fenetres touchees = 13
fenetres completes = 12
fenetres partielles = 1
```

Couverture par dataset :

```text
ercot         = 9 fenetres touchees, 9 completes, 72 branch_steps
exchange_rate = 4 fenetres touchees, 3 completes, 1 partielle, 26 branch_steps
dominick      = pas encore traite dans les CSV actuels
m4_daily      = pas encore traite dans les CSV actuels
```

## Probleme de tracabilite observe

Le fichier actuel :

```text
selected_refinement_windows.csv
```

ne correspond pas parfaitement aux fenetres deja presentes dans
`chronos_scan_summary.csv`.

Comparaison observee :

```text
fenetres dans summary = 13
fenetres selectionnees actuelles = 26
intersection = 7
summary_not_selected = 6
selected_not_summary = 19
```

Hypothese la plus probable :

> Le fichier de selection a ete regenere ou reecrit apres une reprise avec une
> config differente. Les lignes deja calculees restent valides, mais le fichier
> de selection n'est plus une source fiable pour reconstruire exactement le plan
> initial du run.

Correction ajoutee au code :

```text
en reprise, selected_refinement_windows.csv est reutilise s'il existe
les append CSV respectent maintenant les colonnes deja existantes
```

## Distribution du score

Sur les branches alternatives :

```text
median = 0.071
p75    = 0.130
p90    = 0.201
p95    = 0.250
p99    = 0.357
max    = 0.461
```

Lecture :

> Les shifts forts existent, mais ils ne sont pas massivement repartis partout.
> Le refinement revele plutot quelques zones tres sensibles, plus une queue de
> distribution progressive.

## Comparaison par dataset

Sur les branches alternatives :

```text
ercot:
  median score = 0.078
  p90 score    = 0.222
  max score    = 0.461
  median base_mae_over_window_scale = 0.112

exchange_rate:
  median score = 0.063
  p90 score    = 0.123
  max score    = 0.253
  median base_mae_over_window_scale = 0.030
```

Lecture :

> ERCOT domine les plus gros shifts meme apres normalisation `window_scale`.
> Exchange_rate produit moins de gros scores, mais la prediction base y est
> souvent meilleure. Les shifts exchange_rate sont donc scientifiquement
> interessants car ils peuvent indiquer une sensibilite interne sans grosse
> erreur de prediction de base.

## Fenetres les plus sensibles

Exemples principaux :

```text
ercot/EAST window=4 start=128
  max score = 0.461
  median window score = 0.121
  best branch_step = 10
  best token_rank = 2
  base_mae_over_window_scale = 0.112

ercot/NORTH_C window=1 start=32
  max score = 0.432
  median window score = 0.105
  best branch_step = 10
  best token_rank = 3
  base_mae_over_window_scale = 0.192

ercot/FAR_WEST window=1 start=32
  max score = 0.422
  median window score = 0.029
  best branch_step = 0
  best token_rank = 3
  base_mae_over_window_scale = 0.040

exchange_rate/currency_2 window=3 start=96
  max score = 0.253
  median window score = 0.040
  best branch_step = 2
  best token_rank = 2
  base_mae_over_window_scale = 0.031
```

Interpretation :

> Certaines fenetres ont un seul pic isole, par exemple `ercot/FAR_WEST`.
> D'autres ont une sensibilite plus large, par exemple `ercot/NORTH_C window=4`
> dont le score median de fenetre est eleve. Il faut donc regarder a la fois le
> maximum et la mediane par fenetre.

## Probabilite du token et score

Correlations de rang avec le score normalise actuel :

```text
token_probability = +0.343
token_surprisal   = -0.343
token_rank        = -0.357
```

Lecture :

> Dans ce refinement Chronos, les tokens alternatifs les plus probables tendent
> a produire les plus gros shifts. C'est interessant parce que ce n'est pas
> forcement ce qu'on observe en FPA sur LLM, ou l'improbabilite du token n'est
> pas necessairement correlee aux gros shifts.

Conclusion prudente :

> Pour Chronos, les bifurcations fortes semblent souvent venir de futurs
> alternatifs plausibles plutot que de tokens tres improbables. A confirmer sur
> le run complet et avec `context_iqr`.

## Topologie locale

Regimes observes :

```text
uncertain_plausible:
  median score = 0.133
  p90 score    = 0.276
  max score    = 0.428
  median token_probability = 0.113
  median top1_top2_margin = 0.009

mixed_topology:
  median score = 0.065
  p90 score    = 0.170
  max score    = 0.461
  median token_probability = 0.001
  median top1_top2_margin = 0.254

uncertain_competitive:
  median score = 0.051
  p90 score    = 0.178
  max score    = 0.328
  median token_probability = 0.008
  median top1_top2_margin = 0.010
```

Lecture :

> Le regime `uncertain_plausible` est le plus fort en mediane et en p90. Cela
> soutient l'idee que les gros shifts correspondent souvent a une vraie zone
> d'incertitude locale ou plusieurs futurs plausibles coexistent.

Limite :

> Le regime `confident_improbable` n'apparait pas dans la partie terminee du
> refinement. On ne peut donc pas encore conclure qu'il est absent globalement.

## Temporalite

Correlations de rang avec le score :

```text
branch_step        = +0.025
early_law_shift    = +0.052
late_law_shift     = +0.267
persistence_ratio  = +0.699
```

Lecture :

> Le moment exact du `branch_step` n'explique presque rien globalement. En
> revanche, les gros scores sont fortement lies a la persistance du shift dans
> l'horizon futur.

Conclusion :

> Le score actuel ne capte pas seulement une deviation immediate. Il favorise
> clairement les divergences qui restent presentes jusqu'a la fin de l'horizon.
> L'idee de "progressive forking score" reste donc pertinente.

## Ce qu'on apprend deja

1. Le refinement donne une carte plus fine des zones sensibles.
2. Les top shifts actuels sont surtout dans ERCOT.
3. Exchange_rate montre des shifts plus modestes mais avec meilleure base.
4. Les tokens plausibles, surtout ranks 2 a 5, dominent les gros shifts.
5. La topologie `uncertain_plausible` est actuellement le meilleur signal.
6. La persistance explique mieux le score que le branch_step ou l'entropie seule.

## Echecs ou limites du run courant

1. Le run est partiel.
2. Les datasets Dominick et m4_daily ne sont pas encore couverts dans les CSV.
3. Le fichier `selected_refinement_windows.csv` courant n'est pas parfaitement
   coherent avec les fenetres deja calculees.
4. La normalisation utilisee est encore `window_scale`, pas `context_iqr`.
5. ERCOT domine les maxima, donc il faut toujours regarder aussi les vues par
   dataset.
6. Les conclusions topologiques restent provisoires tant que la couverture n'est
   pas terminee.

## Decisions recommandees

Court terme :

1. Finir ce refinement pour exploiter les resultats deja couteux.
2. Garder son analyse marquee comme `window_scale legacy`.
3. Relancer ensuite un refinement propre avec la normalisation `context_iqr`.
4. Ajouter un controle automatique de schema avant toute reprise.

Moyen terme :

1. Produire une carte fine `branch_step x token_rank` par fenetre top.
2. Comparer score max, score median de fenetre et persistence_ratio.
3. Isoler les cas `fort shift + faible base error`.
4. Comparer explicitement `uncertain_plausible` vs `confident_improbable`.
5. Ajouter une selection dynamique de branch_steps autour des zones sensibles.
