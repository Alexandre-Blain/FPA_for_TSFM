# Chronos FPA Metrics

Ce fichier definit les metriques principales utilisees dans la pipeline Chronos FPA.

Les distances exactes W1 et Energy sur samples individuels (Paper 1, optionnelles)
sont definies dans [CHRONOS_PHASE1.md](CHRONOS_PHASE1.md). Elles excluent le token
force ; les metriques historiques ci-dessous gardent leurs definitions.

## 1. Branching

Pour une fenetre donnee, Chronos produit une trajectoire greedy de base. A un `branch_step`, on force un token alternatif, puis on sample des continuations.

La branche forcee est comparee a une branche base forcee avec le token greedy/base, pas seulement a une ligne greedy deterministe. Cela compare donc deux distributions de continuations.

## 2. Quantile Law Shift

Chaque branche produit `num_samples` trajectoires futures. Pour chaque horizon `h`, on calcule les quantiles :

```text
q10, q20, q30, q40, q50, q60, q70, q80, q90
```

Puis :

```text
law_shift_h = mean_q(abs(branch_quantile[h, q] - base_quantile[h, q]))
```

Interpretation :

- petit `law_shift_h` : la branche ressemble a la base ;
- grand `law_shift_h` : la distribution future s'est deplacee.

## 3. Score Brut

Le score brut est utile seulement dans une meme serie ou un meme dataset :

```text
token_bin_forking_score =
    0.40 * mean_law_shift
  + 0.25 * max_law_shift
  + 0.15 * positive_law_amplification
  + 0.10 * shape_break
  + 0.10 * max_widening_10_90
```

Puis :

```text
progressive_token_bin_forking_score =
    token_bin_forking_score
  * (0.5 + 0.5 * last_over_max_law)
  * (0.5 + 0.5 * monotonic_growth_fraction)
```

Attention : ce score melange des composantes avec unite reelle et des composantes sans unite. Il ne doit pas servir au ranking global entre datasets.

## 4. Normalisation Principale

Le defaut actuel est :

```text
context_iqr = q75(context) - q25(context)
```

Pourquoi :

- l'echelle vient uniquement du contexte disponible au moment de predire ;
- elle est plus robuste aux outliers que `context_range` ;
- elle donne une unite fixe pour tout le run au lieu de choisir differemment selon le dataset.

Le score principal est :

```text
context_iqr_scaled_progressive_token_bin_forking_score
```

Formule :

```text
context_iqr_scaled_token_bin_forking_score =
    0.40 * mean_law_shift / context_iqr
  + 0.25 * max_law_shift / context_iqr
  + 0.15 * positive_law_amplification
  + 0.10 * shape_break
  + 0.10 * max_widening_10_90 / context_iqr
```

Puis :

```text
context_iqr_scaled_progressive_token_bin_forking_score =
    context_iqr_scaled_token_bin_forking_score
  * (0.5 + 0.5 * last_over_max_law)
  * (0.5 + 0.5 * monotonic_growth_fraction)
```

Regle importante : pour comparer des branches, utiliser une seule colonne normalisee dans tout le run. Ne pas melanger `context_iqr` pour un dataset et `context_range` pour un autre.

## 5. Normalisations Alternatives Sauvegardees

Le code calcule les memes scores avec plusieurs denominateurs :

```text
context_iqr_scaled_progressive_token_bin_forking_score
context_std_scaled_progressive_token_bin_forking_score
context_range_scaled_progressive_token_bin_forking_score
gt_iqr_scaled_progressive_token_bin_forking_score
gt_std_scaled_progressive_token_bin_forking_score
gt_range_scaled_progressive_token_bin_forking_score
gt_rms_scaled_progressive_token_bin_forking_score
window_scaled_progressive_token_bin_forking_score
```

Depuis le nettoyage v2, il n'y a plus de fallback automatique :

```text
defaut = context_iqr ; autre colonne = choix explicite pour toute l'analyse
```

`window_scale` est l'ancienne echelle conservatrice :

```text
window_scale = max(
    gt_mean_abs,
    gt_std,
    gt_rms,
    gt_range,
    gt_iqr,
    context_mean_abs,
    context_std,
    context_rms,
    context_range,
    context_iqr
)
```

Elle reste utile comme audit, mais elle n'est plus le defaut de ranking.

## 6. Qualite De La Prediction Base

La qualite de Chronos base est mesuree par `base_mae` et ses ratios normalises :

```text
base_mae_over_context_iqr
base_mae_over_context_std
base_mae_over_context_range
base_mae_over_gt_iqr
base_mae_over_gt_std
base_mae_over_gt_range
base_mae_over_window_scale
base_mae_over_gt_mean_abs
```

Pour les nouveaux runs (les anciens CSV restent inchanges) :

```text
base_forecast_bad = base_mae_over_context_iqr >= bad_base_threshold
```

Par defaut :

```text
bad_base_threshold = 1.0
```

Si l'IQR est invalide, l'alerte est indefinie et non assimilable a une bonne
prediction. `base_mae` evalue la trajectoire greedy, alors que la comparaison FPA
utilise la distribution de continuation apres token de base force.

Interpretation : un gros score FPA est plus interessant si l'erreur base reste raisonnable. Si Chronos base est deja tres mauvais, le shift peut surtout refleter une mauvaise calibration du modele sur cette fenetre.

## 7. Topologie Locale Des Tokens

Ces metriques decrivent la distribution next-token au moment du branchement :

- `token_probability` : `P(token force au branch_step | contexte + prefixe greedy)` ;
- `token_surprisal` : `-log(token_probability)` ;
- `top1_probability` : probabilite du token le plus probable ;
- `top2_probability` : probabilite du deuxieme token ;
- `top1_top2_margin` : `top1_probability - top2_probability` ;
- `normalized_token_entropy` : incertitude locale normalisee.

Objectif recherche : tester si les gros shifts arrivent plutot dans des zones incertaines ou dans des zones localement certaines ou un token peu probable casse fortement la trajectoire.

## 8. Scores Temporels

Ces scores separent trois formes de divergence. Par defaut, leurs alias courts utilisent la meme normalisation que le run principal, donc `context_iqr` si disponible.

```text
instant_forking_score = early_law_shift / context_iqr
```

```text
persistent_forking_score =
    late_law_shift / context_iqr
  * (0.5 + 0.5 * persistence_ratio)
```

```text
progressive_forking_score =
    max(late_law_shift - early_law_shift, 0) / context_iqr
  * (0.5 + 0.5 * monotonic_growth_fraction)
  * clip(max(late_over_early_law, 1), upper=10)
```

Le code sauvegarde aussi les variantes par echelle, par exemple :

```text
context_iqr_scaled_progressive_forking_score
context_std_scaled_progressive_forking_score
window_scale_scaled_progressive_forking_score
```

## 9. Colonnes Diagnostics `_over_*`

Les colonnes du type :

```text
mean_law_shift_over_context_iqr
max_law_shift_over_context_iqr
progressive_token_bin_forking_score_over_window_scale
```

sont des diagnostics. Le score comparable principal est la version recomposes avec les composantes unitaires divisees avant ponderation, par exemple `context_iqr_scaled_progressive_token_bin_forking_score`.

