# FPA : valeur incrémentale et estimation de conséquences

**27 novembre 2026 — campagne bornée terminée, H2 partiel.**
H1 complet320/320, H2 complet29/36. Analyse version2, sans nouvelle inférence;
les29 tableaux numériques de la première analyse sont conservés à l'identique.
Le dépassement de temps de24,883 s et l'appariement H2 manqué restent des échecs
explicites, distincts de l'intégrité mathématique validée.

Run : `result/incremental_campaign_20261126T132759Z/` (RUN).
Résultats courants : `RUN/analysis_v2/`. Preuves : `integrity_audit.json`,
`analysis_freeze.json`, `analysis_v2_freeze.json`, `analysis_complete.json`.
Branche `main`, HEAD avant commit chercheur
`a5b6ef6743832f09bfa096078104b727dc84f373`; modifications locales non commitées.

## Part I — Évaluation scientifique

**La narration C, résultats limités, est la mieux soutenue.** Cette campagne
n'établit ni une amélioration robuste du risque prédictif par FPA, ni un avantage
pratique démontré pour estimer des probabilités à coût égal.

1. **Au-delà de SGA :** M3 améliore légèrement l'AURC MASE sur le test interne,
   mais dégrade Weather OOD. Les intervalles primaires incluent zéro.
2. **Estimation d'événements :** aucun avantage convaincant observé. Le contrôle
   MC prévu à coût apparié dépense environ1,88 fois le temps de Neyman;
   la comparaison primaire ne valide donc pas une conclusion à coût égal.
3. **Valeur pratique :** les petits gains H1 ne compensent pas un coût composé
   moyen M3 environ5,15 fois M1; la baseline à sampling naturel supplémentaire
   reste compétitive.
4. **Robustesse :** résultats hétérogènes par dataset, normalisation et population.
   H2 est réduit à9/9/9/2 sources, avec un seul dataset Weather entièrement OOD.
5. **Inexpliqué :** séparation entre faible signal décisionnel, bruit Monte Carlo,
   représentation des features et coût du pilote. L'absence de résultat positif
   ne prouve ni équivalence ni impossibilité générale.

Les conclusions portent sur Chronos-T5-mini original, C512/H32 et **q50**
(masque valide, température1, top-k50 avec égalités, top-p1). Elles ne sont
pas une conclusion sur tous les TSFM, tous les horizons ou le système réel.

## Part II — H1 : information prédictive incrémentale

### Cohorte et modèle de risque

| Dataset | Train | Validation | Test interne | Test OOD |
| --- | ---: | ---: | ---: | ---: |
| London Smart Meters | 38 | 13 | 13 | 0 |
| Electricity Hourly | 38 | 13 | 13 | 0 |
| Pedestrian Counts | 19 | 6 | 7 | 0 |
| Traffic | 58 | 19 | 19 | 0 |
| Weather | 0 | 0 | 0 | 64 |
| Total | 153 | 51 | 52 | 64 |

Une fenêtre par ID original, sélection contextuelle figée, périodes cibles
train/validation/test disjointes dans chaque dataset, aucune identité partagée.
Les320 cibles sont finies; alignement exact contexte/32 valeurs suivantes et
timestamps vérifié sur les349 fenêtres H1/H2 analysées.

Tous les modèles partagent le forecast moyen naturel N60, en trois N20.
M0 utilise contexte, incertitude naturelle et statistiques locales; M1 ajoute
SGA; M2 ajoute FPA à M0; M3 ajoute FPA à M1. Même Ridge sur log1p(perte),
grille alpha0,1/1/10/100, standardisation train uniquement, choix validation,
sans réentraînement sur validation ni accès test pour sélectionner les modèles.
Les prédictions de pertes ne sont pas des probabilités de risque calibrées.

Les lags MASE sont fixés par fréquence :48 London,24 Electricity/Pedestrian/Traffic,
1 Weather, selon les conventions [GluonTS](https://github.com/awslabs/gluonts/blob/dev/src/gluonts/time_feature/seasonality.py).
Le dénominateur est calculé sur le contexte C512. MAE/IQR est apprise et évaluée
séparément; MAE brute est rapportée uniquement à l'intérieur de chaque dataset.

### Comparaisons primaires

NEAURC plus petit est meilleur; delta=M3−M1. IC95% : bootstrap999 des datasets
puis des IDs, modèles entraînés maintenus fixes. Les dépendances physiques
entre canaux et la variabilité de réentraînement ne sont pas modélisées.

| Perte / test | M0 | M1 | M2 | M3 | Delta M3−M1 [IC95%] |
| --- | ---: | ---: | ---: | ---: | --- |
| MASE, interne N52 | 0,8791 | 0,9191 | 0,8797 | 0,8681 | −0,0510 [−0,4285;0,2058] |
| MASE, Weather N64 | 0,1933 | 0,2144 | 0,2828 | 0,2685 | +0,0542 [−0,0339;0,1462] |
| MAE/IQR, interne N52 | 0,2544 | 0,2606 | 0,2348 | 0,2436 | −0,0170 [−0,1439;0,1206] |
| MAE/IQR, Weather N64 | 0,0987 | 0,0980 | 0,1183 | 0,1173 | +0,0193 [−0,0077;0,0756] |

Sur MASE interne, AURC M1=0,6785 contre M3=0,6615 : réduction relative2,51%.
Sur Weather,0,6901 contre0,7093 : dégradation2,77%. Les p unilatéraux primaires
sont0,5 et0,8925, tous deux1 après Holm sur la famille de trois tests.
Le test interne a seulement quatre blocs dataset : sa résolution est grossière,
sans preuve d'équivalence. Weather n'est qu'un dataset; les64 IDs ne garantissent
pas64 stations indépendantes.

Les différences internes changent par dataset : M3−M1 NEAURC vaut environ
−0,322 London,−0,433 Pedestrian,+0,125 Electricity,+0,053 Traffic.
À couverture25%, le risque MASE interne M3=0,632 est plus élevé que M1=0,594,
malgré l'AURC globale légèrement meilleure. Le retrait d'une seule source
fait varier le delta interne de−0,107 à+0,108 : le signe n'est pas stable.

### Bruit, supervision et contrôles

F1 W1 médian=0,0800 IQR, contre0,0533 pour le contrôle indépendant same-token.
Ce niveau de bruit interdit d'interpréter chaque petite distance comme un effet.
Le composant entre tokens à produits croisés est négatif sur151/320 fenêtres;
ces estimations non biaisées et bruitées sont conservées, sans troncature.
Leurs médianes entre tokens et intra-token sont0,000376 et0,0518.

SGA brut sur le test interne a NEAURC MASE1,1756, contre0,9191 après calibration
avec les features M0. Ce gain n'est pas une contribution spécifique de FPA.
Sur MAE/IQR interne, la baseline apprise d'échelles/métadonnées obtient0,1976,
meilleur que M3=0,2436. Les coefficients Ridge sont descriptifs, pas causaux.

F1–F6 sont figées : moyenne W1/ED et null, pondérations q50/préfixe, quantile/max,
décomposition de variance, persistance et sensibilité aux quatre événements.
W1/ED excluent la coordonnée forcée et utilisent22 pas post-fork. F2 ne somme
pas des positions sparse comme des probabilités naturelles disjointes.
**F6 à b9 peut inclure le saut forcé pour les excursions.** Le contrôle
secondaire pré-cibles M3_cheap−M1_cheap ajoute les mêmes six statistiques
bon marché aux deux modèles. Il améliore Weather MASE de−0,0378 NEAURC
[−0,0777;−0,0069], mais pas Weather MAE/IQR (+0,0062).
Il ne remplace pas le résultat primaire défavorable.

### Coût réel et sampling supplémentaire

| Modèle | Coût composé moyen / fenêtre |
| --- | ---: |
| M0 | 6,99 s |
| M1 | 9,72 s |
| M2 | 47,35 s |
| M3 | 50,08 s |

Les composants incluent génération naturelle, setup, replay d'entropies SGA,
graphe, génération FPA et features. Ce sont des décompositions d'une collecte
commune, **pas quatre benchmarks autonomes**. La table distingue coût composé,
chargement complet par fenêtre et total physique des processus, avec startup,
I/O et tentatives interrompues; ne pas sommer les coûts partagés entre méthodes.

Sur les160 IDs de coût préfixés,736 trajectoires naturelles supplémentaires
coûtent en moyenne0,978 fois l'incrément FPA;157/160 sont dans[0,8;1,25].
Tous les modèles sont recalibrés sur les mêmes splits de ce sous-ensemble.
M3−M1_extra_MC MASE : +0,0232 NEAURC interne [−0,3704;0,6256],
−0,0773 Weather [−0,3239;0,0967]. Sur MAE/IQR : +0,0316 interne et−0,0544
Weather, avec IC traversant zéro. Aucun avantage robuste face à plus de
sampling naturel. SGA reste ici calculé sur les trois N20 initiaux.

## Part III — H2 : estimation de probabilités

### Estimand, allocations et exécution

Les événements portent sur les coordonnées absolues H32, avec seuils contextuels :
E1 minimum8..31≤dernier−IQR; E2 maximum8..31≥dernier+IQR;
E3 moyenne24..31≤dernier−0,5 IQR; E4 direction terminale différente du greedy,
avec bande neutre±0,05 IQR. La même définition vaut dans toutes les strates.
Task A estime leur probabilité **sous q50**; Task B la confronte au futur réel.

P1 partitionne b0 en greedy, deux alternatives et résidu complet. P2 utilise la
première déviation du greedy aux positions0..4 : alternative principale,
autres non-greedy et continuation cinq-greedy. Les poids sont exclusifs,
exhaustifs et de somme1; le sampler conditionne sur tout l'historique.

Estimateur stratifié : Σwⱼp̂ⱼ, variance conditionnelle Σwⱼ²sⱼ²/nⱼ.
Le pilote N4 par strate est indépendant des productions et fixe les allocations
uniforme/proportionnelle/Neyman-coût. Il est entièrement facturé à chaque
estimation Neyman/IS individuelle. Les répétitions sont indépendantes
**conditionnellement au même pilote**, sans mesure de variabilité du repilotage.
L'IS optionnel utilise le rapport exact w/a, sans auto-normalisation ni
troncature de l'estimation Task A; sa proposition est inspirée de la variance,
sans revendication d'optimalité. Voir [Owen](https://artowen.su.domains/mc/Ch-var-basic.pdf)
et [importance sampling](https://artowen.su.domains/mc/Ch-var-is.pdf).

29/36 fenêtres complètes :9 London,9 Electricity,9 Weather,2 Traffic;11 ont
dix répétitions, les18 autres une. Les identités sont disjointes de H1.
L'arrêt a suivi l'ordre groupé par dataset, **écart au retrait équilibré demandé**.
Les7 autres fenêtres restent conservées hors analyse, sans remplacement.
Les résultats sont conditionnels à ce sous-ensemble, pas une prévalence générale.

### Erreur et temps mesurés

À l'ancre480, mêmes29 sources, quatre événements moyennés par source :

| Méthode | RMSE vers référence N2000 | Temps variable moyen, pilote inclus |
| --- | ---: | ---: |
| MC naturel N480 fixé | 0,01191 | 27,71 s |
| P1 proportionnelle | 0,01379 | 28,79 s |
| P2 uniforme | 0,03405 | 36,08 s |
| P2 proportionnelle | 0,01493 | 31,04 s |
| P2 Neyman-coût | 0,01638 | 25,29 s |
| IS sur strates | 0,01793 | 22,45 s |
| MC destiné à apparier Neyman | 0,00974 | 47,78 s |

Le dernier contrôle dépense1,879 fois le temps de Neyman, **0% des paires
respectent l'appariement prévu[0,8;1,25]**. Le coût naturel du pilote technique
ne représente pas le débit réel ultérieur. Le primaire observé donne
delta MSE=+0,000174 [0,000058;0,000306], ratio RMSE1,682, et gain sur4/29 sources.
Il s'agit d'une comparaison contre un MC plus coûteux; **aucune conclusion
confirmatoire à coût égal n'est admissible**, même si p primaire=1 (Holm=1).
Les mentions «matched» dans les noms de fichiers/légendes décrivent l'intention
du protocole; les temps réellement obtenus gouvernent l'interprétation.

Le contrôle MC N480 fixé est une comparaison secondaire déjà collectée :
temps moyen environ10% supérieur à Neyman, RMSE environ27% inférieur.
La fraction de répétitions dans la tolérance de coût, moyennée par source,
est92,1%. Cela ne remplace pas le primaire manqué; cela n'apporte pas non plus
d'argument favorable à un avantage de Neyman dans cette réalisation.

Les ancres60/120 sont infaisables pour Neyman/IS après coût du pilote.
Neyman240 n'est faisable que sur25 sources. Les figures annoncent les effectifs;
ne pas comparer des moyennes sur des cohortes différentes comme si elles
étaient appariées. Les pools MC réutilisés entre ancres/méthodes induisent
de la covariance; ils ne sont pas des réplications supplémentaires.

### Références, événements rares et futurs réels

Chaque référence N2000 contient deux N1000 indépendants, après gel des allocations.
40/116 couples source–événement ont zéro succès; deux ont2000 succès.
Zéro n'est pas une probabilité nulle : borne supérieure unilatérale95%≈0,00150.
La variance moyenne estimée de référence est0,0000321. Les différences de MSE
partagent la même référence indépendante; les corrections de variance restent
signées. Les intervalles Hoeffding sont ponctuels, pas simultanés; leur accord
avec une référence finie n'est pas la couverture par rapport à une vérité exacte.

Contre chacun des deux blocs N1000, MSE Neyman≈0,000277/0,000328 et MC destiné
à l'apparier≈0,000132/0,000126. La tendance observée survit à ce changement
de référence, tandis que le défaut de coût subsiste.
61/116 probabilités de référence sont<0,05; les erreurs relatives ne sont
rapportées que si p̂≥0,01. Aucun N10000 supplémentaire n'a été exécuté.

Task B, une issue réelle par source et événement, donne pour la référence
Brier moyen0,1561 : E1=0,0616, E2=0,2171, E3=0,1488, E4=0,1968.
Ces29 issues par événement et les bins de fiabilité sont exploratoires;
aucune amélioration de calibration du TSFM n'est établie.
L'IS est projeté dans[0,1] uniquement pour Task B, avec indicateur explicite.

### Illustrations positives et négatives

La dernière page du PDF sélectionne **après analyse** le plus petit et le plus
grand delta MSE au primaire. Ce ne sont pas de nouvelles validations.

- Weather `ae8ff7796a…` : MSE Neyman0,0000641 contre MC0,0001269,
  temps24,68/44,99 s; référence E1 proche de0,96 et E3 proche de0,84.
  Les trajectoires de référence s'étendent approximativement de1 à11,
  autour d'un greedy presque constant à7,4.
- Electricity `ac38382fa9…` : MSE0,001204 contre0,000337,
  temps25,38/46,38 s; branches de référence autour de92 à128, greedy≈96.
  L'incertitude sur E2/E3 illustre un cas où le sampling naturel gagne.

Les six figures ont été inspectées : risque-couverture, deltas et IC,
coût–erreur global, comparaison primaire aux coûts réellement obtenus,
blocs de référence/Task B, et trajectoires extrêmes. Les tables brutes,
pas la sélection de ces images, définissent les résultats.

## Part IV — Interprétation et audit des biais

**Constat1 — information incrémentale H1 non robuste (observé).**
Le petit gain interne change de signe OOD et varie avec le retrait d'une source.
Cela suggère une utilité limitée du modèle FPA actuel; faible puissance,
features et décalage de domaine restent des explications concurrentes.
L'hypothèse d'une information décisionnelle utile n'est pas réfutée en général.
Aucune contribution de fiabilité TSFM n'est démontrée.

**Constat2 — efficacité H2 non démontrée (observé).**
Les courbes ne montrent pas de gain net, mais l'appariement primaire échoue.
Le coût du pilote et le mauvais débit anticipé sont des explications
concurrentes à l'absence d'information dans les premiers tokens.
La stratification est classique : une nouveauté TSFM exigerait un avantage
empirique supplémentaire, absent ici. Le diagnostic unique proposé enPart V
est le prochain contrôle informatif, sans nouvelle inférence.

**Constat3 — bruit et échelle déterminants (observé/suggéré).**
Distances null substantielles,151 composantes entre tokens négatives et
changements MASE/MAE-IQR montrent des limites de mesure et de normalisation.
L'attribution causale à des tokens importants reste hypothétique.
[Forking Paths](https://arxiv.org/abs/2412.07961) motive l'analyse des décisions;
[Forking Fast](https://arxiv.org/abs/2608.19611) souligne le bruit d'échantillonnage.
Nous n'avons pas reproduit son modèle de lissage. Le port
[SGA](https://arxiv.org/abs/2609.28582), auteur épinglé avec fixtures,
est adapté ici à H32/q50; ce n'est pas une reproduction de tous ses benchmarks.

**Constat4 — portée de généralisation limitée (observé).**
Les fractions moyennes de coordonnées cibles potentiellement antérieures à
la coupure de pré-entraînement sont89,8% London,84,8% Electricity,96,9% Pedestrian.
«Test intact» concerne le modèle de risque, pas une absence garantie
d'exposition du TSFM. Traffic/Weather sont désignés zero-shot par la source.
Weather peut regrouper des variables corrélées sans stations identifiées.
H2 incomplet et quatre blocs dataset ne soutiennent aucune généralisation large.

### Contrôles mathématiques, provenance et incidents

L'audit valide30 225 flux Torch distincts,833 164 trajectoires finalisées
(pilote inclus), les scopes/préfixes/supports, F1–F6 recalculées,2 026 cellules
stratifiées/IS reconstruites, références et fréquences de partition.
Les cas synthétiques ont probabilité0,24 connue, variance stratifiée0,032
et variance IS0,0672; une estimation IS peut dépasser1 sans être tronquée.
Écart maximal de masse float32 brut2,9622e-7, sous8 epsilon float32.
Ces contrôles vérifient les estimands implémentés; ils ne prouvent pas l'absence
de tout biais de dessin ni une contribution scientifique.

Conservation :11 611 fichiers préexistants, tailles/mtime/SHA256 inchangés,
index Git et `.gitignore` inchangés. Les interruptions Windows/softmax et
la reprise autonome restent conservées et facturées. Temps enregistré
**57 624,883 s >57 600 s** : échec de conformité, pas une autorisation implicite.
Le superviseur contrôle le plafond entre opérations; il ne fournit pas une
coupure temps réel indépendante des I/O. Aucun modèle n'a été relancé.

Le premier calcul offline a terminé ses29 tables, puis échoué sur un
`yerr` négatif d'arrondi (minimum−2,22e-16) dans un graphe Wilson.
Source, gel, log et inventaire d'origine sont préservés dans
`analysis_v1_failed_plot_provenance/`. La version2 corrige seulement la
longueur tracée à tolérance1e-12; un écart substantiel déclenche toujours une erreur.
Les29 fichiers numériques sont identiques par SHA256; aucun ajustement de
features, de fit, de test ou de sélection après lecture des cibles.
La suite finale et sa régression graphique passent **320 tests en217,35 s**,
preuves dans `gate_E_final_tests.*`.

Quatre acquisitions publiques,229 429 048 octets, export HF épinglé
`eeecad0b82a8c237e212ce6f8d1abecb513e2cec`, licences originales CC-BY4.0 :
[Weather](https://zenodo.org/records/4654822),
[Electricity](https://zenodo.org/records/4656140),
[Pedestrian](https://zenodo.org/records/4656626),
[Traffic](https://zenodo.org/records/4656132).
Chronos-T5-mini épinglé `bd6a4fde8403b8469acd0abd52852b29dbe61c7b`;
CPU float32, aucun entraînement TSFM, dépendance ou nouveau modèle.

## Part V — Décision Paper1 et suite unique

**A, fiabilité : non soutenue actuellement.** Les gains secondaires localisés
ne remplacent pas le test incrémental primaire ni la comparaison de coût.

**B, estimation de conséquences : non démontrée.** Poids et estimateurs sont
validés, mais cela ne suffit pas pour une contribution pratique. Le défaut
d'appariement empêche la conclusion primaire à coût égal.

**C, résultats limités : retenue.** La campagne apporte une mesure plus fiable
des limites et des coûts, avec des contre-exemples; elle ne suffit pas seule
à revendiquer une méthode supérieure pour Paper1.

**Unique recommandation, à soumettre à la revue chercheur :** diagnostic offline
de l'appariement H2, sur les pools naturels déjà sauvegardés, sans nouveaux tirages.
Figer d'abord une règle choisissant les préfixes de pools uniquement par leurs
temps de génération et leurs frontières enregistrées, puis recalculer les
comparaisons appariées sur les mêmes sources et les quatre événements inchangés.
Coût maximal proposé :2 h d'implémentation/revue,30 min de CPU offline,
**0 s de modèle**, sans téléchargement. Données déjà vues : résultat exploratoire,
aucune nouvelle preuve confirmatoire. Critères d'échec : moins de80% des sources
dans la tolérance[0,8;1,25], ou absence d'une réduction RMSE d'au moins10%
avec intervalle de delta MSE entièrement négatif. Ne pas changer ces critères
selon les résultats. **Non exécuté; approbation du chercheur après revue requise.**

Livrables de revue : `cohort_and_splits.csv`, méthodologie/configurations gelées,
features/forecasts/prédictions/modèles/coûts H1, événements/références/variances/
coûts H2, tests primaires et PDF de six pages. Les copies explicitement choisies
sont regroupées dans `docs/chatgpt-handout.zip`; les archives restent exclues.
Aucun staging, commit ou push par Codex. Arrêt de cette campagne après handoff.
