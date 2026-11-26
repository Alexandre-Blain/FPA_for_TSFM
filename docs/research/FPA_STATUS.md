# État du projet — 26 novembre 2026

**Itération exploratoire terminée; STOP pour revue chercheur–superviseur.**
Lire le [rapport scientifique courant](../reference/FPA_EXPLORATORY_BENCHMARK_AND_FINDINGS.md)
puis le [handoff](FPA_HANDOFF.md). Le complément du superviseur est intégré;
aucune application UCR/Kronos implémentée ou exécutée.

Branche `main`, HEAD de collecte et pré-commit
`302b98782cd5ed5a25754c44501526d85b2226cb`, arbre propre au départ.
Modifications locales non stagées; seul le chercheur réalise les écritures Git.

| Exécution réelle | État / source de vérité |
| --- | --- |
| Pilote multi-séries et revue offline | [Collecte](../reference/LOCAL_PILOT_REPORT.md), [analyse](../reference/LOCAL_PILOT_OFFLINE_ANALYSIS.md) |
| Baselines directes et premier lot étendu du22 novembre | [Rapport original](../reference/FPA_EXTENDED_BATCH_REPORT.md), conservé |
| Exploration et benchmarks du24 novembre | 6 nouvelles fenêtres H32;18 blocs denses;8 contrastes N120;6 références naturelles N120 |
| CPD H64 | 3 fenêtres;31 préfixes ×3N20;9 transitions;17 lois fraîches N120 |
| SGA et white-box | Entropies sur chemins existants;2 passes de reload, zéro nouveau tirage |

Run courant : `result/exploratory_benchmark_20261124T095906Z/`.
**1 916 ensembles,43 020 trajectoires,1 314 720 tokens stochastiques**;
1 916 flux et graines dérivées uniques. 44 processus modèle,62,70 min cumulées,
zéro échec. Collecte terminée le24 novembre à11:23:23 UTC.

**Observé :** Australie T000004 b1/2204 conserve un écart d'événement d'environ
+0,55 sur holdout et N120 frais, Holm8=0,0016. Cet événement est déjà découvert
par le sampling naturel. Un seul des six contrastes scientifiques valide ce
seuil; les contrôles et contre-exemples sont conservés.

**Non établi :** gain FPA de fiabilité, précision ou décision aval à coût égal.
Sur les six nouvelles fenêtres, SGA adapté H32 donne NEAURC0,103 contre0,961
pour FPA W1; aucune généralisation avec ce petit panel. Le gain de couverture
des groupes dépasse le gain de masse couverte. CPD :0/9 transition validée.
Aucune preuve de mémorisation ni mécanisme causal par attention.

**Vérifié :**299 tests offline en97,69 s;11 tests handout en3,27 s;
11 contrôles sur objets réels. Les6 998 fichiers data/result préexistants,
poids, index Git et `.gitignore` sont inchangés. Les gels et sources archivées
restent valides. L'audit distingue indices absolus, q50/p_sel, préfixes,
covariance de réutilisation et biais de sélection. Détails et reçus dans le rapport.

**Proposition unique, non autorisée :** benchmark prospectif de fiabilité
FPA vs SGA/sampling sur24 nouvelles séries et au moins4 datasets disponibles,
avec politiques et pertes figées, coût total comparable. Préparation4–8 h;
plafond proposé1 h CPU modèle après gate de timing. Falsificateur : aucun gain
incrémental reproductible une fois le coût payé. La revue doit choisir et
autoriser la suite; ne relancer aucun collecteur depuis une ancienne configuration.
