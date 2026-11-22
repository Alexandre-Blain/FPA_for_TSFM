# Pilote FPA : précision Monte Carlo et préparation de campagne

**22 novembre 2026 — analyse hors modèle terminée; campagne non autorisée.**

**Recommandation soumise à revue : exploration dense N20 sur davantage de séries,
puis validation indépendante N60 de contrastes présélectionnés.** N20 permet de
cartographier des candidats, mais ne fournit pas un classement fiable des
branches. N40/N60 réduisent sensiblement le bruit; ce pilote ne démontre pas
qu'un de ces N suffise pour tous les contrastes. Les données établissent aussi
quelques différences conditionnelles qui survivent à une validation indépendante.

Le [rapport de collecte](LOCAL_PILOT_REPORT.md) et ses
[preuves originales](LOCAL_PILOT_EVIDENCE.json) restent inchangés. Le
[protocole approuvé](../research/FPA_PROTOCOL_EXPLORATORY.md) reste N20.
Ce rapport distingue une recommandation d'une décision du chercheur.

## Données, provenance et conventions

Analyse partie d'un arbre propre, branche `main`, HEAD
`ad64422b973aa77a33e99827ced9bdae903b15cb`. Aucun Git d'écriture exécuté.
Le HEAD de **collecte**, différent, est
`62271b156db9d56ffbbd673d24b4d111ccd75f7e`, avec sources de collecte archivées.
Chronos-T5-mini, révision `bd6a4fde8403b8469acd0abd52852b29dbe61c7b`,
C512/H32, CPU float32, q50/température1/top-p1, sélection90 % cap8 et résidu.
Gel global `2026-11-20T19:30:30.832303+00:00`;
fin de collecte `2026-11-20T19:50:12.035309+00:00`.

Source : `result/local_pilot_20261120T184035Z/`. Les dix cellules complètes
contiennent **704 ensembles, 17 280 trajectoires**, six séries originales,
dont 10 200 trajectoires primaires et 186 alternatives. T000063 et SOUTHERN ont
chacune trois graines N20 : 20261120/21/22. Toutes les empreintes du gel et du
checkpoint global, les fichiers liés aux dix marqueurs complets, les ensembles,
préfixes, contextes, métriques et événements reconstruits passent les contrôles.
Avant pooling, tous les champs d'identité conditionnelle, hormis la graine,
et les listes de candidats/poids sont vérifiés identiques. **704 identifiants RNG
et 704 graines dérivées distincts** : indépendance prévue par la construction,
conditionnellement au modèle et au contexte; aucune preuve d'indépendance entre séries.
Une égalité de valeurs due à la quantification n'est pas un trajet dupliqué :
l'identité d'un tirage est son ensemble et son indice de ligne.

Les nouveaux fichiers sont uniquement dans
`result/local_pilot_20261120T184035Z/offline_analysis_20261122/`.
`AUTHORIZED_REQUEST.txt`, `analysis_plan.json`, `provenance.json`, les snapshots
du code et `execution_*.json` donnent demandes, choix, hashes et temps.
L'empreinte initiale couvre les **2 898 fichiers préexistants sous data/result**;
la vérification finale est dans `preservation_after.json`. L'ancienne
`analysis/`, les manifestes, captures et trajectoires ne sont pas réécrits.
Aucune inférence, aucun téléchargement et aucune installation.

Choix fixés avant les extensions : graine de rééchantillonnage20261122,
**399 bootstrap de trajectoires entières**, références rééchantillonnées une fois
par fork et réutilisées pour tous ses contrastes, résidu pondéré, objets réutilisés
identiquement dans CPD. Les **3 999 permutations** par comparaison échangent des
trajectoires complètes; 399 initialement envisagées ne permettaient pas de résoudre
le seuil Holm0.05/69, d'où l'augmentation avant leur exécution. Les intervalles
percentiles 2.5–97.5 % sont **conditionnels au pool fini**, ponctuels,
exploratoires et sensibles au biais de distance près du null. Ils ne constituent
ni une garantie de couverture, ni des intervalles entre séries. Aucune permutation
ne traite les horizons ou les branches comme des observations indépendantes.

## 1. Reproduction et divergence avec les nombres préliminaires

Les distances sont recalculées depuis les valeurs individuelles, puis comparées
aux résultats JSON et CSV historiques : écart relatif maximal `5.93e-14` aux
mesures JSON, écart absolu maximal `2.17e-12` aux CSV, compatible avec l'arrondi.
**60/186** W1 complets ≤ leur null; **98/186** W1_relative22 ≤ comparateur
persistant et **91/186** ≤ comparateur AR1 sont reproduits.

| Série | Médiane W1 brut, suffixe complet | ED brute | W1 brut du null, répété par alternative |
| --- | ---: | ---: | ---: |
| T000063 | 24.56685 | 8.54433 | 18.45471 |
| T000049 | 67.44672 | 21.51006 | 66.83053 |
| SOUTHERN | 42.00668 | 17.04088 | 29.06876 |
| FAR_WEST | 34.27910 | 13.47544 | 28.56595 |
| currency_1 | 0.007465 | 0.003196 | 0.005152 |
| currency_2 | 0.013571 | 0.005311 | 0.007511 |

Les 157/186, 59/60, 59/186 préliminaires n'ont pas de coupure early/late
précisée dans la demande. Ils ne sont pas reproduits par les trois définitions
déclarées ci-dessous. Leurs remplacements reproductibles sont :

| Définition, h=1 à b+1 | W1 alternative croissante | Null croissant, compté une fois/fork | W1alternative−W1null croissant |
| --- | ---: | ---: | ---: |
| **Principale : h1..8 versus les huit derniers du suffixe** | **160/186** | **58/60** | **61/186** |
| Sensibilité : h1..10 versus les dix derniers | 160/186 | 59/60 | 66/186 |
| Sensibilité : h1..11 versus h12..22 | 155/186 | 57/60 | 65/186 |

Une croissance signifie strictement moyenne tardive > moyenne précoce,
sans test. Ces nombres ne corrigent pas silencieusement les sorties historiques.
Voir [reconstruction](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/baseline_branches.csv),
[découpages](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/propagation_splits.csv).

## 2. A — Décision de précision N20/N30/N40/N60

Chaque rôle garde ses propres tirages. N20 : trois graines originales;
N30 : six pools ordonnés «20 d'une graine + dix premiers d'une autre», plus
un pool utilisant les dix derniers pour permettre **deux N30 disjoints**.
N40 : les trois couples de graines; N60 : toutes les graines.
Les indices exacts sont dans `precision_pool_designs.json`. Les combinaisons
qui partagent des lignes sont dépendantes. **Aucune réplication N40 contre N40,
ou N60 contre N60 indépendante n'est disponible.** Les comparaisons N20/N40
indépendantes utilisent les deux graines laissées de côté.

Support primaire de précision : **relative22**, b+1..b+22, distances/IQR.
Les médianes suivantes portent sur toutes les alternatives et les pools disponibles
à chaque N; les sept pools N30 ne sont pas sept réplications indépendantes.

| Fenêtre / métrique | N20 | N30 | N40 | N60 |
| --- | ---: | ---: | ---: | ---: |
| T000063 W1 | 0.05811 | 0.05445 | 0.05146 | 0.05057 |
| T000063 ED V | 0.02010 | 0.01564 | 0.01416 | 0.01273 |
| SOUTHERN W1 | 0.02500 | 0.02227 | 0.02074 | 0.01869 |
| SOUTHERN ED V | 0.01002 | 0.00746 | 0.00603 | 0.00497 |

Le bruit same-token baisse lui aussi : médiane W1 T000063 **0.04565→0.02914**,
SOUTHERN **0.01903→0.01180**; ED V **0.01259→0.00342** et
**0.00646→0.00206**. Une baisse avec N ne signifie donc pas disparition d'un
effet réel. L'ED U séparée réduit le biais : médianes alternatives T000063
**0.00470→0.00838**, SOUTHERN **0.00241→0.00243**. Elle peut être négative;
elle ne remplace pas l'ED V approuvée.

Largeurs médianes des intervalles bootstrap ponctuels : une chaîne canonique
imbriquée, graine0, puis ajout de graine1, puis graine2. Les intervalles
alternative−null conservent la covariance de référence; leurs différences
restent des diagnostics descriptifs.

| Fenêtre / métrique | N20 | N30 | N40 | N60 |
| --- | ---: | ---: | ---: | ---: |
| T000063 W1 | 0.07049 | 0.05658 | 0.05633 | 0.05211 |
| T000063 ED V | 0.05438 | 0.04140 | 0.03494 | 0.02683 |
| SOUTHERN W1 | 0.02271 | 0.01931 | 0.01663 | 0.01418 |
| SOUTHERN ED V | 0.02187 | 0.01477 | 0.01203 | 0.00855 |

**Observé :** N60 réduit ces largeurs d'environ26/51 % pour W1/ED sur T000063,
38/61 % sur SOUTHERN. La largeur T000063 W1 reste voisine de sa distance médiane.
N60 n'est donc pas une référence exacte. Le bootstrap conditionnel peut donner
des rangs plus stables que les vraies graines : T000063 W1, corrélation médiane
bootstrap au rang observé N20≈0.50, alors qu'une paire de graines vaut≈−0.10.

| Fenêtre / métrique | Corrélations des trois paires N20 | Top5 commun N20 | Corrélation des deux N30 disjoints | Top5 N30 | N20 graine0 versus N40 laissé de côté |
| --- | --- | --- | ---: | ---: | ---: |
| T000063 W1 | −0.101..0.446 | 0..1/5 | 0.064 | 1/5 | 0.210 |
| T000063 ED | −0.196..0.349 | 0..1/5 | 0.102 | 1/5 | 0.307 |
| SOUTHERN W1 | −0.122..0.380 | 2..3/5 | 0.495 | 2/5 | 0.414 |
| SOUTHERN ED | −0.061..0.340 | 2..3/5 | 0.439 | 2/5 | 0.376 |

Les top10 et tous les couples, avec leur indicateur d'indépendance, sont
exportés. Les 30 paires de sauts opposés disponibles sur ces fenêtres restent
instables : signe du contraste W1 conservé dans **9/20** paires T000063 et
**4/10** SOUTHERN entre les N30 disjoints; ED **9/20** et **3/10**.
Les intervalles des contrastes utilisent la même référence bootstrap des deux côtés.

La notion de «conséquent» n'a pas de seuil scientifique universel ici.
L'excès W1 est positif aux trois N20 pour seulement **16/40** et **16/29**
branches; le signe change pour beaucoup d'autres. À N60, **30/40** et **22/29**
intervalles d'excès W1 englobent encore zéro. «Proche du null» signifie
**non résolu**, sans preuve d'équivalence. Les comptes ponctuels ne sont pas
corrigés pour multiplicité et ne prouvent pas un effet.

Les permutations de contrôle offrent une vérification distincte : sur les69
branches calibrées N60, **11/69** rejettent l'égalité après Holm à5 % pour W1,
**11/69** pour ED, familles séparées par métrique. Aucun des20 nulls ne rejette
dans sa famille distincte. Ces tests évaluent l'égalité des lois conditionnelles,
pas une importance pratique ni une nouveauté au-delà de J.

Pour éviter de valider une sélection avec les mêmes données : top5 W1 et top5 ED
choisis **uniquement sur graine0**, union de12 branches entre fenêtres,
puis tests sur **graines1+2 N40 exclusivement**. Quatre branches passent Holm
sur ces12 dans chaque métrique : T000063 b6/token2152; SOUTHERN
b0/2229, b1/2227, b8/2173. Les autres restent non résolues.
Le top5 W1 de T000063 ne conserve que1/5 au top5 de validation; SOUTHERN3/5.
T000063 b3/2152 passe du rang W1=2 au rang37/40 : contre-exemple concret à
l'utilisation d'un grand N20 sélectionné comme preuve stable.

Pièces : [résumé par N](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/precision_review_summary.csv),
[rangs](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/precision_rank_comparisons.csv),
[incertitudes](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/precision_uncertainty.csv),
[contrastes appariés](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/precision_matched_contrasts.csv),
[permutations](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/precision_permutation_diagnostics.csv),
[validation indépendante](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/precision_holdout_top5.csv).

## 3. B — Propagation et dispersion

Les profils exportent, à chaque coordonnée strictement après b : W1alternative,
W1null, écart signé des moyennes Δμ, différence de variances ddof1, écart moyen
du null et écart-type de référence. La corrélation de rang null-W1/dispersion
de référence vaut **0.444 à0.690** à l'intérieur de chacune des six fenêtres,
avec chaque null compté une fois par coordonnée. Cette association reste
descriptive : horizons corrélés, mêmes références, variance de chaque moyenne.

**Suggéré :** la hausse fréquente de W1 reflète en partie une dispersion future
croissante et son bruit MC. **Non établi :** une amplification conditionnelle
générale. Soustraire W1null ne donne ni effet sans biais ni test : références
communes et variances conditionnelles différentes empêchent cette lecture.

G(h)=Δμ(h)/J est calculé seulement si
`|J| > max(0.01*IQR_contexte, 1e-12*max(1,max|contexte|))`.
**186/186** sauts primaires passent ce filtre; ce n'est pas une nouvelle sélection
de collecte. Les médianes de gains moyens early8→late8 sont :

| Série | Gain précoce → tardif | Inversions de signe entre moyennes early/late |
| --- | --- | ---: |
| T000063 | 1.075→1.565 | 6/40 |
| T000049 | 0.916→0.931 | 9/58 |
| SOUTHERN | 0.634→0.488 | 4/29 |
| FAR_WEST | 0.738→0.519 | 7/19 |
| currency_1 | 1.084→1.441 | 3/20 |
| currency_2 | 1.072→1.325 | 2/20 |

Ces inversions sont des signes estimés, sans preuve individuelle. Le modèle AR1
utilise le lag1 du contexte, Δμ attendu=J·lag1^h; le comparateur persistant utilise J.
Les anciens comparateurs translatent **le null indépendant**, avec la même
référence et le même bruit. Ils expliquent au moins aussi grand W1 pour98 et91
alternatives; aucune preuve de suffisance causale. Différences de variance et
gains complets restent disponibles dans les
[profils](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/propagation_profiles.csv).

## 4. C — Supports, W1/ED et morphologie

Les coordonnées sont indexées à partir de0. Les deux métriques sont calculées
sur **full b+1..31**, **relative22 b+1..b+22**, **absolute22 10..31** et
**final8 24..31**. Toutes excluent le token forcé pour b0..9.
W1 est la moyenne des distances marginales; ED garde la norme euclidienne/√L,
V-statistique, diagonales incluses, sans racine finale. L change la loi ciblée :
une ED final8 et une ED full ne sont pas la même quantité malgré la division/√L.

Corrélations de rang W1/ED primaires :

| Série | Full | Relative22 | Absolute22 | Final8 |
| --- | ---: | ---: | ---: | ---: |
| T000063 | .690 | .756 | .703 | .805 |
| T000049 | .942 | .938 | .946 | .933 |
| SOUTHERN | .964 | .971 | .963 | .920 |
| FAR_WEST | .968 | .961 | .942 | .961 |
| currency_1 | .968 | .973 | .949 | .985 |
| currency_2 | .955 | .955 | .938 | .916 |

L'accord global peut cacher des divergences : T000063 b9/2149 est classé
26e en W1_relative22 mais6e en ED. Il s'agit d'un exemple **post hoc**, pas d'une
preuve isolant la dépendance temporelle. Le passage relative22→final8 modifie
les rangs W1 : corrélations .574 FAR_WEST, .637 SOUTHERN, .682 T000063,
jusqu'à .925 T000049. Les divergences précoces et persistantes doivent rester distinctes.

Transformations déclarées : **centrage de chaque trajet par sa propre moyenne
sur le support**, et **différences consécutives à l'intérieur du support**, L−1
coordonnées. Le null subit exactement la même transformation. Cela enlève
respectivement le niveau constant du trajet et les niveaux cumulés; ni l'une
ni l'autre n'isole automatiquement la dépendance temporelle. Les trajectoires
centrées n'ont notamment plus une interprétation de niveau absolu.

Cas sélectionné sur graine0, validé sur les deux autres : **SOUTHERN b0/2229**,
J/IQR=.04182. En relative22 N40, W1=.04764 versus null=.01535;
ED=.03335 versus .00381. Après centrage, W1=.03585 versus .01367,
ED=.02108 versus .00398; après différenciation W1=.01454 versus .00687,
ED=.00637 versus .00202. Final8 brut W1=.07652 versus .02568.
**Suggéré :** ce cas ne ressemble pas seulement à une translation constante;
sa réponse moyenne et sa forme temporelle changent. Les tests Holm cités plus
haut concernent le support brut relative22, pas toutes ces transformations.
Une variation de pente moyenne ou de variance suffit encore à expliquer l'écart.

Contre-exemple utile : T000063 b3/2152, même procédure de sélection, N40 laissé
de côté W1_relative22=.03092 versus null=.03394; ED=.00595 versus .00603,
ED U=−.00117. Son classement N20 élevé ne survit pas à l'estimation indépendante.

Recherche exploratoire de différences de lois à moyennes similaires : aucun des69
candidats n'a **simultanément aux trois graines** une RMS du profil moyen ≤ celle
du null et une ED > celle du null. Ce critère est descriptif et conservateur,
pas un test d'équivalence des moyennes. **Non vérifié :** un contre-exemple robuste
où seule la structure jointe distinguerait les trajectoires. Les données ne
justifient pas de fabriquer ce résultat à partir d'une image.

Pièces : [distances et transformations](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/temporal_support_distances.csv),
[rangs par support](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/temporal_rank_comparisons.csv),
[cas indépendants](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/independent_case_supports.csv).

## 5. D — Lois continues, CPD et compensation locale

Issues reconstruites sur tous les chemins : Y31 brut; Y31−greedy31 signé;
sa valeur absolue; moyenne brute24..31; moyenne signée relativement au greedy;
moyenne des huit écarts absolus. Les distributions utilisent **q50 par groupe,
puis poids du groupe/N par trajet**, résidu compris. Les deux issues signées
et brutes correspondantes donnent le même W1 par invariance à translation :
ce ne sont pas deux découvertes. Les valeurs absolues ciblent d'autres lois.

P0..P9 sont les mélanges; P10 réutilise b9/greedy N20; P11..P15 sont les directs N60.
Les W1 cumulés P0→Pt et adjacents sont tous exportés avec rééchantillonnage
stratifié des groupes et réutilisation des objets communs. Les bornes bootstrap
de distances positives, parfois même au-dessus du point estimé, reflètent le
biais non négatif du bootstrap près de l'égalité; **leur borne basse >0 n'est
pas un test de changement**.

| Série primaire | W1 terminal P0→P15 / IQR | W1 de calibration P0 versus direct indépendant, même loi théorique | W1 terminal P10→P11 |
| --- | ---: | ---: | ---: |
| T000063 | .05812 | .06033 | .03488 |
| T000049 | 4169.51 | 563.11 | 647.84 |
| SOUTHERN | .03490 | .02657 | .01847 |
| FAR_WEST | .03397 | .03654 | .03511 |
| currency_1 | .25192 | .14985 | .08018 |
| currency_2 | .07031 | .06445 | .03196 |

Les dérives observées sont souvent du même ordre que les écarts entre estimateurs
indépendants d'une loi théoriquement identique. Cela ne prouve ni absence de
dérive ni égalité. T000049 reste dominée par l'échelle pathologique. La frontière
P10/N20→P11/N60 change l'erreur MC. En divisant le **même** P11 en trois blocs
disjoints N20, le W1 P10→P11 varie .03161..07303 pour T000063 et
.01359..02509 pour SOUTHERN, contre .03488/.01847 au direct complet.
P10 commun rend ces trois comparaisons dépendantes. Aucun change point établi,
aucun ajustement BEAST/PELT.

Pour les dix événements binaires fixés, l'identité locale est vérifiée avec
**la référence greedy du même fork des deux côtés** : mélange moins cette
référence = somme des contributions `q_i*(p_i-p_g)`, résidu inclus comme groupe
coarsened. Écart numérique maximal **2.23e-16**, résultat algébrique attendu.
À b0..8, le mélange de la position suivante est un **autre estimateur indépendant**
de la loi greedy actuelle; `independent_prefix_identity.csv` mesure séparément
leur écart. À b9/P10, c'est une réutilisation littérale, donc écart exactement nul.
L'identité n'est appliquée ni à W1 ni à ED.

Sur600 contrastes primaires fork×événement, **441** ont une somme absolue de
contributions non nulle; **92/441** ont une compensation descriptive d'au moins50 %,
définie `1-|somme c|/somme |c|`. Les médianes de compensation par série valent0 :
la compensation systématique n'est pas établie. Exemple exploratoire T000063
b4/événement terminal>.10 : somme absolue .07052, somme signée−.00071,
compensation99.0 %, demi-largeur Hoeffding ponctuelle .20179.
La contribution résiduelle atteint en valeur absolue .04209 : l'omettre n'est
pas défendable.

La concentration maximale médiane d'un groupe dans la somme absolue vaut
.47 à.73 selon la série, en excluant les sommes nulles. Les groupes partagent
la référence : les contributions ne sont pas indépendantes. Pour leur somme,
le coefficient de la référence est `−(1−q_g)`; le proxy Hoeffding est
`(1−q_g)^2/N_g + somme_non_g q_i^2/N_i`. Seulement **3/600** bornes ponctuelles
excluent zéro; aucune conclusion familiale n'est tirée. Des intervalles
bootstrap ponctuels en excluent58, différence qui souligne leur fragilité à
N20, particulièrement pour des événements rares. L'ancien résultat268/960 SE
nulles reste une limite; zéro observation ne démontre pas probabilité nulle.

Pièces : [dérives continues](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/continuous_cpd_drift.csv),
[directs indépendants](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/continuous_direct_overlap.csv),
[compensation et concentration](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/local_cancellation.csv),
[bornes des contributions](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/local_contribution_bounds.csv).
Les contributions signées individuelles et le diagnostic de frontière restent
dans `local_signed_contributions.csv` et `cpd_boundary_subsampling.csv`.

## 6. E — Part du token dans la variance future

Partition q50 : chaque token sélectionné, puis un groupe résiduel. À chaque
coordonnée, calcul de `within=somme w_i*s_i²`, et
`between_plugin=somme w_i*(m_i-mbar)²`. Pour des groupes indépendants, poids fixes :

```text
biais_between = somme_i w_i*(1-w_i)*s_i²/N_i
between_corrigé = between_plugin - biais_between
total_corrigé = within + between_corrigé
```

Les s² sont ddof1. Cette correction retire en espérance le bruit des moyennes
conditionnelles; elle peut être négative et n'est pas tronquée. Le ratio
between_corrigé/total_corrigé n'est pas lui-même un estimateur sans biais.
La partition est un **regroupement** des tokens : le résidu cache de la variance
entre ses propres tokens dans le terme within. La vraie composante entre tokens
peut donc être plus grande. Pas d'interprétation causale sur la série réelle.

| Série | Médiane fraction between corrigée, coordonnées24..31 | Médiane biais estimé / between plug-in |
| --- | ---: | ---: |
| T000063 | 1.49 % | 71.2 % |
| T000049 | 0.73 % | 85.6 % |
| SOUTHERN | 0.99 % | 78.1 % |
| FAR_WEST | 0.25 % | 92.9 % |
| currency_1 | 5.26 % | 32.8 % |
| currency_2 | 2.89 % | 45.9 % |

**120/480** estimations primaires fork×coordonnée finale sont négatives après
correction. Le within domine à ces horizons dans ce regroupement, sans établir
que le token n'importe jamais : des contrastes particuliers survivent à la
validation. Les profils incluent aussi la coordonnée forcée et chaque horizon;
le tableau utilise uniquement des coordonnées strictement post-fork.

Sur les dix positions par fenêtre, corrélations descriptives entropieq50 avec
fraction corrigée moyenne final8 : **.042 à.455**; p_sel **.067 à.455**.
La réponse moyenne quadratique final8 des alternatives a des associations
q50 hétérogènes **−.265 à+.579**, avec |J| **−.089 à+.243**, avec J signé
**−.258 à+.289**. Probabilité, géométrie des bins et saut restent confondus;
les mêmes références se répètent. Six séries et deux fenêtres par domaine ne
permettent pas une loi d'entropie générale ni une attribution au domaine/régime.

Pièces : [décomposition](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/future_variance_partition.csv),
`variance_group_contributions.csv`, `variance_entropy_associations.csv`,
`group_response_associations.csv` dans le même dossier.

## 7. Normalisation et limites de population

T000049 : IQR_contexte **.06500244**, mais écart-type3468.58, range9950.31,
IQR des128 derniers points9730.43. Le plateau occupe assez du contexte pour
maintenir l'IQR minuscule malgré le changement récent de niveau. Les médianes
W1alternative/null sont **1037.60/1028.12 IQR**, mais
**.01945/.01927 écart-type**, ou **.00678/.00672 range**.
Ces deux dernières sont des sensibilités nommées, jamais une modification du
protocole ni un motif pour exclure la fenêtre après coup. Les scores énormes
normalisés ne prouvent pas une sensibilité extraordinaire.
Voir [sensibilités explicites](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/normalization_sensitivity.csv).

Deux fenêtres ERCOT synchrones et deux devises sont corrélées; les strates de
diversité sont intentionnelles. Les réplications de graines ne créent aucune
nouvelle série. Aucune p-value de population n'est calculée en empilant les
branches, horizons ou bootstrap. Chevauchement avec l'entraînement Chronos et
exposition FPA antérieure hors des exclusions connues restent non vérifiés.

## 8. Cinq constats classés et falsificateurs

| Rang / niveau | Ce que le pilote établit | Alternative sérieuse | Falsificateur le plus informatif |
| --- | --- | --- | --- |
| 1 — Observé; classement N20 fiable réfuté sur ce panel | Rangs et contrastes appariés changent fortement; N60 améliore la précision sans résoudre tous les effets | Deux contextes calibrés seulement, variabilité entre contextes | Répliquer prospectivement rangs et contrastes présélectionnés sur un échantillon indépendant de fenêtres, N60 contre N60 indépendant |
| 2 — Observé puis suggéré | Null croît presque aussi souvent que l'alternative; dispersion et W1null covarient | Une vraie réponse moyenne peut aussi croître | Préfixer early/late, mêmes supports, tester Δμ et variance avec nouveaux flux et contrôles sur de nouvelles séries |
| 3 — Observé; interprétation de forme suggérée | Quatre branches sélectionnées sur graine0 survivent aux tests indépendants; SOUTHERN b0 résiste descriptivement au centrage | J, pente moyenne et variance suffisent; aucune dépendance jointe isolée | Comparateur numérique enrichi J/p/bins et famille de transformations fixée avant validation sur séries laissées de côté |
| 4 — Observé; généralisation non vérifiée | Compensation ponctuelle possible, rarement résolue; la variance between plug-in est fortement biaisée | Bruit des moyennes et événements rares créent compensation et between apparents | N indépendant équilibré par groupe, mêmes événements; tester contraste net et correction de biais sans sélectionner les ratios extrêmes |
| 5 — Observé; rupture structurelle non établie | Dérive continue souvent comparable aux écarts entre estimateurs d'une même loi; T000049 dominée par son IQR | Dérive réelle, normalisation atypique, frontière20/60 | Directs indépendants à taille harmonisée autour de positions fixées, sensibilités de normalisation préspécifiées |

## 9. Recommandation de campagne — à approuver

| Option | Décisions raisonnablement servies | Limite / coût |
| --- | --- | --- |
| Uniforme N20 | Cartographie dense, couverture/résidu, candidats et contrôles descriptifs sur plus de séries | Rangs individuels, asymétries fines et CPD confirmatoire non défendables |
| Uniforme N40 | Erreur MC réduite; compromis pour contrastes modérés | Aucune démonstration indépendante40/40; près du null, précision encore limitée |
| Uniforme N60 | ED nettement moins biaisée, contrôles réduits; meilleure estimation par contexte | Ne remplace pas plus de séries; aucune indépendance60/60 disponible; effets petits toujours non résolus |
| **Deux niveaux recommandés** | **N20 dense pour explorer, puis nouveau N60 indépendant pour valider des contrastes gelés et des témoins choisis aléatoirement** | Séparer strictement sélection et validation; coût ciblé et conclusion limitée au panel validé |

Conserver les six séries actuelles comme jeu de conception distinct. Le précédent
objectif de24 nouvelles séries,16 M4/4 ERCOT/4 devises, peut servir de **scénario de
coût**, pas de taille démontrée suffisante ni de nouvelle autorisation. Priorité
aux nouvelles séries originales prospectives plutôt qu'aux fenêtres voisines de
séries déjà observées; mesurer la dépendance commune entre ERCOT/devises et
conserver les clusters. La population locale restante est limitée53/5/5 : aucune
promesse de grande population indépendante. Les quatre fenêtres calibrées du
scénario antérieur ne peuvent suffire à estimer une prévalence générale.

Avant collecte : fixer séries/strates/origines, supports et early/late, tolérance
pratique des effets, dénominateurs sensibles, famille de tests, règles de
sélection et témoins non sélectionnés, événements et précision cible; distinguer
la validation de sélection MC et la généralisation sur nouvelles séries.
Proposition concrète de niveau2 : **au plus deux contrastes par nouvelle fenêtre**,
sélectionnés par une règle fixée, plus un témoin aléatoire si nécessaire;
nouveaux flux N60 pour référence/alternative/null, regroupement des références
si même b. Arrêt aux lots prévus et revue d'intervalles : absence de résolution
n'autorise pas une escalade automatique. Valider une paire opposée requiert
quatre groupes (référence, deux alternatives, null), pas deux tests indépendants.

Coûts mesurés : dix arbres modèle1165.002 s, dont génération inscrite dans les
704 manifestes **899.435 s**; groupes denses N20 **707.980 s**, directs N60
**191.455 s**. Collection totale967.463 s; chargement, parité, capture et
orchestration expliquent les écarts. Les NPZ d'ensembles occupent **2 534 360 octets**
compressés pour17 280 chemins; tokens+valeurs H32 seuls représentent384 octets
bruts/trajet, hors contexte/greedy/métadonnées. Les captures bornées occupaient
335.1 Mo : elles dominent le stockage.

Extrapolation indicative, géométrie moyenne des dix cellules, directs60 et
capture bornée inchangés, coût des groupes denses supposé proportionnel à N :

| Densité uniforme | Chemins par10 cellules de géométrie identique | Temps projeté10 cellules | Scénario24 cellules, marge×2 |
| --- | ---: | ---: | ---: |
| N20 | 17 280 | 1165 s mesurés | ~1 h33 |
| N40 | 29 760 | ~1873 s | ~2 h30 |
| N60 | 42 240 | ~2581 s | ~3 h27 |

Ce ne sont pas des benchmarks N40/N60 : batching, longueurs conditionnelles,
nombre de candidats et capture peuvent casser la proportionnalité. Le scénario
antérieur32 cellules N20 avec marge×2 reste≈2 h04. Pour24 fenêtres, un contraste
validé N60 référence/alternative/null représente180 chemins supplémentaires;
deux contrastes à b distincts360, soit8640 pour24 fenêtres. Au débit dense mesuré
~.0567 s/chemin, cela représente **~8 min10 de génération, ~16 min20 avec marge×2**,
hors chargement/parité/contrôles; une paire opposée240 chemins. Les témoins
supplémentaires ajoutent leur propre coût. L'estimation brute tokens/valeurs
de8640 chemins vaut3.32 Mo, sans NPZ/métadonnées.

Garder tous les chemins et la capture white-box bornée; ne pas multiplier les
captures par N. Scénario24 primaires : environ1.52 Gio de tensors capturés bruts,
plus chemins/métadonnées et espace de travail. Pic Job pilote1.259 Gio, sans
garantie de plafond futur. Ce pilote ne résout ni taille de population nécessaire,
ni précision d'événements rares, ni optimum universel N, ni information prédictive
généralisable au-delà de J/p/entropie, ni causalité interne.

## Vérification, fichiers et remise

**272 tests hors ligne passent en107.67 s**, un avertissement attendu de retry
de publication de dossier Windows. Huit nouveaux tests couvrent W1/ED V/U,
bootstrap par trajet, supports, mélanges pondérés, pooling/RNG, compensation,
correction du biais de variance et permutations avec ties/plus-one/Holm.
Le handout est régénéré avec le présent rapport et des pièces scientifiques
explicitement sélectionnées; aucun import automatique d'archives.
Contrôle documentaire : **58 Markdown,212 liens locaux, aucun lien cassé**.
Vérification ciblée finale : **17 tests passés en5.18 s** (mathématiques et handout).
Le script final a également été exécuté de bout en bout sur les données complètes.

Code nouveau : `code/chronos_fpa/analysis/chronos_offline_precision.py`,
`scripts/viz/analyze_chronos_pilot_offline.py`,
`tests/chronos_fpa/unit/test_offline_precision.py`.
Documents modifiés : index, statut, handoff, décisions append-only, tâche
courante, workflow, guides pratique/structure/tests. Le générateur de handout
donne priorité au présent rapport. Aucun algorithme de génération, protocole,
configuration d'expérience, fichier historique ou `.gitignore` modifié.

Reproduction sans modèle, dans le dossier d'analyse existant avec son plan :

```powershell
.\.venv\Scripts\python.exe scripts/viz/analyze_chronos_pilot_offline.py result/local_pilot_20261120T184035Z result/local_pilot_20261120T184035Z/offline_analysis_20261122
```

Trois pages de diagnostic :
[PDF courant](../../result/local_pilot_20261120T184035Z/offline_analysis_20261122/OFFLINE_REVIEW_FIGURES.pdf).
Les CSV détaillés sont l'appui des chiffres; le PDF reste une aide de lecture.
Le fichier `final_checks.json` local réunit tests, liens, préservation, liste
exacte des modifications et hashes du code final.

Commandes sélectives proposées **au chercheur seulement**, après revue :

```powershell
git status --short
git diff
git add -- code/chronos_fpa/analysis/chronos_offline_precision.py scripts/viz/analyze_chronos_pilot_offline.py tests/chronos_fpa/unit/test_offline_precision.py
git add -- docs/reference/LOCAL_PILOT_OFFLINE_ANALYSIS.md docs/README.md docs/research/FPA_STATUS.md docs/research/FPA_HANDOFF.md docs/research/FPA_DECISIONS.md codex-prompts/CURRENT_TASK.md
git add -- docs/research/README_WORKFLOW_V2.md docs/reference/README_CHRONOS.md docs/reference/PROJECT_STRUCTURE.md tests/README.md scripts/maintenance/prepare_chatgpt_handout.py
git diff --cached
```

Ne pas stage `data/`, `result/`, `.venv/`, ZIP ou handout. Message proposé :
`analysis: assess pilot Monte Carlo precision and campaign sampling`.
HEAD pré-commit=`ad64422…`; le prochain SHA reste inconnu jusqu'au commit du chercheur.

**STOP. Prochaine étape unique : revue scientifique ChatGPT–chercheur,45–60 min,
zéro trajectoire.** Fixer importance pratique et précision cible, puis accepter,
modifier ou rejeter le plan à deux niveaux. Tout nouveau tirage ou campagne
nécessite une autorisation distincte.
