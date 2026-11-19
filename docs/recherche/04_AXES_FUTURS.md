# Axes Futurs

Ce fichier est le fil conducteur principal pour decider comment avancer.

## Mise a jour apres le refinement partiel

Le run :

```text
result/refinement_faster_global_20260728_125930
```

apporte trois informations nouvelles :

1. les gros shifts Chronos semblent souvent venir de tokens encore plausibles
   plutot que de tokens tres improbables,
2. le regime `uncertain_plausible` est actuellement le plus interessant,
3. la persistance du shift explique beaucoup mieux le score que le branch_step
   seul.

Implication :

> Le projet doit maintenant passer d'un simple ranking de gros shifts a une
> cartographie locale des zones sensibles : `branch_step x token_rank x
> topology_regime`.

Limite importante :

> Le refinement courant est partiel et utilise encore `window_scale`. Le prochain
> run de confirmation doit utiliser `context_iqr` comme unite de comparaison par
> defaut.

## Objectif Recherche Court Terme

Determiner si les bifurcations Chronos sont :

- des bifurcations naturelles dans des zones incertaines,
- des stress tests provoques par des tokens improbables,
- ou des artefacts lies a l'echelle, au sampling ou au protocole.

## Priorite 1 - Stabiliser Les Top Windows

Le scan large sert a reperer les fenetres sensibles. Ensuite, un refinement
cible rerun uniquement ces fenetres avec une resolution plus fine.

Configuration retenue maintenant :

- selectionner les top 20 fenetres globales,
- ajouter les top 5 fenetres par dataset,
- rerun avec `num_samples=40`,
- rerun avec `top_k=15`,
- rerun avec une grille plus fine de `branch_step` :

```text
0,2,4,6,8,10,12,16
```

Objectifs :

- comparer la stabilite du ranking entre scan large et refinement,
- verifier si les courbes `law_shift_h` gardent la meme forme,
- resserrer la granularite des tokens pour identifier des micro-zones sensibles.

Note recherche :

> La version suivante devrait remplacer la liste fixe de `branch_step` par une
> liste dynamique. On detecterait d'abord les zones les plus probables de fork,
> puis on testerait tous les tokens dans ces zones.

Version concrete a implementer :

1. scan coarse avec une grille economique,
2. detection des pics locaux de shift ou de forte incertitude,
3. refinement dense autour de ces pics,
4. carte fine par fenetre sensible.

Les seeds multiples ne sont pas prioritaires pour l'instant. La stabilite est
d'abord estimee par comparaison scan large vs refinement cible.

Question :

> Les gros shifts observes sont-ils robustes ou dus au bruit Monte Carlo ?

## Priorite 1bis - Carte Locale Des Micro-Zones Sensibles

Le refinement dense doit produire des figures par fenetre :

```text
x = branch_step
y = token_rank
couleur = score normalise
annotation = topology_regime / token_probability / persistence_ratio
```

Objectif :

> Identifier precisement ou Chronos bifurque dans la fenetre, au lieu de garder
> seulement un top global.

Cette carte est potentiellement la contribution recherche la plus claire :

```text
une methode pour localiser des zones de sensibilite token-level dans un modele
de forecasting discretise.
```

Extension plus ambitieuse :

```text
tester tous les tokens dans une petite zone temporelle detectee comme sensible
```

au lieu de tester beaucoup de steps partout.

## Priorite 1ter - Robustesse De Reprise Et Tracabilite

Le refinement courant a revele un probleme de tracabilite :

```text
selected_refinement_windows.csv ne correspond pas parfaitement aux fenetres deja
ecrites dans chronos_scan_summary.csv
```

Actions ajoutees ou a garder :

1. ne plus reecrire `selected_refinement_windows.csv` pendant une reprise,
2. aligner les colonnes CSV pendant les append,
3. ajouter une verification de schema avant reprise,
4. stocker une `schema_version` dans chaque `config.json`,
5. produire un rapport de completion par dataset et par fenetre.

Objectif :

> Un run interrompu doit pouvoir etre repris sans changer silencieusement son
> plan experimental.


## Priorite 2 - Formaliser La Typologie Topologique

Creer une matrice de lecture basee sur :

- `normalized_token_entropy`,
- `top1_top2_margin`,
- `token_probability`,
- `token_surprisal`,
- `context_iqr_scaled_progressive_token_bin_forking_score` par defaut.
  Les variantes `context_std`, `context_range`, `gt_iqr`, `gt_std`,
  `gt_range` et `window_scale` sont aussi sauvegardees pour auditer la
  normalisation ou basculer tout un run vers une autre unite.

Typologie proposee :

```text
haute entropie + faible marge + gros shift
  -> bifurcation plausible / incertitude naturelle

basse entropie + forte marge + token improbable + gros shift
  -> stress test / fragilite hors trajectoire probable

haute entropie + faible shift
  -> incertitude locale absorbee par le modele

basse entropie + faible shift
  -> trajectoire stable
```

Question :

> Les gros shifts apparaissent-ils plutot dans les zones d'incertitude naturelle
> ou dans les zones de confiance fragile ?

## Priorite 2bis - Comparer Incertitude Modele Et Sensibilite FPA

Nouvel axe ajoute :

```text
docs/recherche/07_INCERTITUDE_MODELE_VS_FPA.md
```

Question :

> La FPA mesure-t-elle seulement l'incertitude deja visible dans les logits de
> Chronos, ou revele-t-elle une sensibilite structurelle differente ?

Premiers resultats :

```text
sur le scan complet, corr(model_distribution_uncertainty_index, FPA) ~= +0.068
sur le refinement partiel, corr(model_distribution_uncertainty_index, FPA) ~= +0.089
```

Lecture :

> L'entropie/marge locale explique peu le score FPA. Cela soutient l'hypothese
> que la FPA mesure autre chose qu'une incertitude interne immediate.

Cas a prioriser :

```text
faible incertitude modele + fort shift FPA
```

Pourquoi :

> Ce sont les exemples ou Chronos semble localement confiant, mais ou une
> intervention token-level deforme durablement la trajectoire future.

## Priorite 3 - Separer Les Scores Temporels

Le score actuel melange amplitude, persistance et amplification.

Ajouter trois scores separes :

`instant_forking_score` :

```text
shift juste apres le token force
```

`persistent_forking_score` :

```text
shift qui reste eleve jusqu'a la fin de l'horizon
```

`progressive_forking_score` :

```text
shift qui augmente au cours du temps
```

Question :

> Cherche-t-on une sensibilite immediate, une divergence durable, ou une
> amplification progressive ?

## Priorite 4 - Comparer Global Et Par Dataset

Toujours produire deux vues :

1. ranking global avec score normalise,
2. ranking separe par dataset.

Pourquoi :

- ERCOT peut dominer le score brut,
- Dominick contient des series courtes et parfois des futurs plats,
- exchange_rate a une echelle tres differente,
- m4_daily peut produire des dynamiques plus proches de vraies series longues.

Question :

> Les memes regimes de shift apparaissent-ils dans tous les datasets ?

## Priorite 5 - Reintroduire Les Bundles De Maniere Ciblee

Le mode `bundle` coute cher.

Strategie recommandee :

1. scan large en `single`,
2. selectionner les top fenetres,
3. rerun cible avec `single,bundle`,
4. comparaison single vs bundle.

Question :

> Les deviations multi-step revelent-elles une fragilite differente du simple
> token forcing ?

## Priorite 6 - Lien Avec L'erreur Future

Comparer :

```text
context_iqr_scaled_progressive_token_bin_forking_score
base_mae_over_window_scale
base_rmse_over_window_scale
```

Quadrants a analyser :

```text
fort shift + faible erreur
  -> sensible mais prediction base correcte

fort shift + forte erreur
  -> zone fragile et incorrecte

faible shift + forte erreur
  -> modele faux avec confiance

faible shift + faible erreur
  -> zone stable
```

Question :

> La FPA est-elle un indicateur d'incertitude utile ou seulement une sonde de
> sensibilite interne ?

## Priorite 7 - Scenarios Decisionnels Generiques

Nouvel axe ajoute :

```text
docs/recherche/08_SCENARIOS_DECISIONNELS.md
```

Question :

> Une branche FPA change-t-elle seulement la trajectoire numerique, ou change-t-
> elle aussi le statut d'un scenario defini sur la forecast ?

Scenarios implementes :

```text
final_direction
upside_threshold_crossing
downside_threshold_crossing
risk_band_breach
peak_timing_bin
trough_timing_bin
```

Premier resultat sur le run complet :

```text
peak_timing_bin                40.7 % de changements
trough_timing_bin              35.5 % de changements
final_direction                 7.9 % de changements
risk_band_breach                6.7 % de changements
upside_threshold_crossing       3.1 % de changements
downside_threshold_crossing     1.8 % de changements
```

Lecture :

> Les branches changent beaucoup plus facilement le timing des evenements que le
> franchissement de seuils. C'est une piste forte : la FPA pourrait etre utile
> pour selectionner des zones sensibles au timing decisionnel.

Cas a prioriser :

```text
faible incertitude modele + fort shift FPA + changement de scenario
```

Prochaine etape :

> Remplacer les scenarios generiques par un petit jeu de scenarios parametrables
> adaptes a une question concrete.

## Message Recherche Possible

Version prudente :

> Nous developpons une adaptation token-level de la FPA pour Chronos afin de
> sonder la sensibilite locale des previsions.

Version a tester :

> Le branching token-level peut servir d'indicateur d'incertitude structurelle
> dans les modeles de prevision tokenises.

Pour defendre la version ambitieuse, il faudra relier les scores FPA a :

- l'erreur future,
- l'entropie des logits,
- les changements structurels dans les series,
- la stabilite sous plusieurs seeds,
- la coherence entre datasets.

