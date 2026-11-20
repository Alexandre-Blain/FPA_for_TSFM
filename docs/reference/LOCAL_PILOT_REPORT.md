# Pilote FPA multi-séries et calibration Monte Carlo

**20 novembre 2026 — terminé, arrêt pour revue scientifique.** Six séries
originales, dix cellules, **17 280 trajectoires / 704 ensembles** finalisés.
Le fonctionnement technique est validé sur ce panel. Les classements N20 restent
instables; la valeur ajoutée au-delà de J/probabilité/bruit n'est pas établie.

Les [preuves structurées](LOCAL_PILOT_EVIDENCE.json) contiennent la sélection,
les rejets, hashes, marqueurs, environnement, tests et chemins modifiés.
Le [PDF de 23 figures](../../result/local_pilot_20261120T184035Z/analysis/PILOT_FIGURES.pdf)
et les CSV sont joints explicitement au handout de cette revue. Les estimands
restent ceux du [protocole](../research/FPA_PROTOCOL_EXPLORATORY.md).

## Autorisation, sources et intégrité

Branche : `main`. HEAD au démarrage :
`b9c6a011e14a93235ed90cf88a11a25cead7264a`. Un commit extérieur à Codex,
`62271b156db9d56ffbbd673d24b4d111ccd75f7e` (`cleaning doc`,19:22:24 UTC), a
intégré la maintenance et une partie de la préparation avant le gel. Ce dernier
SHA est le **HEAD de collecte et actuel avant le prochain commit du chercheur**;
les manifestes le capturent correctement. Codex n'a effectué aucune écriture Git.
L'index est identique à celui enregistré au gel et le staging est vide.
Le hash personnel de `.gitignore` est inchangé depuis le démarrage.
La liste actuelle exhaustive est dans les preuves.
Dossier : `result/local_pilot_20261120T184035Z/`.

Les deux pièces d'autorisation sont conservées byte pour byte; leur texte
normalisé est identique, encodages/fins de ligne différents. Le périmètre est six
fenêtres et quatre réplications, sans les anciens plafonds de Prompt 2.
Aucune installation, acquisition de données, exécution distante, nouvelle
famille de modèles, Stage A ou campagne supplémentaire n'a eu lieu.

Sélection figée à **19:30:30 UTC**, avant modèle. Révision de grille :
`764c2e930b966179390357f2346ddb8d2d16d697296fd784b69ba1ae6cbe0ba6`.
`frozen.json` lie sélection, contextes NPZ, plan, environnement, cache et sources.
**32 fichiers** de collecte sont copiés/hashés dans `source_at_collection/`;
l'analyse a sa copie et son hash distincts. Chronos-T5-mini en cache est épinglé
à `bd6a4fde8403b8469acd0abd52852b29dbe61c7b`. Les fichiers du snapshot local ont
leurs hashes enregistrés. Sources/données sont revérifiées avant chaque cellule;
poids et sources sont revérifiés à la clôture.

Le défaut `target_N20` historique est un écrasement de variable dans le
finaliseur de preuves. L'[addendum](FPA_PROMPT02_EVIDENCE_ADDENDUM.json) reprend
le résumé N20 intact et vérifie les 25 modules archivés correspondants.
L'original gelé est inchangé. Le lanceur intermédiaire exact N20 historique
reste non archivé; aucune reconstruction certaine n'est revendiquée.

## Sélection prospective et qualité

Population : exports JSONL **locaux**, split `train`. Origine `len(target)-32`,
contexte précédent de 512 valeurs; futur exclu des caractéristiques. Exclusion
des séries documentées M4/T000001, ERCOT/EAST et Exchange Rate/currency_3.
Les autres expositions FPA antérieures ne sont pas certifiées absentes.
Un chevauchement avec l'entraînement de Chronos est possible, non vérifié.

Population éligible : **55 M4, 7 ERCOT, 7 Exchange Rate**. Rejets : 44 M4 trop
courtes pour C512+H32, plus les trois séries déjà étudiées. Aucun IQR invalide
parmi les autres candidats. Tous les rejets et les 69 candidats sont conservés
avec ligne source, origine et SHA-256. La population M4 provient de l'export
local de 100 séries; aucune représentativité de toute M4 n'est revendiquée.

Représentant : tirage uniforme sur IDs triés, graine par dataset dérivée par SHA
de `20261120`. Diversité : distance moyenne quadratique entre rangs de six
caractéristiques, maximale depuis le représentant parmi les autres séries
dont le rayon de rang reste sous le quantile 90 %. Caractéristiques : tendance/IQR,
volatilité des différences/IQR, autocorrélations 1/24, changement de moyenne entre
demi-contextes/IQR et fraction de zéros. Égalités par ID lexical; aucun score FPA
ni erreur de prévision. Les règles et populations sont gelées avant inférence.

| Dataset / série | Strate | Contexte `[début,fin)` | Origine | IQR |
| --- | --- | ---: | ---: | ---: |
| M4 / T000063 | représentative | [476,988) | 988 | 400.875 |
| M4 / T000049 | diversité | [330,842) | 842 | 0.0650024 |
| ERCOT / SOUTHERN | représentative | [154328,154840) | 154840 | 1559.680 |
| ERCOT / FAR_WEST | diversité | [154328,154840) | 154840 | 511.465 |
| Exchange Rate / currency_1 | représentative | [7044,7556) | 7556 | 0.0381738 |
| Exchange Rate / currency_2 | diversité | [7044,7556) | 7556 | 0.195875 |

**Anomalie conservée :** T000049 passe d'un long plateau à environ 10 000 dans
la fin du contexte; son IQR reste celui du plateau. Le filtre de rangs n'excluait
pas ce cas. L'IQR est valide mais rend l'interprétation normalisée fragile.
Aucun remplacement de normalisation ni rejet après observation n'est appliqué.

Six identités distinctes ne garantissent pas l'indépendance statistique :
corrélation des deux contextes ERCOT synchrones **0.8854**, devises **-0.6114**.
Aucune inférence de prévalence ou généralisation hors entraînement.

## Collecte exécutée et contrôles

H32/C512, b0..9 denses, N20, q50/température1/top-p1, greedy-first90 % cap8,
résidu, contrôle same-token indépendant, P0..15 et overlaps P0/P9/P10 sont
conservés. Préfixes, tokens complets, valeurs, probabilités, logits des dix forks,
échelles et flux RNG sont persistés. T000063 et SOUTHERN passent les contrôles
avant les quatre autres. Calibration préchoisie sur ces deux représentantes;
graines `20261120`, puis `20261121/20261122`. Poids/candidats/greedy identiques
entre graines; **704 identifiants RNG distincts**.

| Cellule | Ensembles | Trajets | Collecte, s |
| --- | ---: | ---: | ---: |
| T000063 / 20261120 | 78 | 1880 | 104.732 |
| SOUTHERN / 20261120 | 67 | 1660 | 81.345 |
| T000049 / 20261120 | 96 | 2240 | 133.305 |
| FAR_WEST / 20261120 | 57 | 1460 | 76.317 |
| currency_1 / 20261120 | 58 | 1480 | 74.676 |
| currency_2 / 20261120 | 58 | 1480 | 75.774 |
| T000063 / 20261121 | 78 | 1880 | 125.932 |
| SOUTHERN / 20261121 | 67 | 1660 | 86.039 |
| T000063 / 20261122 | 78 | 1880 | 111.349 |
| SOUTHERN / 20261122 | 67 | 1660 | 97.994 |
| **Total** | **704** | **17280** | **967.463** |

Primaires : 10 200 trajets, 60 positions, 186 alternatives. Réplications :
7 080 trajets. Total : 100 positions; 100 références, 324 alternatives,
100 nulls et 100 résidus N20; 50 directs P11..15 et 30 overlaps N60.
P10 réutilise b9 sans nouvel ensemble. Aucun tirage stochastique de profiling.

**264 tests hors ligne passés en 108.24 s**, après263 en 92.18 s avant collecte.
Couverture : futur, sélection/QC, cap8/résidu84 %, fenêtres entrelacées avec mêmes
tokens/graines, interruption/reprise, checksums, objets étrangers, snapshots sans
écriture, calculs connus et covariance. Pytest ne charge aucun poids préentraîné.
Neuf tests couvrent aussi le handout et ses pièces explicites.

Les espaces de stockage sont propres à la fenêtre/graine. La lecture complète
vérifie scope, SHA, préfixes, N, reconstruction des distances et événements.
`complete.json` n'est publié qu'après capture/parité/intégrité. Les analyses lisent
seulement ces objets finalisés, liés par `pilot_complete.json`.

**2 924 contrôles réels de parité passent** : préfixes greedy/échantillonnés,
réencodage indépendant, attention activée/désactivée. Erreurs absolues maximales :
logits `1.52588e-5`, q50 `4.26173e-6`; tolérances absolues/relatives combinées
`1e-5/1e-4`, `1e-6/1e-4`, support positif identique exigé. Aucune garantie GPU.
Une reprise réelle vérifie les dix cellules sans modèle ni onzième tentative.
Aucune interruption réelle pendant la collecte; les interruptions sont testées
sur des collections contrôlées, sans démonstration de résistance à une panne secteur.

## Coûts et conservation white-box

Torch CPU, float32/eager; pas de CUDA/XPU. Profil sans tirage sur greedy/replay,
1/2/4 threads :0.989/0.808/0.529 s, puis quatre threads fixés. Ce passage unique
n'établit pas un optimum universel. Un processus par cellule libère les caches;
Job Windows natif sans ancien plafond mémoire/temps, kill-on-close et
`STOP_REQUESTED` aux publications durables permettent arrêt/reprise.

Dix tentatives, zéro échec. Temps cumulé des arbres modèle : **1165.002 s
(19 min 25 s)**, chargement/parité/capture compris. Fin : **19:50:12 UTC**.
Pic engagé des Jobs : **1 351 790 592 octets, 1.259 Gio**; ce n'est pas la mémoire
totale de la machine. RAM système libre minimale :584 810 496 octets.
Sorties à l'analyse : environ 354.4 Mo. Journaux par seconde : temps, RAM libre,
pic Job et disque libre.

Capture par primaire des deux premiers chemins référence/alternative d'ordre q50
à b0/b9 : **48 chemins nommés**, choisis avant leurs issues. Toutes couches/têtes,
32 queries : hidden encoder/décodeur, attentions encoder/self/cross, logits,
embeddings, bins, tokens, valeurs. Encodeur stocké une fois par fenêtre; batches2.
Query b avant consommation du token forcé, b+1 après; shapes/dtypes/hashes déclarés.

263 828 646 octets statiques +144 132 096 octets décodeur bruts;
335 081 673 octets de fichiers après compression/métadonnées; **35.220 s** mesurées
de capture/sérialisation. Extrapolation des octets à tous les trajets :30.89 Go
pour les primaires, 52.33 Go pour dix cellules, sans garantie de temps de replay.
Cela motive la capture bornée autorisée. Tous les autres trajets restent complets
et rejouables; leurs activations ne sont pas présentées comme déjà capturées.
Aucun résultat causal d'attention n'est établi.

## Distances, bruit et explications concurrentes

Médianes descriptives des alternatives, suffixe strict complet :

| Série | W1 brut | ED brute | W1/IQR | ED/IQR | W1 ≤ null indépendant |
| --- | ---: | ---: | ---: | ---: | ---: |
| T000063 | 24.5669 | 8.5443 | 0.06128 | 0.02131 | 11/40 |
| T000049 | 67.4467 | 21.5101 | 1037.60 | 330.91 | 29/58 |
| SOUTHERN | 42.0067 | 17.0409 | 0.02693 | 0.01093 | 8/29 |
| FAR_WEST | 34.2791 | 13.4754 | 0.06702 | 0.02635 | 7/19 |
| currency_1 | 0.007465 | 0.003196 | 0.19555 | 0.08372 | 4/20 |
| currency_2 | 0.013571 | 0.005311 | 0.06928 | 0.02712 | 1/20 |

Distributions par dataset en brut et normalisé dans les preuves/CSV, deux séries
visibles dans les boxplots. Étendues W1/IQR : M4 0.03287..6498.58,
ERCOT 0.01658..0.11736, devises 0.04262..0.39367. ED/IQR :0.00926..1337.98,
0.00454..0.07693, 0.00943..0.25176 respectivement. Les médianes poolées pondèrent
implicitement les séries par leurs candidats; aucune estimation de population.
Les unités brutes diffèrent entre datasets.

**60/186 branches** ont W1 inférieur ou égal à leur null. La médiane null de
T000049 vaut1028.12 IQR, proche de l'alternative1037.60 : sa grande échelle
normalisée ne démontre pas une séparation propre aux alternatives. Ni W1 ni
l'ED V-statistique positive à N fini ne sont des tests de différence.

Comparateurs sans modèle/tirage supplémentaire : translation de l'**ensemble
null indépendant** par J, persistante ou atténuée comme `J * lag1_contexte^h`.
Même bruit N20 et mêmes distances strictes. **98/186** alternatives ne dépassent
pas le W1_fixed22 du comparateur persistant; **91/186**, celui atténué.
Ces comparateurs sont simplistes et corrélés aux mesures par références
partagées; ces décomptes ne prouvent ni équivalence ni mécanisme causal.

Associations de rang intra-fenêtre W1_fixed22–|J| : -0.100..0.513;
q50 : -0.698..0.450; entropie q50 : -0.131..0.344. p_sel, q50, entropies,
bin-width/IQR, sauts signés et absolus sont exportés séparément. Tokens éloignés
et faibles probabilités sont souvent associés. Bins/échelle confondent les
relations. Les prédicteurs de fork se répètent entre alternatives et les
références sont partagées : aucun p-value poolé.

Les 75 paires de sauts opposés sont conservées. Exemple exploratoire currency_1,
b5 : |J|/IQR ≈0.1415 des deux côtés, W1_fixed22 0.12284 contre 0.33380,
q50 0.17551 contre 0.19357. Asymétrie possible, mais probabilités/bruit non contrôlés
et aucune réplication de graine sur cette fenêtre. T000049 domine certaines
asymétries normalisées; il ne doit pas devenir une démonstration principale.

W1 complet versus fixed22 : +4.21 % en médiane, jusqu'à144.38 % d'écart relatif
absolu. Supports non interchangeables. Les profils par horizon montrent aussi le
null; leurs médianes descriptives répètent le null par alternative. Après h22,
la composition des positions disponibles change. Aucune loi universelle de
localisation temporelle n'est établie.

Neuf cas morphologiques, explicitement post hoc : plus grande ED par fenêtre,
un cas sous le null, deux côtés de la plus grande asymétrie appariée. Chaque
panneau montre les **20 chemins de chacun des deux ensembles**, médiane et bande
10–90 %, relativement au greedy. SOUTHERN b3/token2216 montre des bandes largement
superposées. Descripteurs sur toutes les branches : niveau/terminal relatifs au
greedy, pente résiduelle, rugosité des trajectoires/résidus. Les figures suggèrent
surtout déplacements et dispersion; aucun nouveau motif validé. Une bande de
chemins10–90 % n'est pas un intervalle de confiance sur un effet.

## Calibration des lois d'issues

Deux séries ×trois graines ×trois overlaps ×dix événements = **180 comparaisons**.
Même terminal/last8 et cinq seuils fixes; toutes les courbes P0..15, SE et bornes
sont exportées. Conditionnellement au contexte/modèle/poids déterministes :

```text
Var(mélange) estimée = somme_i w_i² s_i² / n_i
Var(direct) estimée = s² / 60
Cov(P9_mélange, P10_réutilisé) estimée = w_g s_g² / 20
Var(P9-P10) = Var(P9) + Var(P10) - 2 Cov(P9,P10)
```

Hypothèses : chemins Bernoulli indépendants dans chaque groupe, flux indépendants
entre rôles/graines hors réutilisation déclarée. Événements et positions peuvent
être dépendants. Demi-largeur pointwise 95 % Hoeffding :
`sqrt(log(40)/2 * somme(w_i²/n_i))`; contraste avec direct indépendant : ajouter
`1/60` sous la somme. Correction union-bound/Bonferroni180 aussi fournie.
Aucun bootstrap n'est compté comme nouveau tirage.

| Position | Plus grand écart absolu, deux séries/trois graines |
| --- | ---: |
| P0 | 0.15419 |
| P9 | 0.17037 |
| P10 | 0.35000 |

Maximum : T000063, première graine, last8 >0.05; P10 réutilisé0.35, direct0.70,
différence -0.35. SE du contraste0.12463; demi-largeur Hoeffding 0.35066, et 0.54412
après correction famille. **0/180** bornes pointwise et famille excluent zéro.
La moyenne des trois graines garde un écart maximal0.13333, sous sa demi-largeur
0.20245. Compatible avec ces bornes conservatrices de bruit fini; cela ne prouve
pas absence de biais ou égalité exacte des lois.

**268/960 estimations primaires ont une SE plug-in nulle**; les bornes restent
non nulles. Aucun événement sur N20 n'établit pas une probabilité nulle.
À probabilité égale, P10/N20 a trois fois la variance d'un direct N60; une cassure
P10/P11 peut venir de l'estimateur. Proxys Hoeffding 1/20 versus1/60.
Covariance de réutilisation : sur les événements non dégénérés de T000063,
SE adjacente médiane naïve0.08164, corrigée0.04390. Les covariances empiriques sur
trois graines sont exportées mais ne sont pas stables.

Corrélations des rangs de branches entre graines, W1_fixed22 : **-0.101..0.446**
sur T000063 et **-0.122..0.380** sur SOUTHERN; ED : **-0.196..0.349** et
**-0.061..0.340**. Forte limite des classements N20. La réplication MC ne crée
pas de nouvelles séries et ne mesure pas leur variance. Aucun BEAST/PELT ajusté.

## Niveau de preuve et explication concurrente principale

| Niveau | Conclusion | Alternative / limite |
| --- | --- | --- |
| Observé | collecte, résidu, persistance et replay corrects sur dix cellules | pas de garantie autre backend/machine |
| Observé | T000049 atteint cap8 à quatre positions, manque90 % à b0/b1 | masses71.55/88.96 %, résidus28.45/11.04 % bien conservés |
| Réfuté sur ce panel | toutes les alternatives dépasseraient leur contrôle |60/186 contre-exemples W1 |
| Suggéré | hétérogénéité/asymétries conditionnelles possibles | J, probabilité, bins, échelle et MC suffisent peut-être |
| Observé | rangs N20 peu reproductibles sur deux fenêtres | variance d'estimation et références partagées |
| Non vérifié | information générale au-delà de J/p/entropie, motif stable | aucune validation hors séries ou mécanisme distinct démontré |
| Non vérifié | rupture structurelle des lois d'issues | frontière d'estimateurs, covariance,16 positions |

## Proposition locale plus large — non autorisée

**24 nouvelles séries**, une origine chacune :16 M4,4 ERCOT,4 devises, tirages
prospectifs dans les populations restantes53/5/5, sans sélection par résultat.
Les six séries du pilote restent une étude de conception distincte, avec strates
de diversité identifiées. Quatre nouvelles fenêtres préchoisies (2 M4,1 ERCOT,
1 devise) recevraient trois graines : **32 cellules**, au plus79 360 trajets H32/N20.

Ce nombre vise davantage de contextes M4 et la couverture des petits domaines
locaux, pas une puissance confirmatoire. Sous échantillonnage iid idéal,
demi-largeur de planification d'une moyenne ≈0.49 écart-type pour 16 séries,
≈0.98 pour quatre, avant dépendance/sélection. L'écart-type des six médianes
W1/IQR observées vaut423.57, dominé par T000049; deux séries par domaine ne
permettent pas une estimation fiable pour calculer une taille définitive.
Ces facteurs de précision ne sont pas des intervalles obtenus ici.

Précision MC séparée : trois graines donnent N60 effectif à P10, demi-largeur
Hoeffding 95 % maximale≈0.175; une fenêtre N20 seule reste à≈0.304.
Plus de séries ne stabilise pas une branche donnée. La revue doit fixer le
besoin de précision avant campagne ou changement de protocole; aucun changement
n'est appliqué ici.

Coût aux mesures actuelles :32×116.5 s, marge 2, **environ 2 h04 min** d'arbres
modèle; analyses/tests en plus. Marge2 non probabiliste. Capture bornée sur 24
primaires : environ 1.52 Gio de tensors bruts, plus chemins/métadonnées/figures;
réserver plusieurs Gio. Le pic mémoire observé n'est pas un plafond garanti.

**Une prochaine recommandation : revue scientifique hors modèle (45–60 min,
zéro tirage)**, priorité à précision N20, normalisation et dépendance des séries.
Rejeter le passage à la campagne si la cible de précision manque, si le résultat
repose seulement sur l'IQR pathologique, ou si un rang reproductible est prétendu
malgré les graines. Toute campagne attend une autorisation séparée. STOP ici.

## Changements et remise au chercheur

| Chemins scientifiques/outils | Changement |
| --- | --- |
| `code/chronos_fpa/runtime/ensemble_store.py` | scope fenêtre/graine, isolation et rejet d'objets étrangers |
| `code/chronos_fpa/runtime/windows_job.py` | plafond optionnel, kill-on-close conservé |
| `code/chronos_fpa/pipeline/chronos_exploratory_window.py` | scope, entropies, progression/reprise |
| `code/chronos_fpa/data/chronos_pilot_selection.py` | sélection/QC context-only |
| `code/chronos_fpa/pipeline/chronos_pilot_validation.py` | lecture complète et reconstruction des estimands |
| `code/chronos_fpa/metrics/chronos_pilot_uncertainty.py` | bornes conditionnelles et covariance |
| `scripts/runs/run_chronos_local_pilot.py` | freeze, dix cellules, gate deux fenêtres, supervision/capture |
| `scripts/viz/analyze_chronos_local_pilot.py` | analyse sans modèle, CSV et 23 figures/PDF |
| `configs/chronos_local_pilot/pilot_v1.json` | configuration autorisée, choix prospectifs |
| `tests/chronos_fpa/unit/test_pilot_selection.py`, `test_pilot_uncertainty.py`, `test_local_pilot_driver.py` | nouveaux tests |
| `tests/chronos_fpa/integration/test_exploratory_window.py`, `test_chatgpt_handout.py` | isolation/reprise/cap/résidu, lecture complète et pièces |
| `scripts/maintenance/prepare_chatgpt_handout.py` | pièces PDF/PNG/CSV explicites/hashées, archives exclues |

Six sources actives, index, tâche courante et guides de structure/tests sont
actualisés. Rapport/preuves et addendum N20 lié au benchmark sont les nouvelles
références. Le tableau ci-dessus couvre aussi la préparation intégrée par le
commit extérieur; seuls les chemins encore modifiés sont à proposer au staging.
Les 1 139 artefacts préexistants conservent taille/mtime; empreintes historiques
brutes revérifiées. Aucun dataset/résultat/checkpoint historique supprimé.

Commandes suggérées **au chercheur uniquement**, après revue des diffs depuis
`62271b1`; aucune exécutée par Codex :

```powershell
git status --short
git diff
git add -- code/chronos_fpa/metrics/chronos_pilot_uncertainty.py code/chronos_fpa/pipeline/chronos_pilot_validation.py code/chronos_fpa/pipeline/chronos_exploratory_window.py
git add -- scripts/runs/run_chronos_local_pilot.py scripts/viz/analyze_chronos_local_pilot.py
git add -- scripts/maintenance/prepare_chatgpt_handout.py tests/chronos_fpa/unit/test_pilot_selection.py tests/chronos_fpa/unit/test_pilot_uncertainty.py tests/chronos_fpa/unit/test_local_pilot_driver.py tests/chronos_fpa/integration/test_exploratory_window.py tests/chronos_fpa/integration/test_chatgpt_handout.py tests/README.md
git add -- AGENTS.md codex-prompts/CURRENT_TASK.md docs/README.md docs/research/FPA_DECISIONS.md docs/research/FPA_HANDOFF.md docs/research/FPA_PROTOCOL_EXPLORATORY.md docs/research/FPA_STATUS.md docs/research/README_WORKFLOW_V2.md
git add -- docs/reference/BENCHMARK_REPORT.md docs/reference/FPA_TECHNICAL_GATES.md docs/reference/PROJECT_STRUCTURE.md docs/reference/README_CHRONOS.md docs/reference/FPA_PROMPT02_EVIDENCE_ADDENDUM.json docs/reference/LOCAL_PILOT_REPORT.md docs/reference/LOCAL_PILOT_EVIDENCE.json
git diff --cached
```

La modification `.gitignore` du chercheur est déjà intégrée au commit extérieur;
son contenu a été préservé et n'a aucun nouveau diff.
Garder hors staging `data/`, `result/`, `.venv/`, source ZIP et handout.
Message proposé : `feat: validate six-series FPA pilot and Monte Carlo estimators`.
Le SHA d'un prochain commit reste inconnu tant que le chercheur ne l'a pas créé.
