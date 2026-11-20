# Incertitude modele vs sensibilite FPA

Objectif de cet axe :

> Tester si l'incertitude interne de Chronos explique les zones ou la FPA trouve
> une divergence structurelle, ou si la FPA capture une information differente.

## Runs analyses

Run complet principal :

```text
result/faster_global_scan_no_refinement_20260727_173315
```

Run de refinement partiel :

```text
result/refinement_faster_global_20260728_125930
```

Les analyses sont offline : aucun nouvel appel Chronos n'est lance. On lit
uniquement `chronos_scan_summary.csv`.

Commande :

```powershell
.\.venv\Scripts\python.exe scripts\viz\analyze_chronos_uncertainty_alignment.py `
  result\faster_global_scan_no_refinement_20260727_173315 `
  result\refinement_faster_global_20260728_125930 `
  --top-n 50
```

Sorties par run :

```text
recherche/model_uncertainty_alignment/
  model_uncertainty_fpa_correlations.csv
  model_uncertainty_fpa_quadrant_summary.csv
  model_uncertainty_fpa_quadrant_branches.csv
  model_uncertainty_interesting_branches.csv
  model_uncertainty_dataset_summary.csv
  model_uncertainty_alignment_summary.json
  figures/
```

## Separation conceptuelle importante

Il faut separer deux objets :

### Incertitude de distribution du modele

Elle decrit la distribution locale de Chronos au `branch_step`.

Colonnes utilisees :

```text
normalized_token_entropy
top1_top2_margin
top1_probability
```

Index ajoute :

```text
model_distribution_uncertainty_index
```

Construction :

```text
moyenne des rangs percentiles de :
  normalized_token_entropy         plus haut = plus incertain
  inverse_top1_top2_margin         marge faible = plus incertain
  inverse_top1_probability         top1 faible = plus incertain
```

### Plausibilite du token force

Elle decrit le token alternatif que l'on force, pas l'incertitude globale du
modele.

Colonnes utilisees :

```text
token_probability
token_surprisal = -log P(token)
token_rank
```

Index ajoute :

```text
forced_token_implausibility_index
```

Interpretation :

> Un token improbable n'est pas equivalent a un modele incertain. Le modele peut
> etre tres confiant et l'on force volontairement un token peu probable.

## Resultat principal sur le scan complet

Run :

```text
result/faster_global_scan_no_refinement_20260727_173315
```

Score FPA utilise :

```text
window_scaled_progressive_token_bin_forking_score
```

Branches alternatives analysees :

```text
1008
```

Correlations Spearman avec le score FPA :

```text
normalized_token_entropy              +0.085
model_distribution_uncertainty_index  +0.068
inverse_top1_probability              +0.065
inverse_top1_top2_margin              +0.050
token_rank                            -0.126
token_surprisal                       -0.139
forced_token_implausibility_index     -0.146
```

Lecture :

> L'incertitude interne du modele est tres faiblement correlee au score FPA. La
> FPA ne semble donc pas etre une simple relecture de l'entropie des logits.

Autre point important :

> Les tokens les plus improbables ne produisent pas les plus gros shifts. Au
> contraire, la correlation negative avec `token_surprisal` et `token_rank`
> indique que les alternatives plus plausibles tendent legerement a produire des
> shifts plus forts.

## Resultat sur le refinement partiel

Run :

```text
result/refinement_faster_global_20260728_125930
```

Attention :

> Le CSV du refinement contient des lignes ecrites avec un schema incompatible.
> L'analyse ignore ces lignes invalides avec `on_bad_lines='skip'`.

Branches alternatives analysees :

```text
1372
```

Correlations Spearman avec le score FPA :

```text
inverse_top1_top2_margin              +0.110
model_distribution_uncertainty_index  +0.089
inverse_top1_probability              +0.078
normalized_token_entropy              +0.076
token_surprisal                       -0.343
forced_token_implausibility_index     -0.354
token_rank                            -0.357
```

Lecture :

> Le refinement confirme que l'entropie/marge locale explique peu le score FPA.
> En revanche, la plausibilite du token force devient plus structurante : les
> top ranks produisent plus souvent les gros shifts.

## Quadrants interessants

Sur le scan complet :

```text
high_model_uncertainty + high_fpa_shift:
  82 branches
  median score = 0.283

lower_model_uncertainty + high_fpa_shift:
  170 branches
  median score = 0.249
```

Interpretation :

> Les gros shifts ne sont pas reserves aux zones ou Chronos est localement
> incertain. Il existe beaucoup de cas ou le modele semble relativement confiant
> localement, mais ou la FPA trouve une divergence forte.

Cas recherche fort :

```text
lower_model_uncertainty + high_fpa_shift
```

Pourquoi :

> C'est le cas ou la FPA apporte potentiellement une perspective differente du
> modele : Chronos ne signale pas fortement son incertitude locale, mais une
> alternative forcee change durablement la trajectoire future.

## Exemples notables

Scan complet, cas `low_model_uncertainty_high_fpa` :

```text
m4_daily/T000000 window=4 branch_step=4 rank=3
  score = 0.415
  entropy = 0.068
  margin = 0.781
  persistence_ratio = 0.964

exchange_rate/currency_5 window=3 branch_step=4 rank=5
  score = 0.406
  entropy = 0.005
  margin = 0.987
  topology = confident_improbable
  persistence_ratio = 0.999

m4_daily/T000000 window=2 branch_step=16 rank=3
  score = 0.394
  entropy = 0.094
  margin = 0.658
  persistence_ratio = 0.919
```

Ces exemples sont importants parce qu'ils correspondent a :

```text
faible incertitude locale du modele + fort shift FPA persistant
```

## Difference par dataset

Scan complet :

```text
ercot:
  corr(model_distribution_uncertainty_index, FPA) = +0.193

exchange_rate:
  corr(model_distribution_uncertainty_index, FPA) = +0.041

m4_daily:
  corr(model_distribution_uncertainty_index, FPA) = -0.161
```

Lecture :

> Le lien entre incertitude modele et sensibilite FPA depend du dataset. Ce
> n'est pas une relation universelle simple.

## Conclusion provisoire

Hypothese soutenue :

> La FPA revele une incertitude structurelle differente de l'incertitude interne
> immediate de Chronos.

Version plus precise :

> L'entropie/marge des logits de Chronos donne une incertitude locale au moment
> du token. La FPA mesure plutot la capacite d'une alternative locale a deformer
> durablement la trajectoire future.

## Limites

1. Les runs analyses utilisent encore `window_scale`, pas encore `context_iqr`.
2. Le refinement est partiellement corrompu par un ancien append CSV de schema
   incompatible.
3. Les correlations sont descriptives, pas causales.
4. Le score FPA reste composite : amplitude, persistance et progression.
5. Le scan teste surtout les top-k tokens, donc il couvre mal les tokens tres
   profonds.

## Prochaines ameliorations

1. Relancer un scan/refinement propre avec `context_iqr`.
2. Faire une figure dediee aux quadrants :

```text
x = model_distribution_uncertainty_index
y = FPA score
couleur = dataset
annotation = topology_regime
```

3. Ajouter une selection automatique des cas :

```text
faible incertitude modele + fort FPA + faible erreur base
```

4. Comparer les correlations par type de score :

```text
instant_forking_score
persistent_forking_score
progressive_forking_score
```

5. Utiliser cet axe comme pont vers les scenarios decisionnels :

```text
une zone est-elle sensible seulement mathematiquement,
ou peut-elle changer une decision definie sur la forecast ?
```
