# Chronos FPA Math Audit

Audit des choix mathematiques actuels pour eviter que des erreurs se propagent dans les analyses.

Le nettoyage v2 conserve les formules du score et corrige les contrats de
donnees et d'analyse : une normalisation explicite, identifiants preserves,
extrema ex aequo signales et reprises atomiques. Les anciens CSV ne sont pas
recalcules. Voir [le bilan](../archive/CLEANUP_REPORT.md) et
[la suite de tests](../../tests/README.md) pour les verifications reproductibles.

## 1. Comparaison Des Branches

La comparaison principale se fait entre :

- une branche alternative avec token force ;
- une branche base forcee avec le token greedy/base.

Cela evite de comparer une distribution de samples a une seule trajectoire greedy deterministe.

## 2. Quantiles

Chaque branche produit `num_samples` trajectoires futures. Les trajectoires sont transformees en quantiles par horizon :

```text
q10, q20, q30, q40, q50, q60, q70, q80, q90
```

Le shift par horizon est :

```text
law_shift_h = mean_q(abs(branch_q[h, q] - base_q[h, q]))
```

Les objets compares sont homogenes : quantiles de valeurs futures vs quantiles de valeurs futures.

## 3. Normalisation

La normalisation par defaut est maintenant :

```text
context_iqr = q75(context) - q25(context)
```

Raison : `context_iqr` est observe avant prediction et resiste mieux aux valeurs extremes que `context_range`.

Le code calcule aussi les memes scores avec `context_std`, `context_range`, `gt_iqr`, `gt_std`, `gt_range`, `gt_rms` et `window_scale`. Ces colonnes permettent de basculer tout un run vers une autre unite si `context_iqr` est defectueux.

Point de vigilance : ne jamais comparer directement deux scores calcules avec deux denominateurs differents. Si on bascule, on bascule le ranking et toutes les visualisations vers la meme colonne.

## 4. Score Principal

Le score principal global est :

```text
context_iqr_scaled_progressive_token_bin_forking_score
```

Il ne fait pas simplement :

```text
raw_score / context_iqr
```

car le score brut melange des termes avec unites et des termes sans unite. A la place, seules les composantes en unites reelles sont divisees par `context_iqr` :

```text
0.40 * mean_law_shift / context_iqr
+ 0.25 * max_law_shift / context_iqr
+ 0.15 * positive_law_amplification
+ 0.10 * shape_break
+ 0.10 * max_widening_10_90 / context_iqr
```

Puis les multiplicateurs progressifs sont appliques.

## 5. Qualite Base

Le code sauvegarde plusieurs ratios de qualite base :

```text
base_mae_over_context_iqr
base_mae_over_context_std
base_mae_over_context_range
base_mae_over_gt_iqr
base_mae_over_gt_std
base_mae_over_gt_range
base_mae_over_window_scale
```

Pour les nouveaux runs, le warning `base_forecast_bad` utilise
`base_mae_over_context_iqr >= bad_base_threshold`. Une echelle invalide donne
une alerte indefinie. Les anciens runs utilisaient `window_scale` et restent
inchanges ; ne pas comparer leurs alertes comme si la convention etait identique.

## 6. Topologie Logits

La topologie est calculee a partir de la distribution next-token apres masquage des tokens speciaux.

Checks mathematiques :

- `top1_probability >= top2_probability` ;
- `top1_top2_margin = top1_probability - top2_probability` ;
- `token_surprisal = -log(token_probability)` ;
- `0 <= normalized_token_entropy <= 1` ;
- `0 <= top_k_probability_mass <= 1`.

## 7. Ce Qui Est Comparable

Comparable globalement :

```text
context_iqr_scaled_progressive_token_bin_forking_score
```

Comparable globalement seulement si on force la meme colonne partout :

```text
context_std_scaled_progressive_token_bin_forking_score
context_range_scaled_progressive_token_bin_forking_score
gt_iqr_scaled_progressive_token_bin_forking_score
window_scaled_progressive_token_bin_forking_score
```

Diagnostic seulement :

```text
progressive_token_bin_forking_score_over_window_scale
progressive_token_bin_forking_score_over_context_iqr
```

Ces ratios divisent le score brut entier, donc ils restent moins propres mathematiquement que les scores recomposes.

