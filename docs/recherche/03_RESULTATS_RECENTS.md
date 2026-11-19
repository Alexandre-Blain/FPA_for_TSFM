# Resultats recents

Ce fichier donne la synthese courte. Le detail chiffre du refinement en cours
est dans :

```text
docs/recherche/06_REFINEMENT_FAST_GLOBAL_20260728.md
```

## Run large de reference

```text
result/topology_temporal_single_20260724_175602
```

Configuration :

```text
model = amazon/chronos-t5-mini
mode = single
branch_steps = 0,8,16,32
top_k = 5
num_samples = 10
horizon = 64
adaptive_context = true
fenetres effectives = 68
```

Ce run a servi a reperer les fenetres les plus sensibles avant refinement.

Conclusion principale du scan large :

> L'improbabilite du token ne suffit pas a expliquer les gros shifts. Le signal
> le plus interessant vient plutot de la combinaison entre topologie locale,
> plausibilite du token et persistance de la divergence.

## Run de refinement courant

```text
result/refinement_faster_global_20260728_125930
```

Etat actuel :

```text
status = running
completed_branch_groups = 98
fenetres touchees = 13
fenetres completes = 12
branches alternatives analysees = 1372
```

Attention :

```text
score analyse = window_scaled_progressive_token_bin_forking_score
```

Ce run ne contient pas encore la normalisation `context_iqr`. Les conclusions
doivent donc etre considerees comme un refinement legacy utile, mais pas comme
le run final normalise.

## Findings actuels

1. ERCOT domine les plus gros shifts.
2. Exchange_rate a des shifts plus faibles mais une meilleure prediction base.
3. Les tokens alternatifs probables, surtout ranks 2 a 5, produisent souvent les
   plus gros shifts.
4. Le regime `uncertain_plausible` donne la meilleure mediane et le meilleur p90.
5. `persistence_ratio` est tres fortement relie au score.
6. `branch_step` n'a pas de tendance globale forte : les zones sensibles sont
   locales, pas simplement "plus tot" ou "plus tard".

## Resultats chiffres importants

Distribution du score sur les branches alternatives :

```text
median = 0.071
p90    = 0.201
p95    = 0.250
max    = 0.461
```

Correlations de rang avec le score :

```text
token_probability = +0.343
token_surprisal   = -0.343
token_rank        = -0.357
persistence_ratio = +0.699
branch_step       = +0.025
```

Lecture :

> Le refinement actuel suggere que les gros shifts Chronos viennent souvent de
> branches plausibles et persistantes, pas seulement de tokens improbables.

## Exemples de fenetres sensibles

```text
ercot/EAST window=4 start=128
  max score = 0.461
  best branch_step = 10
  best token_rank = 2

ercot/NORTH_C window=1 start=32
  max score = 0.432
  best branch_step = 10
  best token_rank = 3

exchange_rate/currency_2 window=3 start=96
  max score = 0.253
  best branch_step = 2
  best token_rank = 2
```

## Ce qui change par rapport au scan large

Le scan large montrait une relation faible entre probabilite du token et score.
Le refinement plus dense montre au contraire une relation plus nette :

```text
plus le token alternatif est haut dans le ranking Chronos,
plus il a tendance a produire un gros shift.
```

Interpretation prudente :

> Chronos semble bifurquer fortement quand on force une alternative encore
> plausible. Cela peut etre different de la FPA sur LLM, ou le lien entre
> improbabilite et shift est souvent moins direct.

## Limites majeures

1. Le refinement n'est pas fini.
2. La couverture actuelle est surtout ERCOT + exchange_rate.
3. `selected_refinement_windows.csv` a ete reecrit et ne reconstruit pas
   parfaitement le plan initial du run.
4. La normalisation utilisee par ce run est `window_scale`, pas `context_iqr`.
5. Il faut eviter de tirer une conclusion globale avant de couvrir Dominick et
   m4_daily.
