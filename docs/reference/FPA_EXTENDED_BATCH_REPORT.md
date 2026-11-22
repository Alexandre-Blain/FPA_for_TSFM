# FPA — premier lot étendu et validation directe des baselines

**22 novembre 2026 — lot, validations et analyse terminés. STOP pour revue.**
Huit nouvelles identités, 24 blocs denses et 34 980 trajectoires ont été collectés.
Un N60 frais rejette les deux baselines pour SOUTH_C b0/2214; leur rejet conjoint
ne se reproduit pas sur son holdout N40. WEST b0/2222 reproduit trois des quatre
rejets de baselines. N60 réduit les bandes, mais la précision pratique et les
classements globaux restent insuffisamment établis.
Autorisation originale : [tâche terminée](../../codex-prompts/CURRENT_TASK.md).

## Provenance et dessin prospectif

Branche `main`, HEAD de départ propre et de collecte
`ea3d78a10280e83e65a2bd7474af3eaf8ee1a905`. Les sources modifiées sont archivées
et hashées avant les nouveaux tirages; aucun Git d'écriture par Codex.
Résultats nouveaux : `result/extended_batch_20261122T115422Z/`.
Gel : `2026-11-22T12:09:22.897254+00:00`.
`frozen.json` lie sélection, contextes, plan des24 blocs, flux RNG réservés,
sources, environnement, poids et gate A. Chronos-T5-mini, révision
`bd6a4fde8403b8469acd0abd52852b29dbe61c7b`, C512/H32, q50/top-k50 avec ties,
température1/top-p1,90 % de masse sélectionnée, cap8 incluant greedy, résidu explicite.

| Dataset | Série | Strate | Origine | IQR du contexte |
| --- | --- | --- | ---: | ---: |
| M4 Daily | T000029 | représentative, round0 | 831 | 203.22244 |
| M4 Daily | T000008 | diversité, round0 | 981 | 59.85251 |
| M4 Daily | T000092 | représentative, round1 | 537 | 239.50000 |
| M4 Daily | T000028 | diversité, round1 | 988 | 1733.52502 |
| ERCOT | SOUTH_C | représentative | 154840 | 3297.18542 |
| ERCOT | WEST | diversité | 154840 | 426.78754 |
| Exchange Rate | currency_8 | représentative | 7556 | .02586700 |
| Exchange Rate | currency_6 | diversité | 7556 | .00123550 |

Origine=longueur−32; seules les512 valeurs précédentes servent aux caractéristiques
et au QC. Chaque round reprend le sélecteur existant : tirage uniforme parmi
IDs éligibles triés, puis plus grande distance de rangs des six caractéristiques
de contexte, sous le90e percentile de rayon; exclusion du couple avant le round
suivant. Les valeurs futures et résultats FPA n'entrent pas dans ces critères.
Les hashes de fichiers sources servent à la provenance et aux espaces RNG.

Les anciens CSV de scans, y compris archivés, étendent les exclusions à M4
T000000..T000004, ERCOT COAST/EAST/FAR_WEST/NORTH/NORTH_C et devises1..5;
les identités du pilote sont ajoutées. `exclusion_evidence` conserve fichiers,
SHA et IDs observés. Certains CSV historiques ont une largeur de lignes variable;
la lecture des colonnes d'identité ne réécrit aucun de ces fichiers.
L'exposition antérieure de FAR_WEST/currency_1/currency_2 du petit pilote est
ainsi maintenant documentée; cela limite la nouveauté de sa cohorte, sans
invalider ses mesures conditionnelles ni sa loi de sampling.

Populations locales éligibles après exclusions :52 M4,2 ERCOT,3 devises.
Après ce lot : **48 M4,0 ERCOT,1 devise** encore disponibles comme nouvelles
identités locales. Les deux régions ERCOT et les devises partagent des processus;
les corrélations sont conservées dans `cohort_dependence.json` : .95245 pour
ERCOT et .66076 pour les devises, aux mêmes origines respectives. Les associations
de forme M4 vont de −.89180 à .58468, sur des origines non alignées; elles ne
démontrent pas un processus contemporain commun. Ni huit IDs
distincts ni trois graines ne garantissent huit unités statistiques indépendantes.

## Stage A — comparaison directe, avant nouveaux tirages

Les dix cellules du pilote antérieur sont relues avec vérification des
checkpoints et704 flux RNG distincts. W1/ED historiques reproduits à une erreur
relative maximale `5.93e-14`. **279 tests offline passent en122.59 s** avant gel.

Prédictions fixées sans continuation alternative : translation de l'ensemble
same-token indépendant par J, ou par `J*phi^(coordonnée−b)`, phi=lag1 du contexte.
Le test compare **alternative versus loi transformée**. Le contrôle même loi
est référence versus null, équivalent après la même translation des deux côtés.
La comparaison des seules distances à la référence reste un diagnostic distinct.

Supports : suffixe complet b+1..31, relatif22 b+1..b+22, absolu22 10..31,
final8 24..31. Le token forcé est exclu; les exposants AR1 restent absolus
par rapport à b, y compris sur les supports tardifs. W1 marginal moyen et ED V
avec norme euclidienne/√L; pas de racine finale. Les ED de dimensions différentes
ne sont pas le même estimand.

Validation sur graines20261121/22 N40, indépendantes de la première graine du
pilote, avec19 999 permutations de trajectoires entières et Holm sur
**69 alternatives ×2 baselines ×2 métriques=276 tests** en relatif22.
**12 tests**, portant sur cinq alternatives, rejettent une baseline à5 %.
Les supports restants sont descriptifs. Les graines ont déjà été analysées dans
l'itération précédente : cette réanalyse est exploratoire; les nouveaux tirages
du présent lot fournissent la validation prospective suivante.

Deux exemples SOUTHERN rejettent **les deux baselines dans les deux métriques** :

| Fork / token | W1 alternative/référence / IQR | W1 résiduel persistant / AR1 | ED résiduelle persistante / AR1 | Null W1 / ED |
| --- | ---: | --- | --- | --- |
| b0 /2229 | .04764 | .04498 / .04178 | .02811 / .02552 | .01535 / .00381 |
| b1 /2227 | .03700 | .03724 / .02991 | .02299 / .01484 | .01164 / .00238 |

Les quatre p-values corrigées valent.0138 dans chaque exemple. J=65.22754,
IQR=1559.67987. Ces résultats soutiennent l'inadéquation de **ces deux
transformations fixes** dans ces cas. Ils ne réfutent pas tous les modèles de
propagation numérique, ne démontrent pas l'importance pratique et ne mesurent
pas une causalité sur la série réelle. Ne pas rejeter ailleurs n'établit pas
l'équivalence. Les asymétries de sauts opposés sont conservées avec références
partagées et intervalles bootstrap ponctuels.

## Révision d'échantillonnage de ce lot seulement

Chaque loi conditionnelle reçoit trois blocs indépendants N20, racines
2026112211/12/13. Les directs P11..15 et overlaps P0/P9/P10 sont aussi20+20+20;
P10 réutilise les trois références b9. Cela donne N60 partout sans répéter trois
fois des directs N60. Le pilote historique reste N20 inchangé.
2 768 flux potentiels, incluant les réservations de validation, sont nommés et
seedés avant inférence; seuls les rôles effectivement nécessaires sont tirés.
Identités, tokens/valeurs complets, blocs et provenance restent séparés.

Sélection exclusivement sur bloc0 : plus grande ED_relative22, puis plus grand
W1_relative22 parmi les autres; ties (b,token). Un contrôle uniforme restant,
distinct si possible, utilise une graine dédiée. Les deux autres blocs forment
le holdout N40. Au plus ces deux alternatives reçoivent un nouveau N60, racine
2026112291; référence/null partagés seulement à b identique. Le contrôle
aléatoire reste évalué sur holdout. Aucun agrandissement adaptatif.

Familles prospectives séparées : holdout, candidats et contrôles ×raw/persistant/AR1
×W1/ED en relatif22; validation fraîche, candidats seuls ×les mêmes six tests.
Holm à5 % dans chaque famille, contrôles same-token dans une famille distincte.
19 999 permutations,399 bootstrap de trajectoires entières, indices de référence
et null communs aux contrastes concernés. Les bandes percentiles restent
conditionnelles aux pools finis et biaisées près de l'égalité; leurs bornes
positives ne sont pas des tests. Le seuil.02 IQR est une sensibilité de dessin,
sans minimum pratique universel approuvé, et n'a pas le même sens pour W1 et ED.

Capture white-box bornée aux huit chemins prédéfinis du bloc0 par fenêtre;
aucune multiplication par trois. Tous les autres tokens/valeurs sont conservés
avec leurs prérequis de replay. Les deux premières fenêtres ont passé le gate
complet avant les six suivantes. Reprise sans rééchantillonnage des objets
finalisés; ressources mesurées par Job Windows, un worker à la fois.

## Collecte réellement exécutée et intégrité

Fin de collecte : `2026-11-22T12:57:43.086666+00:00`; fin d'analyse :
`2026-11-22T13:07:46.222798+00:00`. Les 24 cellules denses sont trois blocs pour
chacune des huit fenêtres, pas 24 séries indépendantes. Elles contiennent
**1 617 ensembles N20 et 32 340 trajectoires**. Les validations ajoutent
**44 ensembles N60 et 2 640 trajectoires** : 16 alternatives, avec références
et nulls partagés dans les deux fenêtres où les candidats ont le même b.
Total : **1 661 ensembles, 1 661 identités RNG et graines dérivées distinctes,
34 980 trajectoires**. Le pooling primaire couvre 80 positions et235 alternatives.

Les gates A, deux premières fenêtres et reconstruction des vues poolées passent.
L'analyse reconstruit q50, ties, selected/residual, p_sel et entropies depuis les
240 logits de fork sauvegardés : erreur maximale des poids de mélange nulle,
sans modèle. Le pooling concatène tokens/valeurs, vérifie contexte et greedy,
recalcule W1/ED et les mélanges; moyenner trois distances n'aurait pas produit
la distance N60. Les identités probabilistes poolées correspondent à la moyenne
des trois probabilités N20 à1e-12. Les contrôles de conditioning, decoder parity,
couverture et publication des cellules sont dans les marqueurs complets.

La reprise après achèvement a été exécutée avec lancement de worker interdit :
**zéro lancement, zéro nouveau tirage**, toujours32 tentatives; les hashes de
3 844 fichiers expérimentaux sont inchangés (`resume_verification.json`).
La vérification finale contrôle aussi les2 956 fichiers data/result préexistants,
taille, date et SHA, l'index Git, `.gitignore` et le cache modèle épinglé.
Les rapports historiques et le protocole N20 d'origine ne sont pas réécrits.

Coût local mesuré : **2 837.954 s, soit47 min17.954 s cumulées de processus
modèle**,32 tentatives, aucun échec; CPU float32/eager, quatre threads, Python
3.12.12, torch2.11.0, transformers5.12.1. Ce temps inclut lancement, chargement,
contrôles et publication; la collecte dense seule rapporte2 063.062 s, ses
chargements146.065 s. Ce ne sont pas des heures CPU ni un débit isolant le
decoder. Stage A prend144.460 s et l'analyse nouvelle434.896 s, hors modèle.

Pic de mémoire engagée du Job Windows : **1 407 582 208 octets,1.311 Gio**;
minimum RAM libre du système178 659 328 octets et disque libre315 050 188 800
octets. Ce pic concerne le processus et ses descendants, pas toute la machine.
Un worker à la fois, garde RAM64 Mio pendant cinq secondes consécutives et
plancher disque1 Gio; aucune garde n'a arrêté le lot. Les autres applications
expliquent une partie de la pression mémoire observée, sans attribution causale.

Stockage figé après analyse : cellules474 358 714 octets, validations779 147,
analyse16 815 502 et sources de collecte402 815. Les NPZ des cellules et validations
totalisent462 021 536 octets, captures comprises. **64 chemins white-box** sont
capturés, huit par fenêtre sur bloc0; zéro tirage additionnel pour capture.
Tous les autres chemins conservent leurs tokens, valeurs et prérequis de replay.
Ces tailles excluent le ZIP de revue et les journaux/receipts finaux.

Les sources de collecte sont figées dans `source_at_collection/` et
`source_manifest.json`; les sources d'analyse dans `analysis/source/`.
SHA256 de l'analyse étendue :
`55ad3b6d3bc43717d196e39d6187addb78bbfb5eb0a0adc2028b74909e9ac66e`.
Elle réutilise l'analyse offline antérieure, SHA256
`e06abb94325783e3cc326701cd2197a3d33f318f8b9f2a5dc18851e7044b0842`.
Le HEAD seul ne décrit donc pas les sources exécutées : il faut ces archives
du travail non commité et leurs hashes. Le futur SHA de commit chercheur est inconnu.

## Précision et validation indépendante

Le primaire est relatif22. Holdout :24 contrastes,16 sélectionnés et8 aléatoires,
×3 méthodes raw/persistant/AR1 ×2 métriques = **144 tests, une famille Holm**.
N60 frais :16 sélectionnés ×6 = **96 tests, une autre famille Holm**.
Les tests same-token ont leurs propres familles de42 et28 tests après déduplication
des positions partagées; aucun ne rejette. Ce contrôle ne prouve pas l'égalité
exacte ni une calibration universelle. Aucun FWER global entre toutes les étapes
et toutes les questions n'est revendiqué.

| Test sur16 candidats | Rejets holdout40 | Rejets frais60 | Rejet dans les deux |
| --- | ---: | ---: | ---: |
| W1 raw | 5 | 8 | 3 |
| ED raw | 4 | 9 | 3 |
| W1 persistant | 1 | 4 | 1 |
| ED persistant | 1 | 3 | 1 |
| W1 AR1 | 1 | 2 | 1 |
| ED AR1 | 0 | 1 | 0 |

Les contrôles aléatoires holdout rejettent raw dans2/8 cas, en W1 comme en ED;
aucun rejet de baseline. L'enrichissement sélectionné est donc modeste à N égal :
5/16 contre2/8 pour W1,4/16 contre2/8 pour ED. Le premier slot ED produit2/8
rejets raw W1 et1/8 raw ED; le slot W1 restant3/8 dans les deux métriques.
Ces contrôles sont de vraies alternatives, pas des lois nulles par construction.
Ils n'ont pas de N60 frais : comparer16 candidats frais aux huit contrôles N40
ne permettrait pas de conclure à un enrichissement. Huit sources dépendantes
ne justifient pas un test de population utilisant les branches comme unités.

Bandes percentile ponctuelles à95 %, largeur médiane parmi les alternatives,
W1/IQR relatif22 :

| Série | N20 bloc0 | N40 holdout | N60 pool | Rang bloc0/holdout W1 / ED | Top5 commun W1 / ED |
| --- | ---: | ---: | ---: | --- | --- |
| T000029 | .11155 | .08466 | .07632 | .268 / .259 | 2 /2 |
| SOUTH_C | .03089 | .02194 | .01851 | .586 / .605 | 4 /4 |
| T000008 | .29110 | .18986 | .18196 | −.296 /−.278 | 1 /1 |
| T000092 | .20173 | .15624 | .13450 | .197 / .255 | 0 /0 |
| T000028 | .04358 | .03541 | .03001 | .206 / .089 | 2 /0 |
| WEST | .03703 | .02398 | .01797 | .538 / .687 | 3 /3 |
| currency_8 | .21228 | .17744 | .15420 | −.600 /−.309 | 2 /2 |
| currency_6 | .09921 | .07090 | .07464 | .244 / .251 | 2 /2 |

Le N60 donne ici des largeurs W1 de25–51 % et ED de34–71 % plus petites que
bloc0; l'évolution réalisée n'est pas monotone pour chaque ensemble. Ces
échantillons N20/N40 sont disjoints, mais le N60 les inclut : les comparaisons
N60 ne sont pas des réplications indépendantes. Toutes les combinaisons N20/N40
figurent dans `precision_estimates.csv`; les dépendances dans `rank_stability.csv`.
Les bandes ED restent souvent plus larges que leur estimation ponctuelle.
La stabilité globale N60/N60 n'est pas mesurée : seuls deux candidats/fenêtre
ont des tirages frais. Les rangs N20/holdout ne l'établissent pas par extrapolation.

## Échec direct des baselines : ce qui se reproduit

**SOUTH_C b0/2214**, J=266.9921875, soit.080976 IQR. Sur le N60 indépendant,
les distances sont les suivantes; les quatre rejets de baselines ont chacun
pHolm=.0048 dans la famille96 :

| Comparaison | W1 brute | W1/IQR [bande ponctuelle] | ED brute | ED/IQR [bande ponctuelle] |
| --- | ---: | --- | ---: | --- |
| Alternative/référence | 157.06027 | .04764 [.04213,.06276] | 117.00960 | .03549 [.02724,.05239] |
| Résidu persistant | 185.02364 | .05612 [.04622,.06986] | 112.61425 | .03415 [.02484,.05157] |
| Résidu AR1 | 121.54841 | .03686 [.03021,.04995] | 50.80129 | .01541 [.01144,.02743] |
| Same-token | — | .01495 | — | .00243 |

Le holdout confirme la différence brute dans les deux métriques (.0072 corrigé),
mais **aucune des quatre comparaisons transformées ne rejette après Holm**
(.65945/.435 pour persistant W1/ED;1/1 pour AR1). Le résultat frais constitue
une validation indépendante de la sélection, pas une réplication positive des
quatre rejets sur les deux ensembles. Le candidat SOUTH_C b0/2213 rejette aussi
le persistant frais dans les deux métriques; les candidats partagent référence/null.

**WEST b0/2222** reproduit les rejets persistant W1/ED et AR1 W1 dans holdout
et frais. Distances fraîches/IQR : persistant W1=.04300 (pHolm=.0048),
ED=.02600 (.0048), AR1 W1=.02806 (.015); null=.01590/.00342. L'AR1 ED ne
rejette pas. WEST b0/2217 ajoute un rejet persistant W1 frais (.02952,.042).
Les autres comparaisons n'établissent pas un échec de baseline après correction.

Il existe donc des exemples indépendamment soutenus où ces prédictions fixes
sont inadéquates, avec une réplication plus forte de certains contrastes WEST.
Cela va au-delà d'une simple égalité des distances à la référence et teste
explicitement J et phi. Cela ne démontre ni une propriété universelle, ni une
information prédictive supplémentaire par rapport à p_sel/entropie, ni une
importance pratique. L'AR1 peut réduire une distance sans rendre les lois égales.
Le seuil exploratoire.02 IQR n'est pas un critère d'équivalence validé : par
exemple l'ED AR1 SOUTH_C rejette tout en étant.01541 IQR.

Les paires opposées à même nombre de bins sont conservées dans les CSV de
contrastes et de résidus, avec bootstrap partageant les indices de référence/null.
Au N60 pool,97 paires en relatif22 : médiane descriptive de l'asymétrie absolue
W1=.01988 IQR brute, .01077 après persistant, .00897 après AR1;
ED=.00972, .00314, .00309. Ces médianes de paires dépendantes ne constituent
pas un test. Une partie de l'asymétrie est compatible avec la propagation
numérique; ni son explication complète ni une asymétrie universelle ne sont
établies. Les ensembles frais opposés éventuellement retenus partagent leur
référence explicitement; aucune validation additionnelle n'a été choisie après
inspection de leurs asymétries. Les bandes ne sont pas corrigées comme les tests.

## Effets, supports et explications concurrentes

Médianes parmi les alternatives de chaque source, N60 pool, relatif22. Les
unités brutes restent celles de la série; aucune moyenne brute inter-datasets :

| Série | Alternatives | W1 brute | ED brute | W1/IQR | ED/IQR | W1 complet ≤ null |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| T000029 | 29 | 14.02762 | 3.49020 | .06903 | .01717 | 5 |
| SOUTH_C | 33 | 79.03594 | 20.75776 | .02397 | .00630 | 9 |
| T000008 | 20 | 10.25584 | 2.59502 | .17135 | .04336 | 0 |
| T000092 | 64 | 30.18374 | 7.13913 | .12603 | .02981 | 14 |
| T000028 | 30 | 47.93147 | 14.79113 | .02765 | .00853 | 4 |
| WEST | 29 | 10.20115 | 2.44079 | .02390 | .00572 | 3 |
| currency_8 | 10 | .005445 | .002537 | .21050 | .09806 | 0 |
| currency_6 | 20 | .000097 | .000029 | .07851 | .02368 | 1 |

Les moyennes des médianes par source donnent M4 n4=.09851/.02472 W1/ED,
ERCOT n2=.02394/.00601, devises n2=.14451/.06087. C'est une description de
cohorte, pas une comparaison causale de modèles/datasets. **36/235** distances
W1 complètes sont ≤ null; leur différence avec le pilote ne peut être attribuée
au seul N, puisque la cohorte change. Les statistiques complètes et brutes des
quatre supports sont dans `temporal_support_distances.csv` et les baselines
dans `direct_baseline_distances.csv`.

Les rangs W1/ED raw en relatif22 ont rho=.903 à.984 selon source; la concordance
sur un pool partagé ne prouve pas la reproductibilité entre tirages. Entre
full et relatif22, W1 rho=.708 à.989, ED=.817 à.997; pour T000008 le support
modifie davantage les rangs. Full pondère des horizons différents selon b;
absolute22 fixe les coordonnées, relatif22 fixe le temps écoulé. Les estimands
ne doivent pas être confondus.

Le centrage par moyenne de chaque trajectoire et la différence première
réduisent beaucoup les distances : médianes W1/IQR raw/centré/différencié
.1714/.0589/.0376 pour T000008 et.2105/.0415/.0206 pour currency_8.
Un effet de niveau ou de tendance est donc compatible avec une part importante
des distances. Le centrage ne retire pas toute la forme; différencier change
dimension et estimand. Aucun test corrigé n'isole ici un effet de dépendance
jointe à marges et moyennes égales.

Sur early8/late8 strictement post-fork,170/235 W1 alternatives augmentent,
mais aussi78/80 nulls; seulement64/235 excès descriptifs alternative−null
augmentent. La corrélation intra-série de W1 null avec la dispersion de référence
va de.657 à.857. Cela soutient la dispersion/variabilité ordinaire comme
explication concurrente majeure de l'augmentation brute. Les profils signés,
variances et gains figurent dans `propagation_profiles_N60.csv` :32/235
réponses moyennes changent de signe entre ces supports, sans tests individuels
de renversement. Les235 J satisfont le seuil préexistant d'éligibilité du gain.
Ni amplification physique ni causalité interne ne découlent de ces diagnostics.

Les corrélations descriptives W1–q50/p_sel sont négatives dans les huit sources
(rho −.645 à−.164); entropie–W1 varie de−.118 à.441. Ce n'est pas une analyse
incrémentale ajustée. |J| et distance covarient dans plusieurs sources, avec
confusion position/probabilité/bin. **T000008, currency_6 et currency_8 n'ont
que des offsets absolus d'un bin** : leurs petites variations de |J| déquantifié
proviennent notamment du calcul float32; leur corrélation de rang avec |J|
ne mesure pas une variation substantielle de taille d'intervention. Les faibles
associations de largeur de bin ont la même limite. Les caractéristiques
de régimes sont publiées par source; huit unités dépendantes ne permettent pas
d'estimer proprement leurs effets ajustés.

Cinq positions atteignent cap8; deux de T000092 restent sous90 % de masse,
minimum .85755, résidu maximal .14245. Le résidu est effectivement échantillonné,
pas abandonné. `normalization_sensitivity.csv` conserve IQR, std, range et IQR
récent128, avec indicateurs invalides et sans remplacement silencieux. Les
IQR présents sont positifs; les ratios inter-séries restent sensibles à l'échelle
et ne résolvent pas la pathologie IQR documentée sur l'ancienne T000049.

## CPD, compensation et variance future

P0..P9 restent des mélanges q50 avec résidu explicite; P10 est la référence b9,
P11..15 des tirages directs N60. Les mêmes événements binaires fixés par fenêtre
et six outcomes continus sont utilisés partout. Les distances continues incluent
cumul et adjacent; raw et signed sont parfois la même distance par invariance
de translation, pas deux découvertes.

W1 terminale P0→P15/IQR, puis gap indépendant same-law de P0 : T000029
.20259/.05348, SOUTH_C .05622/.01598, T000008 .40444/.19955, T000092
.20931/.11422, T000028 .06271/.02800, WEST .01810/.01454, currency_8
.12566/.07623, currency_6 .10572/.05578. Les gaps sont des contrôles Monte
Carlo, pas des seuils exacts pour une autre comparaison. Les courbes décrivent
un changement de loi conditionnelle; elles n'établissent pas des change points.

Les240 comparaisons binaires mixture/direct ont un écart maximal .18691,
**zéro exclusion par borne Hoeffding ponctuelle et familiale**. Leur absence
n'établit pas l'égalité ou l'absence de biais. P10/P11 ont maintenant tous deux
N60 : le déséquilibre20/60 historique est absent, mais méthodes et covariances
diffèrent toujours. `reuse_covariance_N60.csv` explicite la réutilisation P9/P10;
`p10_p11_uncertainty.csv` donne proxy1/60, bootstrap et bornes appropriées.
Les SE plugin valent zéro pour231/1280 événements primaires; les bornes finies
restent non nulles, y compris pour les événements rares.

Sur800 événements locaux,687 ont une contribution absolue non nulle et160/687
une compensation ≥50 %. Cinq bornes locales ponctuelles excluent zéro, sans
correction familiale; la contribution résiduelle absolue maximale vaut.03661.
L'identité signée locale est algébrique, vérifiée empiriquement avec la même
référence, et non un résultat mécanistique nouveau. La comparaison à la mixture
de position suivante est distincte, tandis que b9/P10 réutilise littéralement
la même loi. Aucune compensation systématique ni progression monotone établie.

La variance between est corrigée du bruit des moyennes conditionnelles par
`sum w*(1-w)*s²/n`. Sur640 coordonnées final8,91 estimates corrigées sont
négatives et conservées. La fraction between corrigée médiane par source est
.00394 à.02940; correction/between plugin médiane .182 à.754. Ce biais est
donc matériel. La variance interne du résidu agrégé cache une partie de la
variance entre ses tokens; le ratio corrigé n'est lui-même pas sans biais.
Les associations avec entropie restent descriptives, sur dix forks/source.

## Conclusions classées et prochaine décision

1. **Observé, preuve indépendante ciblée : les deux transformations fixes ne
   suffisent pas dans certains cas.** SOUTH_C frais rejette les quatre tests;
   WEST reproduit trois rejets sur deux ensembles. C'est une information au-delà
   de ces prédictions de J/phi et de leur bruit sous l'égalité, sans établir un
   effet utile ni un gain au-delà de toute fonction de J/probabilité. Une étude
   confirmatoire avec seuil pratique fixé et effets proches du null pourrait
   réfuter leur importance; aucune généralisation hors de ces sources n'est vérifiée.
2. **Observé, preuve de précision limitée : N60 améliore les bandes, sans valider
   un classement fin.** Les réductions de largeur sont nettes, mais rho N20/N40
   peut être négatif et seulement3/16 rejets bruts se répètent par métrique.
   Cela suggère une sélection instable; un classement N60/N60 indépendant stable
   au niveau source pourrait réfuter cette réserve. L'adéquation à un seuil
   pratique reste ouverte; aucune nouvelle taille N n'est automatiquement justifiée.
3. **Observé et suggéré : niveau, jump et dispersion expliquent une partie des
   profils.** Centrage/différences réduisent les distances, les nulls croissent
   presque partout et les baselines réduisent l'asymétrie médiane. L'hypothèse
   d'une amplification propre au token reste non vérifiée. Des réponses ajustées
   et reproductibles, avec controls de dispersion et J appariés, pourraient
   réfuter l'explication ordinaire. Les corrélations actuelles ne démontrent
   aucune information supplémentaire conditionnelle à probabilité/entropie.
4. **Observé, résultat négatif : pas de rupture CPD ni compensation systématique
   établie.** Les gaps entre estimateurs et le biais between sont importants;
   les contrôles binaires ne rejettent pas. Cela ne réfute pas toute dérive
   réelle. Une dérive définie à l'avance, excédant des contrôles de même méthode
   avec correction multiple, pourrait renverser cette conclusion.
5. **Observé, limite de généralisation : huit identités ne font pas huit sources
   indépendantes.** Deux ERCOT fortement corrélées, deux devises, une seule
   fenêtre/source et des stocks locaux presque épuisés hors M4 limitent C2.
   Des sources indépendantes avec effets cohérents pourraient réfuter cette
   limite empirique; rajouter des fenêtres voisines ne le ferait pas.

**Prochaine recommandation unique, non autorisée comme nouvelle collecte : revue
ChatGPT–chercheur45–60 min, zéro tirage.** Fixer des seuils pratiques distincts
W1/ED, choisir les hypothèses confirmatoires et décider précision nécessaire,
diversité et taille restante. La proposition d'étendre simplement cette grille
serait invalidée si le gain attendu ne dépasse pas le bruit ou si les nouvelles
sources ne peuvent fournir les unités indépendantes demandées. Toute collecte
supplémentaire demande une nouvelle autorisation avec plafond explicite.
**Arrêt effectif après ce premier lot; aucun deuxième lot lancé.**

## Tests, fichiers et remise au chercheur

Tests exécutés : suite précollecte279 réussis/122.59 s; analyse ciblée2/6.19 s;
suite finale **281 réussis/144.39 s**, six avertissements de retries de publication
de dossiers temporaires Windows ayant réussi; handout ciblé **9/4.10 s**.
Les tests utilisent des données factices/offline, sans nouvelles inférences.
Contrôles finaux : **216 liens locaux dans59 Markdown canoniques et338 liens
dans29 Markdown exportés, zéro lien cassé**; `git diff --check` passe.
Les hashes des documents/assets/ZIP et la conservation des preuves passent.
Les receipts
`final_checks.json` et `preservation_after.json` donnent les comptes exacts.

Fichiers source modifiés et raison :

- `code/chronos_fpa/pipeline/chronos_exploratory_window.py`,
  `chronos_pilot_validation.py`, `scripts/runs/run_chronos_local_pilot.py` :
  mode explicite de bloc20 et namespace RNG, avec anciens défauts conservés.
- Nouveaux `code/chronos_fpa/analysis/chronos_propagation_baselines.py`,
  `code/chronos_fpa/data/chronos_extended_selection.py`,
  `configs/chronos_extended_batch/batch_v1.json`,
  `scripts/runs/run_chronos_extended_batch.py`,
  `scripts/viz/analyze_chronos_direct_baselines.py`,
  `scripts/viz/analyze_chronos_extended_batch.py` : transformations, sélection,
  gel, collecte bornée et analyse reproductible.
- Nouveaux tests `tests/chronos_fpa/unit/test_extended_baselines.py`,
  `tests/chronos_fpa/unit/test_extended_analysis.py`,
  `tests/chronos_fpa/integration/test_extended_batch.py` : indexing, comparaisons
  directes, exclusion/sélection context-only, pooling, blocs et reprise.
- `scripts/maintenance/prepare_chatgpt_handout.py` : rapport courant prioritaire;
  `tests/README.md`, `docs/reference/PROJECT_STRUCTURE.md` : points d'entrée.
- `docs/reference/FPA_EXTENDED_BATCH_REPORT.md` : unique rapport de cette étape;
  `docs/README.md`, `docs/research/FPA_STATUS.md`, `FPA_HANDOFF.md`,
  `FPA_DECISIONS.md`, `README_WORKFLOW_V2.md`, `codex-prompts/CURRENT_TASK.md` :
  état réel, autorisation et arrêt. Aucun fichier supprimé ou déplacé.

Le handout renouvelle les copies gérées, joint **39 assets explicites** dont un
PDF de quatre pages et les CSV de revue, sans archive automatique. Les objets
complets, snapshots, RNG, logits, traces et receipts restent dans le dossier
résultat ignoré; le ZIP ne les remplace pas. Conserver aussi non suivis `data/`,
`result/`, caches, `.venv/`, `docs/chatgpt-handout/` et son ZIP.

Branche `main`, HEAD pré-commit `ea3d78a10280e83e65a2bd7474af3eaf8ee1a905`;
aucun staging/commit/push/pull/changement de branche exécuté. État Git et
commandes sélectives réservées au chercheur ci-dessous; ne pas ajouter les sorties.

```text
 M code/chronos_fpa/pipeline/chronos_exploratory_window.py
 M code/chronos_fpa/pipeline/chronos_pilot_validation.py
 M codex-prompts/CURRENT_TASK.md
 M docs/README.md
 M docs/reference/PROJECT_STRUCTURE.md
 M docs/research/FPA_DECISIONS.md
 M docs/research/FPA_HANDOFF.md
 M docs/research/FPA_STATUS.md
 M docs/research/README_WORKFLOW_V2.md
 M scripts/maintenance/prepare_chatgpt_handout.py
 M scripts/runs/run_chronos_local_pilot.py
 M tests/README.md
?? code/chronos_fpa/analysis/chronos_propagation_baselines.py
?? code/chronos_fpa/data/chronos_extended_selection.py
?? configs/chronos_extended_batch/
?? docs/reference/FPA_EXTENDED_BATCH_REPORT.md
?? scripts/runs/run_chronos_extended_batch.py
?? scripts/viz/analyze_chronos_direct_baselines.py
?? scripts/viz/analyze_chronos_extended_batch.py
?? tests/chronos_fpa/integration/test_extended_batch.py
?? tests/chronos_fpa/unit/test_extended_analysis.py
?? tests/chronos_fpa/unit/test_extended_baselines.py
```

Après revue, suggestion sélective, **non exécutée** :

```powershell
git add -- code/chronos_fpa/analysis/chronos_propagation_baselines.py code/chronos_fpa/data/chronos_extended_selection.py code/chronos_fpa/pipeline/chronos_exploratory_window.py code/chronos_fpa/pipeline/chronos_pilot_validation.py configs/chronos_extended_batch/batch_v1.json
git add -- scripts/runs/run_chronos_extended_batch.py scripts/runs/run_chronos_local_pilot.py scripts/viz/analyze_chronos_direct_baselines.py scripts/viz/analyze_chronos_extended_batch.py scripts/maintenance/prepare_chatgpt_handout.py
git add -- tests/chronos_fpa/unit/test_extended_baselines.py tests/chronos_fpa/unit/test_extended_analysis.py tests/chronos_fpa/integration/test_extended_batch.py tests/README.md
git add -- docs/reference/FPA_EXTENDED_BATCH_REPORT.md docs/reference/PROJECT_STRUCTURE.md docs/README.md docs/research/FPA_STATUS.md docs/research/FPA_HANDOFF.md docs/research/FPA_DECISIONS.md docs/research/README_WORKFLOW_V2.md codex-prompts/CURRENT_TASK.md
```

Message proposé : `feat: validate direct propagation baselines and first N60 extended batch`.
Le [handoff](../research/FPA_HANDOFF.md) reste le point de reprise de la revue.
