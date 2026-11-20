# Biais, limites et controles

Ce fichier liste les risques d'interpretation qui peuvent faire deriver le
projet si on ne les surveille pas.

## Mise A Jour Maintenance V2

Les resultats historiques sont conserves sans recalcul, y compris les runs
partiels. L'[inventaire](CLEANUP_REPORT.md) distingue couverture,
integrite et completion. Une interruption materielle n'invalide pas les
observations deja sauvegardees.

Corrections pour les nouveaux traitements : identifiants textuels preserves,
pas de rejet CSV silencieux, une normalisation explicite par analyse, timings
d'extrema ex aequo indefinis, et checkpoints atomiques avec etat aleatoire.
Les conventions sont versionnees ; les alertes de qualite utilisent maintenant
MAE greedy / IQR du contexte. Les formules et coefficients du score FPA restent
inchanges.

Les anciennes figures peuvent etre affectees par la conversion numerique de
`series_id`. Leur validite doit etre verifiee individuellement contre le CSV ;
ce n'est pas une raison de jeter les runs correspondants.

Ces corrections ne suppriment pas les biais scientifiques : top-k tronque,
amplitude du saut de token, dependance des fenetres et absence d'un controle
independant a token identique. Les correlations par branche et par point de
branchement restent descriptives, pas une preuve d'independance ni de causalite.

## 0. Biais observe dans le refinement courant

Run concerne :

```text
result/refinement_faster_global_20260728_125930
```

Problemes observes :

1. le run est partiel,
2. la couverture actuelle est surtout `ercot` et `exchange_rate`,
3. `selected_refinement_windows.csv` ne correspond pas parfaitement aux fenetres
   deja presentes dans `chronos_scan_summary.csv`,
4. le run utilise encore `window_scale`, pas la normalisation `context_iqr`,
5. les conclusions sur Dominick et m4_daily ne sont pas encore possibles.

Consequence :

> Ce run est excellent pour guider les hypotheses, mais il ne doit pas encore
> etre presente comme confirmation finale.

Controle ajoute au code :

```text
en reprise, la selection existante est reutilisee si elle existe
les append CSV suivent le schema deja present
```

Controle a ajouter :

```text
schema_version + rapport automatique de completion + alerte si la selection
courante diverge du summary deja ecrit
```

## 1. Branches base dans les statistiques

Les lignes :

```text
is_base_token = True
```

correspondent a la branche base forcee. Leur score est normalement zero ou
quasi zero.

Pour analyser les vrais shifts, filtrer souvent :

```text
is_base_token = False
```

## 2. Biais d'echelle

Le score brut depend des unites de la serie.

Regle :

```text
score brut = analyse intra-dataset ou intra-fenetre
score normalise = comparaison globale
```

Score global recommande pour les nouveaux runs :

```text
context_iqr_scaled_progressive_token_bin_forking_score
```

Pourquoi :

```text
context_iqr = q75(context) - q25(context)
```

Cette unite est robuste aux outliers et ne depend pas directement du futur que
l'on essaie d'expliquer.

## 3. Contextes plats ou quasi plats

La normalisation par `context_iqr` peut devenir non exploitable si le contexte
est plat.

Controle :

1. sauvegarder toutes les variantes normalisees,
2. verifier combien de lignes ont `context_iqr` nul ou presque nul,
3. si `context_iqr` est defectueux pour un run, basculer tout le run vers une
   autre colonne, par exemple `context_std` ou `window_scale`.

Important :

> On ne doit pas comparer ERCOT avec `context_iqr` et exchange_rate avec
> `context_range` dans la meme figure principale. Une figure = une unite de
> normalisation.

## 4. Series courtes et adaptive context

Avec :

```text
--adaptive-context
```

certaines series courtes produisent seulement :

```text
window_id = 0
window_start = 0
```

Risque :

> Le dataset semble produire des gros shifts, mais on observe seulement le debut
> ou une seule zone de la serie.

Controle :

1. toujours reporter `context_len`,
2. separer series courtes et longues,
3. verifier la distribution de `window_start`.

## 5. Bruit de sampling

Avec peu de samples, les quantiles sont instables.

Interpretation pratique :

```text
num_samples = 5   debug
num_samples = 10  exploration rapide
num_samples = 40  refinement raisonnable
num_samples = 100 confirmation plus stable
```

Controle :

> Les top fenetres doivent etre rerun avec plus de samples avant conclusion
> forte.

## 6. Score trop composite

Le score global melange plusieurs dimensions :

```text
amplitude
shift max
widening
amplification
shape break
persistance
croissance monotone
```

Ce n'est pas faux, mais cela peut masquer la raison exacte d'un gros score.

Controle :

1. regarder les composantes du score,
2. separer `instant_forking_score`, `persistent_forking_score` et
   `progressive_forking_score`,
3. ne pas interpreter le score global comme une mesure unique d'incertitude.

## 7. Top-k limite

Le scan teste surtout les top-k tokens.

Risque :

> On mesure surtout les alternatives plausibles de Chronos, pas tous les tokens
> possibles.

Controle :

1. garder top-k pour le scan large,
2. faire un refinement plus dense sur les fenetres sensibles,
3. ajouter ensuite des tokens random ou des rangs plus profonds.

## 8. Comparaison single vs bundle

Les resultats propres actuels sont en `single`.

Risque :

> Conclure trop vite sur la dynamique multi-step alors que seul un token est
> force.

Controle :

1. utiliser `bundle` sur un sous-ensemble top-ranked,
2. comparer si le bundle confirme ou change la typologie.

## 9. Qualite de la base Chronos

Un fort shift est plus difficile a interpreter si Chronos base est deja mauvais.

Colonnes utiles :

```text
base_mae_over_window_scale
base_forecast_bad
chronos_base_quality_warnings.csv
```

Quadrants utiles :

```text
fort shift + faible erreur
fort shift + forte erreur
faible shift + forte erreur
faible shift + faible erreur
```

## 10. Controles experimentaux a ajouter

Priorites :

1. fenetres random,
2. plusieurs seeds de sampling,
3. rerun top windows avec plus de samples,
4. comparaison par dataset,
5. series synthetiques simples,
6. tokens random hors top-k,
7. single vs bundle,
8. series courtes vs longues,
9. verification automatique de schema avant reprise.
