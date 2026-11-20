# Chronos FPA - Guide D'Interpretation Des Figures

Ce guide explique ce que chaque graphe essaie de montrer.

Les figures standard sont dans `result/NOM_DU_RUN/figures/`; les figures
exploratoires dans `result/NOM_DU_RUN/figures/recherche/`.

## Figures Standard

### `chronos_top_branch_scores.png`

Montre les branches avec les plus gros scores FPA.

- y = fenetre + step + token force,
- x = score FPA normalise. Par defaut :
  `context_iqr_scaled_progressive_token_bin_forking_score`,
- plus la barre est grande, plus la distribution future s'eloigne de la branche base.

Un gros score ne veut pas dire bonne prediction. C'est une mesure de sensibilite.

### `chronos_window_score_overview.png`

Vue globale des meilleurs scores par fenetre. Elle sert a voir si quelques
fenetres ou quelques datasets dominent tout le run.

### `chronos_top_law_shift_curves.png`

Montre la courbe `law_shift_h` apres le branchement.

- pic rapide = effet instantane,
- courbe elevee jusqu'a la fin = divergence persistante,
- courbe qui monte avec le temps = amplification progressive,
- courbe qui retombe = convergence vers la branche base.

### `chronos_base_quality.png`

Compare l'erreur de la prediction base Chronos a l'echelle choisie pour les
figures quand disponible.

- `base_mae_over_context_iqr` faible = prediction base raisonnable avec le
  defaut actuel,
- `base_mae_over_window_scale` reste le warning conservateur historique,
- valeur proche ou au-dessus de 1 = Chronos est deja mauvais sur cette fenetre.

### `chronos_score_distribution.png`

Distribution des scores FPA. Une longue queue a droite indique quelques branches
tres sensibles.

### `chronos_score_by_dataset_boxplot.png`

Distribution des scores par dataset. Sert a voir si un dataset produit
systematiquement plus de shifts que les autres.

### `chronos_raw_vs_normalized_score.png`

Compare score brut et score normalise. Si les points changent beaucoup apres
normalisation, l'echelle du dataset influencait fortement le score brut.

Le score normalise affiche par defaut est `context_iqr_scaled...`. On peut
forcer une autre colonne avec `--visualisation-score-column`.

### `chronos_score_vs_base_error.png`

Compare sensibilite FPA et erreur de prediction base avec une normalisation
coherente lorsque possible.

- fort shift + faible erreur = prediction base correcte mais localement sensible,
- fort shift + forte erreur = zone fragile et prediction incorrecte,
- faible shift + forte erreur = modele faux mais peu sensible localement,
- faible shift + faible erreur = zone stable.

### `chronos_score_component_contributions.png`

Decompose le score en amplitude, persistance, amplification, shape break et
widening des quantiles.

### `chronos_window_sensitivity_heatmap.png`

Carte dataset/serie/fenetre des scores. Elle sert a reperer les zones
temporelles sensibles avant un refinement cible.

### `chronos_dataset_diagnostic_matrix.png`

Resume plusieurs diagnostics par dataset : score FPA, erreur base, echelle et
couverture.

### `chronos_score_vs_token_probability.png`

L'axe x signifie :

```text
P(token force au branch_step | contexte + prefixe greedy)
```

Donc ce n'est pas la probabilite de toute la trajectoire. C'est uniquement la
probabilite locale du token que l'on force au moment exact du branchement.

```text
P(token force au branch_step | contexte + prefixe greedy)
```

- gros shift sur token peu probable = stress test hors trajectoire probable,
- gros shift sur token probable = bifurcation plausible dans la distribution locale.

### `chronos_score_vs_token_surprisal.png`

Meme idee, mais avec :

```text
surprisal = -log(P(token force au branch_step | contexte + prefixe greedy))
```

Plus la surprisal est grande, plus le token force etait improbable.

### `chronos_score_vs_token_entropy.png`

Compare score FPA et incertitude locale de Chronos au moment du branchement.

- haute entropie + gros shift = zone naturellement incertaine,
- basse entropie + gros shift = fragilite potentiellement interessante.

### `chronos_score_vs_top1_top2_margin.png`

Compare score FPA et marge entre les deux tokens les plus probables.

- faible marge = Chronos hesite entre plusieurs tokens,
- forte marge = Chronos a un token dominant.

### `chronos_branch_step_token_rank_heatmap.png`

Carte globale `branch_step x token_rank`.

- x = rang du token force,
- y = step de forecast ou le token est force,
- couleur = max score FPA normalise observe.

## Figures Recherche

Ces figures sont dans :

```text
figures/recherche/
```

### `score_vs_token_probability_alternatives_only.png`

Comme le graphe de probabilite token, mais sans les branches base/greedy. But :
analyser uniquement les vraies alternatives.

### `score_vs_token_surprisal_alternatives_only.png`

Comme le graphe de surprisal, mais sans branches base/greedy. But : tester si
les gros shifts viennent surtout de tokens improbables.

### `topology_regime_map_alternatives_only.png`

Carte topologique :

- x = marge top1-top2,
- y = entropie normalisee,
- couleur = score FPA,
- taille = improbabilite du token force.

But : distinguer zones incertaines et zones de confiance fragile.

### `branch_step_token_rank_zone_map_alternatives_only.png`

Carte agregee des micro-zones sensibles.

- x = rang du token force,
- y = `branch_step`,
- couleur = plus gros score observe.

But : voir rapidement si les shifts viennent de certains steps ou de certains
rangs de tokens.

### `window_token_rank_micro_map_alternatives_only.png`

Carte plus fine des top fenetres sensibles.

- chaque ligne = une fenetre + un `branch_step`,
- chaque colonne = rang du token force,
- couleur = score FPA.

But : cibler precisement les zones a rerun ensuite avec une liste dynamique de
steps ou de tokens.

### `temporal_shift_profile_alternatives_only.png`

Compare early/mid/late shift pour les meilleures branches alternatives. But :
separer shift instantane, persistant et progressif.

### `temporal_shift_profile_alternatives_only_clipped_p95.png`

Meme graphe, mais l'axe x est clippe au percentile 95. But : rendre les
patterns lisibles quand quelques branches explosent l'echelle.

## Figures Par Dataset

Les figures par dataset sont dans :

```text
figures/by_dataset/NOM_DATASET/
```

Elles reprennent les memes diagnostics, mais sans melanger les datasets. C'est
important quand un dataset domine le ranking global.

