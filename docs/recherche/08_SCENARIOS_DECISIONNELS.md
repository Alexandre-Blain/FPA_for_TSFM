# Scenarios decisionnels generiques

Objectif de cet axe :

> Tester si les branches FPA changent facilement le statut d'un scenario defini
> sur la forecast.

Ce n'est pas encore un modele d'action metier, type acheter/vendre. C'est une
sonde generique :

```text
base forecast -> scenario status
branch forecast -> scenario status
```

Puis on regarde si le statut change.

## Runs analyses

Run complet principal :

```text
result/faster_global_scan_no_refinement_20260727_173315
```

Run de refinement partiel :

```text
result/refinement_faster_global_20260728_125930
```

Commande :

```powershell
.\.venv\Scripts\python.exe scripts\viz\analyze_chronos_scenario_sensitivity.py `
  result\faster_global_scan_no_refinement_20260727_173315 `
  result\refinement_faster_global_20260728_125930 `
  --top-n 50
```

Sorties par run :

```text
recherche/scenario_sensitivity/
  scenario_branch_decisions.csv
  scenario_summary.csv
  scenario_dataset_summary.csv
  scenario_interesting_branches.csv
  scenario_sensitivity_summary.json
  figures/
```

## Scenarios implementes

Les scenarios sont volontairement simples et adaptables.

### 1. final_direction

Compare la direction finale de la mediane forecast :

```text
up / down / flat
```

Seuil de neutralite :

```text
0.10 * decision_scale
```

### 2. upside_threshold_crossing

Teste si la mediane forecast depasse :

```text
base_start_q50 + 0.25 * decision_scale
```

### 3. downside_threshold_crossing

Teste si la mediane forecast passe sous :

```text
base_start_q50 - 0.25 * decision_scale
```

### 4. risk_band_breach

Teste si l'intervalle de prediction `q10-q90` franchit un seuil haut ou bas.

Lecture :

> Ce scenario ne regarde pas seulement la mediane, mais aussi l'incertitude de
> distribution predite.

### 5. peak_timing_bin

Regarde si le moment du pic de mediane change de zone :

```text
early / middle / late
```

### 6. trough_timing_bin

Regarde si le moment du creux de mediane change de zone :

```text
early / middle / late
```

## Echelle decisionnelle

Le script utilise une echelle commune appelee :

```text
decision_scale
```

Ordre de fallback :

```text
context_iqr
window_scale
context_std
context_range
gt_iqr
fallback derive de la forecast
```

Important :

> Le scenario ne depend pas d'un seuil absolu arbitraire en unite brute. Les
> seuils sont exprimes en fraction d'une echelle locale.

## Resultat principal sur le run complet

Run :

```text
result/faster_global_scan_no_refinement_20260727_173315
```

Branches alternatives :

```text
1008
```

Taux de changement par scenario :

```text
peak_timing_bin                40.7 %
trough_timing_bin              35.5 %
final_direction                 7.9 %
risk_band_breach                6.7 %
upside_threshold_crossing       3.1 %
downside_threshold_crossing     1.8 %
```

Lecture :

> Le branching change beaucoup plus facilement le timing des evenements que le
> franchissement de seuils absolus.

Interpretation :

```text
FPA sensible au "quand" avant d'etre sensible au "est-ce que l'evenement arrive".
```

## Resultat par dataset

Sur le run complet :

```text
peak_timing_bin:
  m4_daily      49.0 %
  exchange_rate 46.3 %
  ercot         30.8 %

trough_timing_bin:
  m4_daily      50.5 %
  exchange_rate 31.8 %
  ercot         31.5 %

final_direction:
  ercot         19.0 %
  exchange_rate  0.8 %
  m4_daily       0.5 %
```

Lecture :

> Les scenarios de timing sont sensibles dans plusieurs datasets. En revanche,
> le changement de direction finale est surtout observe sur ERCOT.

## Exemples interessants

### Risk band annulee

```text
exchange_rate/currency_3 window=0 branch_step=0 rank=3
scenario = risk_band_breach
change = cancelled
decision_shift_score = 2.405
FPA score = 0.125
base_mae_over_window_scale = 0.010
```

Lecture :

> La prediction base est bonne, mais certaines branches changent l'alerte de
> risque. C'est un cas interessant pour une future interpretation decisionnelle.

### Timing du pic deplace

```text
m4_daily/T000000 window=0 branch_step=4 rank=5
scenario = peak_timing_bin
change = early_to_late
decision_shift_score = 2.000
FPA score = 0.393
base_mae_over_window_scale = 0.039
```

Lecture :

> La branche ne dit pas seulement "plus haut ou plus bas" : elle deplace la
> structure temporelle de la forecast.

## Lien avec l'axe 1

Axe 1 :

```text
La FPA n'est pas redondante avec l'incertitude locale simple de Chronos.
```

Axe 2 :

```text
Cette sensibilite peut changer des proprietes decisionnelles generiques de la
forecast.
```

Message provisoire :

> La FPA semble utile pour localiser des branches qui ne changent pas seulement
> l'amplitude de la forecast, mais aussi son statut vis-a-vis d'un objectif.

## Limites

1. Les scenarios sont generiques, pas encore lies a un vrai cas metier.
2. Les seuils `0.10` et `0.25` sont raisonnables mais arbitraires.
3. Les scenarios de timing sont sensibles, mais parfois trop faciles a changer.
4. Le refinement reste partiellement corrompu par un ancien probleme de schema
   CSV.
5. Le run complet utilise encore `window_scale` quand `context_iqr` n'est pas
   disponible.

## Prochaines ameliorations

1. Ajouter une config JSON pour parametrer les scenarios :

```text
threshold_fraction
direction_deadband_fraction
timing_bins
```

2. Ajouter des scenarios metier adaptes :

```text
alerte si pic > seuil
alerte si baisse durable
objectif de stabilite
objectif de timing
```

3. Relier les scenarios a l'erreur future :

```text
est-ce qu'une branche change une decision qui aurait ete correcte/incorrecte ?
```

4. Croiser avec l'axe 1 :

```text
faible incertitude modele + fort shift FPA + scenario change
```

5. Construire une carte :

```text
branch_step x token_rank -> taux de changement de scenario
```
