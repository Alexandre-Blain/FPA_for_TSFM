# FPA exploratoire : benchmarks et phénomènes scientifiques

**Collecte du 24 novembre 2026 terminée. Synthèse et complément du superviseur :
26 novembre 2026. STOP pour revue scientifique.**

Un effet conditionnel important se reproduit, mais **aucun gain pratique FPA
sur la fiabilité, la précision ou une décision aval n'est établi**. SGA est un
concurrent sérieux : son adaptation évaluée ici classe mieux les erreurs que
nos scores FPA sur les six nouvelles séries. Les résultats de découverte sont
plus favorables à la couverture des groupes qu'à la masse probabiliste couverte.

Source locale : branche `main`, HEAD initial propre et pré-commit
`302b98782cd5ed5a25754c44501526d85b2226cb`. Sources exécutées modifiées localement,
archivées et hashées avant collecte. Aucun Git d'écriture par Codex; un éventuel
nouveau SHA restera inconnu jusqu'au commit du chercheur.

Dans ce rapport, `RUN` désigne
`result/exploratory_benchmark_20261124T095906Z/`.
[Autorisation originale](../../codex-prompts/CURRENT_TASK.md), copie exacte
`RUN/AUTHORIZED_REQUEST.txt`; complément exact `RUN/SUPERVISOR_ADDENDUM.txt`.
Le [lot précédent](FPA_EXTENDED_BATCH_REPORT.md), terminé le 22 novembre,
reste distinct et conservé. Ses validations de baselines n'ont pas été relancées.

## I. Évaluation scientifique à froid

Avant cette itération, les distances conditionnelles étaient mesurables, certaines
baselines numériques échouaient localement, mais les classements N20 étaient
instables et l'utilité prédictive restait ouverte. L'analyse offline initiale
des huit fenêtres précédentes confirme cette réserve : NEAURC du forecast moyen,
largeur d'intervalle 0,505, FPA dense W1 0,540, sparse W1 0,528. Plus faible est
meilleur; ce résultat ne désigne pas FPA comme meilleur estimateur de fiabilité.

Cette itération ajoute deux identités de datasets, six fenêtres C512/H32, trois
blocs indépendants N20 par loi, huit contrastes N120 frais, un N120 naturel
indépendant par fenêtre, trois fenêtres H64 et deux replays white-box dans des
processus différents. La sélection des fenêtres utilise uniquement les contextes;
les huit contrastes viennent uniquement du bloc 0. Les méthodes et outcomes sont
figés avant l'ouverture de la référence naturelle N120.

Le gate des deux premières fenêtres a passé à 10:31:56 UTC, les 18 blocs denses
étaient complets à 11:01:27 UTC, et toutes les phases bornées à 11:23:23 UTC,
le 24 novembre. Le complément n'a ajouté aucun tirage, modèle ou dataset.

| Phase réellement exécutée | Ensembles | Trajectoires |
| --- | ---: | ---: |
| H32 dense, 6 fenêtres × 3 blocs | 1 590 | 31 800 |
| H32, 8 contrastes frais, alternative/référence/null N120 | 24 | 2 880 |
| Référence naturelle indépendante N120 | 6 | 720 |
| H64, 3 fenêtres × 31 préfixes × 3 blocs | 279 | 5 580 |
| H64, 9 transitions, préfixes frais N120 dédupliqués | 17 | 2 040 |
| **Total** | **1 916** | **43 020** |

Les 1 916 flux RNG et graines dérivées sont distincts. Les trajectoires ne sont
pas des unités de réplication inter-séries. H64 réutilise trois des six contextes.
Les séries australiennes partagent un domaine électrique; les dates des fenêtres
ne sont pas alignées. La comparaison d'exposition n'est pas randomisée.

## II. Observations et hypothèses classées

### 1. Un token peut déplacer une conséquence sans grand saut numérique — observé localement

Australie `T000004`, b1/token2204 : probabilité de **direction_reversal**,
définie par des moyennes initiale/finale sur huit pas de signes opposés au-delà
de ±0,25 IQR du dernier contexte. L'écart alternative−référence vaut +0,55 au
bloc 0, +0,575 au holdout N40, puis **+0,55 au N120 frais** : 80/120 contre
14/120, bootstrap ponctuel [0,458; 0,658], p Monte Carlo 0,0002, Holm8 0,0016.
J=0,0648 IQR; W1 sur les 22 pas strictement post-fork=0,0561 IQR, contre
0,0128 pour référence/null de même token.

La baseline de translation persistante prédit 0,500 et AR1 0,525 contre 0,667
observé. Ces résidus sont descriptifs : le test formel porte sur alternative vs
référence, pas sur le rejet de ces deux modèles. Neutraliser uniquement la
coordonnée forcée dans les chemins sauvegardés réduit l'écart à **+0,442**.
Cette sensibilité posthoc montre qu'une partie de l'événement dépend de la
coordonnée imposée; elle n'est pas une nouvelle intervention échantillonnée.

La branche a q50=0,0453, masse du préfixe greedy=0,1896 et masse de première
déviation=0,00859. Sa contribution estimée à la probabilité naturelle de
l'événement vaut 0,00572, pas 0,667. La référence naturelle retrouve déjà cet
événement **31/120 fois**. Le résultat porte donc sur la localisation d'une
sensibilité conditionnelle, pas sur la découverte d'un futur absent du sampling.

Contre-exemple : `T000002` b0/2201 conserve +0,15 sur holdout et frais, mais
Holm8=0,1008; ce signal reste **suggéré**, pas validé à 5 % dans cette famille.
Seul 1/6 contraste scientifique franchit ce seuil, contre 0/2 contrôles
aléatoires. Ces deux contrôles ne suffisent pas à estimer un taux d'enrichissement.

Explications concurrentes : seuil près d'une moyenne, dynamique locale et
conditionnement sur un préfixe particulier. FPA/Forking Fast savent déjà
localiser des décisions conséquentes; l'extension numérique n'établit pas à
elle seule une nouveauté méthodologique. Décision aval candidate : déclencher
une revue d'un scénario fragile. Falsificateur : aucun gain de risque sélectif
ou de détection d'événements, à coût égal, sur de nouvelles séries non choisies
pour leurs effets, après contrôle de J et de l'entropie.

### 2. Les grands effets exploratoires tardifs se reproduisent mal — observé

Londres `T003562` b4/2100 : le candidat «manqué par sparse» passe de −0,35
au bloc 0 à −0,025 au holdout puis +0,025 au N120. `T003248` b8/2142 passe
de +0,15 à +0,10 puis −0,058. Le contrôle aléatoire australien b6 passe de
+0,15 à −0,025 puis +0,067. La sélection sur un maximum bruité explique
une part substantielle des premières impressions. Inversement, l'effet b1
ci-dessus persiste : tous les écarts ne sont pas du bruit.

La somme des conséquences retenues par sparse est un écran descriptif, pas un
test validant chaque branche manquée. Des préfixes tardifs ont parfois une masse
naturelle extrêmement faible : le contraste londonien b8 ne pèse qu'environ
6,4×10⁻¹² comme première déviation. Son intérêt conditionnel ne garantit aucune
importance pour les décisions usuelles.

Hypothèse utile : privilégier des forks à masse plausible pourrait économiser
des validations. La sélection des points influents et ses biais sont déjà connus
en FPA et en resampling de raisonnement; aucune nouveauté revendiquée pour cette
idée. Falsificateur : sur un panel prospectif, une politique sparse fixée ne
réduit pas le coût à utilité aval conservée, ou manque l'effet précoce validé.

### 3. Couvrir davantage de groupes n'apporte qu'un petit gain de masse — observé, utilité ouverte

À 40 chemins par méthode, contre le N120 naturel réservé, rappel moyen des
groupes : naturel 0,843, dense 0,939, regular3 0,967. Masse empirique couverte :
**0,983, 0,987 et 0,999** respectivement. Ces moyennes portent sur six fenêtres,
une seule allocation sauvegardée par méthode et des groupes définis par des
seuils fixes; elles ne démontrent pas une supériorité générale. Pour `T003562`,
le naturel couvre tous les groupes observés, dense seulement 5/6 et 95 % de
la masse. Les groupes supplémentaires ne sont pas des modes prouvés.

Exemple historique plus stable : `currency_8`, événement terminal_down, absent
de chacun des trois N20 naturels. L'estimation par première déviation vaut
3,22 %, 3,50 %, 3,38 % sur les blocs indépendants. Un N60 naturel manquerait
un événement à 3,37 % avec une probabilité d'environ 13 %. La stratification
paie beaucoup plus de lois conditionnelles; cet exemple n'établit pas un gain
à coût égal. Les nouveaux événements absents du N120 ont généralement une
masse très faible et des réplications proches de zéro.

FPA pourrait aider une décision sensible à un événement rare et coûteux; la
couverture brute n'est alors pas la bonne métrique. Le sampling stratifié et
les regroupements existent déjà; l'apport potentiel serait un meilleur coût
par risque aval estimé. Falsificateur : l'avantage disparaît contre davantage
de sampling naturel, ou les groupes supplémentaires ne changent aucune décision.

## III. Méthodes conventionnelles et SGA

Tous les indicateurs classent les **mêmes forecasts H32 et mêmes cibles**.
Le forecast primaire est la moyenne des 60 chemins P0 naturels; greedy et
médiane sont des sensibilités séparées. Les indicateurs ne voient jamais les
cibles. MAE, MAE/IQR et MASE sont sauvegardés; MASE utilise le lag contextuel
48 pour les nouveaux datasets. Pour l'ancien FX, lag1 est explicitement une
convention exploratoire, pas une reproduction du benchmark SGA.

| Indicateur, six fenêtres, forecast moyen | NEAURC | Spearman vs MASE |
| --- | ---: | ---: |
| SGA, code auteur adapté H32, moyenne de 3×K20 | **0,103** | 0,771 |
| Nombre de groupes de trajectoires | 0,692 | 0,174 |
| Dense FPA ED | 0,858 | 0,086 |
| Sparse FPA W1, positions0/4/9 | 0,935 | 0,086 |
| Entropie locale q50 | 0,945 | −0,314 |
| Dense FPA W1 | 0,961 | 0,029 |
| Saut numérique moyen | 1,055 | −0,257 |
| Écart-type naturel moyen | 1,066 | −0,314 |
| Largeur d'intervalle80 % | 1,075 | −0,371 |
| Entropie des groupes | 1,100 | −0,143 |
| 1−probabilité moyenne du token greedy | 1,269 | −0,486 |

NEAURC=(AURC−oracle)/(random−oracle), intégration trapézoïdale sur couvertures
1/n..1; les égalités de score utilisent le risque attendu dans les permutations
liées. Une valeur >1 est possible. Ce classement descriptif ne mesure ni
calibration ni amélioration de précision. Avec greedy, SGA reste à 0,208 contre
0,532 pour l'intervalle et 0,616 pour FPA W1. Les n=3 par dataset et n=6 globaux
ne permettent pas une conclusion de généralisation ou un test de supériorité
inter-datasets crédible. Une séparation entre datasets peut suffire à bien classer.

**Reproduction SGA exacte dans son périmètre.** La méthode construit un graphe
de tranches de trajectoires et fournit un score d'incertitude du forecast entier,
évalué par classement des erreurs. Voir [l'article](https://arxiv.org/html/2609.28582v1).
Le [code auteur](https://github.com/zhangsq-nju/SGA/tree/03d8133912c4e5c813cae084ca5f5358d7e5a206)
a été épinglé : tranches4, seuil DTW/longueur0,25, échelle d'erreur saisonnière
avec plancher10⁻⁴, fusion au premier nœud compatible, parents uniques,
alpha0,1, poids racine1 et nœud1+entropie. Ces conventions du code ne sont pas
identiques à toutes les équations imprimées. Quatre fixtures exécutant le
constructeur auteur et notre port donnent les mêmes nœuds/arêtes et une erreur
maximale de score de 2,85×10⁻¹³.

Pour chaque nouvelle fenêtre, trois K20 naturels ont leurs **entropies top20
renormalisées correspondant aux vrais chemins** récupérées par replay. Leur
coût de replay total est 76,17 s hors rechargements. H32/q50, moyenne de trois
scores K20 et forecast commun N60 sont nos adaptations; les résultats publiés
sur l'ensemble du benchmark auteur ne sont pas reproduits. Les anciens chemins
sans entropies correspondantes ne reçoivent pas de faux score SGA. SGA traite
les mêmes chemins naturels pour A2; ce post-traitement ne crée pas de nouveaux
futurs. Son coût de graphe/replay doit être ajouté à celui du sampler.

**Coûts réellement enregistrés.** 1 314 720 tokens stochastiques; génération des
ensembles 46,21 min; 44 processus modèle surveillés totalisent 62,70 min, zéro
échec. Cela inclut chargements, greedy, logits et replay, pas seulement les
tirages. Pic mémoire Job 1,26 Gio; mémoire système libre minimale379 Mio.
Téléchargement limité aux quatre parquets autorisés : 614 245 275 octets,
349,70 s. Le run avant figures finales occupait environ570 Mo; les tailles
finales sont dans la clôture. Chronos-T5-mini original CPU float32/eager,
quatre threads, batch8; révision `bd6a4fde8403b8469acd0abd52852b29dbe61c7b`.
Ni ces coûts globaux ni un nombre égal de chemins n'établissent à eux seuls
une égalité des budgets d'une méthode déployée.

## IV. Efficacité d'échantillonnage

Comparaisons offline exactes sur **tokens déjà observés** : dense, early3,
regular3, random3, entropy3; probabilité2, extrêmes numériques2, stratification2;
allocations uniformes ou pondérées. Les politiques utilisent contexte et logits
greedy; les méthodes à chemins nouveaux non sauvegardés restent non testées.
«Stratification2» choisit des rangs numériques parmi les tokens collectés;
ce n'est pas une exploration de tout le vocabulaire.

Part moyenne de la somme des écarts d'événements du holdout N40 conservée :
early3 43,5 %, entropy3 42,5 %, regular3 34,7 %, random3 31,1 %, extrêmes2
46,5 %, probabilité2 21,9 %, stratification2 31,9 %. Cette somme utilise des
maxima d'écarts Monte Carlo bruités; sa valeur ne constitue pas une utilité
aval ni une proportion d'effets validés. Le candidat «sparse miss» N120 n'a
justement pas confirmé son grand effet initial.

Le budget en chemins est évalué séparément du budget en temps. Les estimations
de coût proratisé d'un sous-ensemble sont étiquetées comme telles. Une seconde
comparaison n'utilise que des ensembles N20 entiers, leurs temps enregistrés,
un ordre de politique fixe, et s'arrête avant dépassement, sans sauter une cellule
coûteuse après avoir vu son temps. Sur les douze budgets naturels N20/N40,
rappel moyen naturel0,798, dense0,700, random3 0,748. Granularité N20 et budget
inutilisé pénalisent parfois FPA. Encoder, logits de sélection, greedy et
rechargement partagés sont exclus de ce seul tableau : **ce n'est pas un test
prospectif de latence bout en bout**. Aucun avantage de coût robuste n'est acquis.

Les fréquences forcées ne sont jamais interprétées comme des probabilités
naturelles. Pour l'événement E, la partition disjointe utilise
Σb [∏j<b q50(gj)] Σt≠gb q50(t|g<b) P(E|g<b,t), avec résidu explicite,
puis la masse «dix premiers tokens greedy» et sa loi de continuation.
Les poids somment à1. Les SE sont conditionnels aux lois et logits fixes,
optimistes près de zéro, et ne mesurent pas l'incertitude entre sources.

## V. Exposition au préentraînement

La [publication originale Chronos](https://arxiv.org/html/2403.07815v2) classe
M4 Daily et London Smart Meters comme in-domain; ERCOT, Exchange Rate et
Australian Electricity comme zero-shot. Elle réserve les derniers horizons
d'évaluation : M4 Daily14, Londres/Australie48. L'appartenance au dataset
n'atteste pas qu'un segment précis a été tiré pendant le préentraînement.

Les nouveaux exports viennent de `autogluon/chronos_datasets`, révision
`eeecad0b82a8c237e212ce6f8d1abecb513e2cec`, split nommé `train` qui contient
aussi les dernières valeurs d'évaluation; ce nom ne prouve donc pas l'exposition.
[Carte du dataset épinglée](https://huggingface.co/datasets/autogluon/chronos_datasets/blob/eeecad0b82a8c237e212ce6f8d1abecb513e2cec/README.md).

| Dataset / série | Origine, index0 | Offset depuis fin | Statut des32 cibles | MAE/IQR |
| --- | ---: | ---: | --- | ---: |
| Australie T000004 | 230672 | 64 | zero-shot32 | 0,190 |
| Londres T002383 | 33856 | 80 | potentiellement exposées32 | 0,717 |
| Australie T000003 | 230720 | 64 | zero-shot32 | 0,492 |
| Londres T003562 | 29744 | 64 | potentielles16, heldout16 | 0,315 |
| Australie T000002 | 232208 | 64 | zero-shot32 | 0,066 |
| Londres T003248 | 30208 | 32 | heldout32, in-domain | 0,695 |

La fréquence réelle des six sources est vérifiée sur les timestamps complets :
30min régulières; décalage initial de1 s pour Londres. Trois IDs distincts
par dataset; cinq séries d'État australiennes disponibles contre5 560 ménages
londoniens. La sélection uniforme/diversité est contextuelle. Les suffixes des
strates brutes partagés entre datasets ne sont **pas** des étiquettes d'exposition;
`documented_pretraining_status` et les indices font autorité.

Le lead affiché1 correspond à l'index `origine`; les étiquettes originales
ont été recalculées indépendamment et sont correctes. Pour les anciens M4 H32,
le découpage publié implique18 valeurs potentiellement exposées puis14 heldout,
mais les exports historiques sans révision et correspondance d'ID d'origine
ne permettent pas de certifier une appartenance effective segment par segment.

Les courbes sont comparées aux mêmes leads et à une baseline saisonnière lag48.
Pour la fenêtre londonienne mixte, l'erreur moyenne/IQR vaut0,431 sur les16
premiers pas et0,199 sur les16 suivants : ce contraste confond lead et exposition.
Le tableau par lead conserve cette limite. Même fréquence ne retire ni
l'agrégation ménage/État, ni la saisonnalité, ni le régime ou la date. Les lags48
contextuels australiens vont de0,754 à0,899, londoniens de0,260 à0,292.
Le sélecteur initial utilise notamment lag24, soit12 h à cette fréquence;
les lags48/336 sont des diagnostics ajoutés après sélection, sans la modifier.
**Aucune preuve spécifique de mémorisation; même une association causale
d'exposition n'est pas identifiée par ces six séries.**

## VI. CPD H64 et white-box

CPD porte sur Londres `T003562`, Australie `T000004` et `T000003`. Les préfixes
P0..P30 sont tous directement échantillonnés; terminal63 et late56..63 restent
fixes sur la courbe. Il n'y a pas de frontière mélange/direct à confondre avec
une transition. Les deux transitions scientifiques et le contrôle de chaque
fenêtre sont figés après le bloc0, avant les blocs indépendants et les N120.
17 lois fraîches suffisent grâce au partage de P14 dans deux comparaisons.

**0/9 transition rejette après Holm9; aucune ne conserve son sens dans les trois
étapes bloc0/holdout/frais.** Londres P22→23 passe de−0,40 à0 puis−0,133,
p=0,0538, Holm=0,484. Une bande bootstrap ponctuelle excluant0 ne remplace
pas ce test corrigé. Les profils suggèrent une évolution sous conditionnement
greedy croissant, mais les sauts locaux sélectionnés ne sont pas validés comme
des change points. Cela n'établit pas l'absence de tout effet à N120.

White-box : fork conséquent validé, plus faible **contraste d'événement**,
contrôle même token et sentinelle de capture originale. Un événement faible
n'implique pas une loi proche du null : `T000003` b0/2198 garde W1=0,165 IQR.
Deux processus frais distincts vérifient chemins/valeurs, logits capture/plain,
hidden states, self-attention et cross-attention. Les25 champs comparés au
reload sont exacts, erreur max0; la sentinelle concorde aussi avec les tenseurs
**teacher-forced** enregistrés lors de la collecte. Les activations du sampling
online initial n'ont pas été conservées : leur équivalence reste invérifiable.

Les divergences commencent après l'entrée du token dans le décodeur : query b
ne l'a pas encore vu, b+1 l'a vu. Les visualisations révèlent aussi des
divergences importantes pour deux continuations indépendantes de même token.
Un seul couple de chemins par cas, pas de comparaison causale de mécanismes,
de probe ou de SAE. Une carte d'attention n'est pas une attribution causale.

## VII. Conséquences pour Paper1

La contribution primaire la plus défendable est pour l'instant une **hypothèse** :
localiser, puis pondérer par leur plausibilité, les décisions de génération qui
changent une conséquence utile. La preuve actuelle est un contraste conditionnel
reproduit; la preuve manquante est son utilité face à SGA et davantage de sampling.
La meilleure alternative est une caractérisation critique des sensibilités
numériques et de leurs limites, sans revendiquer une meilleure incertitude.

Objection principale : les scores FPA coûtent davantage et peuvent mesurer la
sensibilité à des préfixes très improbables sans améliorer une décision réelle.
Les résultats de classement favorisent SGA ici. Si un benchmark indépendant et
budgété ne trouve aucun gain incrémental, il faudra restreindre la contribution
à l'analyse conditionnelle ou changer d'application; un p significatif entre
deux continuations ne suffira pas.

L'expérience confirmatoire candidate et la recommandation unique sont précisées
ci-dessous. **Ce sont des propositions, aucune n'a été exécutée ou autorisée.**

## Paper 1 Application and Novelty Assessment - Supervisor Feedback

### Méthodes proches et limites de nouveauté

| Travail / tâche et estimand | Accès et coût | Évaluation / acquis | Apport FPA encore à prouver |
| --- | --- | --- | --- |
| [SGA](https://arxiv.org/html/2609.28582v1) : incertitude d'un forecast entier | K chemins; probabilités pour entropies; graphe/DTW en plus | NEAURC des erreurs; topologie temporelle déjà étudiée | Gain de fiabilité ou découverte décisionnelle à coût égal; graphe et dynamique ne sont pas nouveaux |
| [Forking Paths](https://arxiv.org/abs/2412.07961) : influence d'un token sur l'issue textuelle | Accès à continuation conditionnelle, sans poids nécessaires; rollouts par préfixe | Distributions d'issues et tokens influents | Conséquences numériques et utilité aval; forking et profils d'issues déjà présents |
| [Forking Fast](https://github.com/ericb-goodfire/forking-fast) : calcul de profils conditionnels | Accès modèle/cache; nombreuses continuations | Outils de sampling et courbes d'outcomes | Mesure coût/utilité; ni cache de préfixes ni CPD ne constituent seuls une nouveauté |
| [Thought Anchors](https://arxiv.org/abs/2506.19143) : importance d'étapes de raisonnement | Environ100 rollouts pour l'attribution contrefactuelle; accès interne pour attention/suppression | Importance de phrases, connexions d'attention et interventions | Une conséquence utile en prévision; attribution d'étapes et comparaison d'attention existent |
| [Thought Branches](https://arxiv.org/abs/2510.27484) : influence par resampling, résilience et médiation | Nombreux rollouts conditionnels, parfois sélection répétée | Changements de décisions; limites des éditions off-policy | Étendre l'estimand numérique; distributions de continuations et interventions plausibles existent |
| [Incertitude sémantique](https://www.nature.com/articles/s41586-024-07421-0) : désaccord entre sens des réponses | Sampling et regroupement sémantique, modèle d'équivalence éventuel | Détection de réponses erronées | Regrouper des trajectoires n'est pas nouveau; nos bins ne sont pas une équivalence sémantique validée |
| [Prédiction sélective](https://arxiv.org/abs/1705.08500), intervalles/variance/diversité | Scores directs ou chemins; calibration séparée pour garanties | Risque vs couverture, abstention | Même forecast et même perte, comparer le risque accepté et le coût total; pas seulement une corrélation |

Pour le sampling naturel, les estimands d'événement sont E_q[1E] et leurs
fréquences Monte Carlo; pour un fork, E_q[1E|préfixe,token]. Ils ne répondent
pas à la même question sans pondération. Une incertitude de forecast, une
amélioration de précision et une politique de décision demandent chacune leur
propre évaluation. Ces acquis réduisent fortement l'espace des revendications
de nouveauté fondées uniquement sur les visualisations ou le forçage de tokens.

### Route1 : fiabilité des forecasts, FPA versus SGA

**Comparaison commune la plus défendable :** garder le même forecast naturel,
classer sa perte MASE par les différents indicateurs, comparer les courbes de
risque/couverture et NEAURC, à budget total mesuré. Le résultat actuel est une
première comparaison sur données existantes, favorable à SGA; il ne valide pas
une stratégie d'abstention calibrée. Le futur test doit compter aussi sélection,
logits, greedy, replay et graphe, et dépenser le temps économisé par un concurrent
en sampling supplémentaire. Les références d'évaluation ne servent pas à choisir
les méthodes. Une réduction de risque à couverture donnée est une meilleure
fiabilité sélective, pas une amélioration de tous les forecasts.

**Recommandation unique, après accord de la revue :** une validation prospective
de cette route sur24 nouvelles séries, au moins4 datasets avec population
d'identités suffisante, préfixes sélectionnés sans cibles. Vérifier les IDs
disponibles avant de fixer le plan; l'Australie n'offre que deux États encore
inutilisés ici et ne doit pas fournir artificiellement six nouvelles unités.
Figer3 positions et au plus2 tokens par position, N20 conditionnels, naturel
N20/40/60 et SGA sur les mêmes chemins, référence indépendante N120 pour A2;
ne choisir aucun meilleur score après consultation du test. Critère primaire :
différence de risque sélectif/NEAURC à coût égal, incertitude regroupée par
source et dataset; A2 est secondaire, pondéré par coût d'événement préfixé.
Estimation de préparation4–8 h et plafond proposé1 h de modèle CPU, à vérifier
sur un gate de timing avant collecte, jamais à dépasser automatiquement.
Falsificateur : pas de gain FPA reproductible au-delà de SGA/sampling/J/entropie
sur le panel indépendant, ou gain absorbé par son coût. Ce plan est plus petit
qu'un nouveau dense et réutilise le code validé; il reste à pré-enregistrer.

### Route2 : UCR, compléter puis classifier — faisable sous conditions

[UCR](https://www.timeseriesclassification.com/) fournit des séries étiquetées,
mais leur origine et leur normalisation ne garantissent pas un problème causal
de décision précoce. Les travaux de [TEASER](https://arxiv.org/abs/1908.03405)
évaluent déjà quand une classe est suffisamment fiable pour être annoncée.
La [revue et le benchmark ECTS](https://arxiv.org/html/2406.18332v6) distinguent
prédiction/déclenchement et approches anticipatrices; [Wu et al.](https://arxiv.org/abs/2102.11487)
mettent en cause les hypothèses de départ et la fuite par normalisation complète.
Notre pipeline précis Chronos→classifieur est une proposition; aucune
reproduction de performance forecast-then-classify n'a été réalisée ici.

Design minimal proposé : deux datasets bruts à début d'observation justifiable,
deux préfixes fixés (50/75 %, suffixes≤64), jusqu'à100 exemples test par dataset.
Séparer train, calibration/choix et test par individu/source quand disponible.
Entraîner un classifieur complet indépendant, par exemple MiniROCKET+logistique,
et le calibrer sur données réelles réservées; entraîner aussi les classifieurs
de préfixe. Sélectionner toute normalisation sur train ou préfixe observé. Des
exports déjà z-normalisés sur la série complète ne sont pas rendus sans fuite
par une seconde normalisation du préfixe; les exclure ou limiter l'affirmation.

Pour une classe c, πc=E_q[f_c(préfixe,Ysuffixe)] est la distribution des sorties
du classifieur sous les futurs Chronos. **Ce n'est pas automatiquement la vraie
probabilité de classe** : une calibration sur séries réelles ne garantit rien
sur les complétions synthétiques. Mesurer variation de π sous forks, erreurs
de classe, Brier/log-loss, calibration, risque/couverture, coût délai+erreur et
temps d'inférence. Les bins de trajectoires seuls ne suffisent pas.

Baselines : classifieur du préfixe avec seuil de confiance calibré; complétion
naturelle N20/N40, intervalle/entropie/token/J, SGA si son score est pertinent
pour la même erreur; observation complète comme plafond d'information. Une
baseline d'anticipation/déclenchement ECTS empêche de confondre gain FPA et simple
prévision du futur. Comparer les mêmes budgets de modèle **et de classifieur**.
Pour agréger les branches forcées, utiliser q et résidu, jamais leurs fréquences
uniformes. Ne modifier que le suffixe causal; masquer un trou avec des points
observés à sa droite est une autre tâche d'imputation.

Valeur attendue : une conséquence de classe directement interprétable et une
décision «annoncer/attendre». Risques : suffixes hors distribution, classe déjà
déterminée par le préfixe, contexte court pour Chronos, déclenchement choisi sur
test, normalisation avec fuite, dépendance entre fragments du même sujet. Arrêter
le pilote si aucune version brute adaptée n'est disponible ou si la complétion
naturelle dégrade fortement les baselines de préfixe. Estimation prospective :
2–4 jours de préparation/validation et1–2 h CPU de génération au plus pour ce
petit pilote, à mesurer; aucune dépendance, donnée ou classification ajoutée ici.

### Route3 : Kronos financier — faisable, adaptation substantielle

[Kronos, article et appendiceD](https://arxiv.org/html/2508.02739v1) utilise une
tokenisation multivariée de bougies OHLCVA et une génération autorégressive
hiérarchique. Ses métriques publiées sont **IC/RankIC** pour prix et rendements,
**MAE/R²** pour volatilité réalisée, scores de génération et TSTR; le backtest
rapporte **Annualized Excess Return et Information Ratio**. IC des prix est
calculé le long de chaque prévision par canal; IC des rendements compare les
vecteurs de rendements, pas le même axe. Le test publié commence après juin2024.
Sharpe/Sortino et drawdown seraient des métriques complémentaires de notre
proposition, pas les métriques principales publiées attribuées à tort à Kronos.

Le [code inspecté](https://github.com/shiyu-coder/Kronos/blob/67b630e67f6a18c9e9be918d9b4337c960db1e9a/model/kronos.py)
échantillonne s1 puis s2 conditionnel à s1, et moyenne les échantillons avant
de rendre les prédictions. L'adaptateur devra exposer chaque paire de tokens,
ses probabilités et chaque chemin avant moyenne. Forcer s1 doit laisser s2 être
tiré sous la nouvelle condition; forcer s2 exige de garder s1 fixe. Un token
latent n'est pas un bin scalaire de prix; reprendre l'indexation W1 de Chronos
sans redéfinir l'estimand serait incorrect.

Point technique vérifié dans [module.py](https://github.com/shiyu-coder/Kronos/blob/67b630e67f6a18c9e9be918d9b4337c960db1e9a/model/module.py) :
le bloc d'attention utilise un flag causal dépendant de `training`. À l'inférence
incrémentale, la dernière query ne voit que le préfixe disponible; un replay
teacher-forced complet en mode eval peut en revanche voir les tokens ultérieurs.
Le décodeur du tokenizer reconstruit aussi des positions à partir de plusieurs
latents. Il faudra tester cette non-localité, préserver le contexte observé et
vérifier la parité incrémentale avant toute capture interne ou optimisation.
Archive de lecture du code/licence dans `RUN/references/Kronos/`; aucun modèle
Kronos chargé, installé ou exécuté.

**A. Fiabilité/sélection du risque :** conserver les forecasts Kronos natifs et
tester si FPA identifie pertes/prévisions ou décisions fragiles, à couverture
égale, contre variance, quantiles/downside risk et sampling additionnel.
Expérience la moins coûteuse : une fréquence quotidienne, un univers fixé,
par exemple20 actifs ×60 origines non chevauchantes, C40/H12 conforme à une
configuration publiée, séparation chronologique calibration/test et purge H.
Préfixer le coût d'événement et l'algorithme de sélection avant test; incertitude
regroupée par date/actif. Cette taille est un gate de faisabilité, pas une preuve
de rentabilité. Un simple classement des pertes peut éliminer une mauvaise idée
avant de construire tout un backtest.

**B. Amélioration de forecast :** nécessite un algorithme explicite, par exemple
une pondération de chemins apprise uniquement sur calibration puis gelée.
Comparer ses IC/RankIC et MAE de volatilité aux prédictions natives et à plus de
sampling; supprimer des trades ne démontre pas une précision accrue. Pour une
décision financière, ajouter un backtest chronologique distinct : signaux
disponibles au moment de l'ordre, exécution au bar suivant, univers point-in-time,
splits/dividendes, frais/slippage/rotation, benchmark commun, IR/excès de rendement
et drawdown. Prévenir survivance, recouvrement des horizons et sélection de
stratégie sur test. Aucun gain financier ne découle du contraste Chronos observé.

Coût prospectif estimé : 3–5 jours d'adaptation, données et parité; plusieurs jours
supplémentaires pour un backtest crédible. Budget d'inférence à mesurer sur un
micro-gate matériel, ordre indicatif1–4 h GPU pour le pilote, sans garantie issue
des temps Chronos. Cette étude n'autorise ni poids, ni données de marché, ni GPU.

### Comparaison des routes

| Route candidate | Information scientifique / coût | Objection décisive | Priorité proposée |
| --- | --- | --- | --- |
| Fiabilité FPA vs SGA | Code et métriques déjà disponibles; comparaison aval directe | FPA peut perdre contre SGA et le sampling supplémentaire | **1**, panel indépendant borné ci-dessus |
| UCR / classes sous futurs générés | Conséquence lisible, décision annoncer/attendre | Validité/calibration des complétions et fuites de prétraitement | 2, si un problème causal brut est identifié |
| Kronos / risque et signaux | Application économique mesurable | Nouvelle tokenisation, loi de sampling, données et backtest | 3, gate de parité avant étude de bénéfice |

Le contraste validé soutient la possibilité d'une sensibilité conditionnelle;
il ne soutient aucune performance UCR/Kronos. SGA fournit déjà un bon classement
local. La contribution qui resterait distinctive est une **amélioration mesurée
de décision ou d'estimation d'un risque coûteux grâce à l'intervention**, avec
coût total et évaluation indépendante. C'est l'hypothèse à réfuter en premier.

## Audit final, preuves et reprise

L'audit demandé vérifie : gels collection/validation; reconstruction des huit
choix à partir du seul bloc0; plafonds, préfixes et rôles; séparation q50/p_sel;
partition de première déviation; RNG; W1 strictement post-fork par l'identité
des échantillons triés; frontière temporelle; reçus de replay et indexation b+1.
Les bootstrap réutilisent les mêmes indices pour un préfixe/référence partagé;
Holm8 et Holm9 restent des familles distinctes, bandes ponctuelles non simultanées.
Les tests de labels binaires permutent des chemins complets via leur loi
hypergéométrique, jamais des horizons supposés indépendants.

**Aucune erreur de loi d'échantillonnage ou d'indexation scientifique détectée.**
Une suspicion initiale de décalage de frontière a été réfutée par recalcul :
zéro étiquette changée,16/16 vérifié. Les sources et sorties figées restent
intactes. `exposure_by_lead_verified.csv` ajoute les indices source pour revue.
Les biais de sélection exploratoire, le petit nombre de sources, les contrôles
numériques descriptifs, les seuils d'événement et le coût offline incomplet
restent des limites explicites; aucun audit ne garantit l'absence de tout biais.

**299 tests offline passent en97,69 s**. Un premier passage avait296 succès et
un échec de renommage Windows du handout. Le générateur utilise désormais une
reprise bornée des verrous transitoires et préserve les fichiers après échec
persistant; deux tests supplémentaires couvrent les deux cas. Onze contrôles
d'audit sur objets réels passent. Les6 998 fichiers data/result préexistants
ont les mêmes tailles, mtimes et SHA256; index Git, `.gitignore` et poids locaux
sont inchangés. Les hashes des anciens rapports restent vérifiables par le diff.
L'audit documentaire vérifie60 fichiers Markdown et218 liens locaux, sans lien
cassé; les11 tests spécifiques au handout passent en3,27 s.

Preuves sous `RUN` : `frozen.json`, `source_at_collection/`,
`validation_source_manifest.json`, `source_at_validation/`, `validation_plan.json`,
`benchmark_plan.json`, `dataset_provenance.json`, `rng_plan.json`,
`dense_complete.json`, `remaining_execution.json`, `whitebox/pass1.json`,
`whitebox/pass2.json`, `analysis/postcollection_audit.json`, `tests_final.txt`,
`preservation_before.json`, `preservation_after.json` et `final_checks.json`.
La clôture et le handout contiennent les vérifications de liens et de reprise.

Le PDF scientifique autonome contient7 pages. Les CSV sélectionnés couvrent
benchmarks, probabilités, coûts, validation, provenance et replay. Ils sont joints
explicitement au handout, sans import automatique d'archives ou de tenseurs bruts.
Les copies de `docs/chatgpt-handout/` sont jetables; modifier les sources canoniques.

Reproduction **offline uniquement**, depuis la racine, sans relancer de collecteur :

```powershell
.venv/Scripts/python.exe scripts/viz/review_chronos_discovery.py result/exploratory_benchmark_20261124T095906Z --analyze
.venv/Scripts/python.exe scripts/viz/finalize_chronos_discovery.py result/exploratory_benchmark_20261124T095906Z
.venv/Scripts/python.exe scripts/viz/plot_chronos_discovery.py result/exploratory_benchmark_20261124T095906Z
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe scripts/maintenance/prepare_chatgpt_handout.py --check-links
```

L'analyse recalcule ses propres sorties dérivées; les objets bruts ne sont pas
réécrits. Les deux premiers scripts vérifient les sources figées : conserver
leurs versions archivées pour reproduire l'itération après une future modification.

### Changements et propriété Git

Nouveaux : `analysis/chronos_discovery.py` sous `code/chronos_fpa/`, configuration
datée, préparateur des deux datasets, collecteur borné, replay sans sampling,
quatre scripts d'analyse/figures/finalisation, quatre fichiers de tests et ce
rapport. Modifiés : générateur et tests handout, entrées de navigation, tâche,
objectif, statut, handoff et décisions. Aucun fichier historique supprimé ou
déplacé. Le statut exact est enregistré dans `RUN/git_status_final.txt`.

À garder hors Git : `data/`, `result/`, poids, `.venv`, handout et ZIP. Le chercheur
relit les diffs et choisit les fichiers; commandes **proposées, non exécutées** :

```powershell
git add -- code/chronos_fpa/analysis/chronos_discovery.py configs/chronos_discovery/iteration_20261124.json
git add -- scripts/data/prepare_chronos_discovery_data.py scripts/runs/run_chronos_discovery.py scripts/runs/replay_chronos_discovery.py
git add -- scripts/viz/analyze_chronos_discovery.py scripts/viz/review_chronos_discovery.py scripts/viz/finalize_chronos_discovery.py scripts/viz/plot_chronos_discovery.py
git add -- tests/chronos_fpa/unit/test_discovery.py tests/chronos_fpa/unit/test_discovery_validation.py tests/chronos_fpa/unit/test_discovery_finalization.py tests/chronos_fpa/integration/test_discovery_collections.py
git add -- scripts/maintenance/prepare_chatgpt_handout.py tests/chronos_fpa/integration/test_chatgpt_handout.py tests/README.md
git add -- docs/README.md docs/reference/README_CHRONOS.md docs/reference/PROJECT_STRUCTURE.md docs/reference/FPA_EXPLORATORY_BENCHMARK_AND_FINDINGS.md
git add -- codex-prompts/CURRENT_TASK.md docs/research/FPA_NORTH_STAR.md docs/research/FPA_STATUS.md docs/research/FPA_HANDOFF.md docs/research/FPA_DECISIONS.md docs/research/README_WORKFLOW_V2.md
```

Message proposé : `Add bounded FPA discovery benchmarks and critical application review`.
**STOP : aucune route candidate ni campagne supplémentaire lancée.**
