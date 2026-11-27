# État du projet — 27 novembre 2026

**Campagne H1/H2 terminée au gate E. Revue chercheur avant toute nouvelle tâche.**
Résultats et limites détaillés dans le
[rapport scientifique](../reference/FPA_INCREMENTAL_VALUE_AND_EVENT_SAMPLING.md);
pièces de transmission et reprise dans le [handoff](FPA_HANDOFF.md).

**Observé : aucun gain FPA robuste démontré.** H1 M3−M1 donne un petit gain
MASE interne (delta NEAURC−0,0510, IC comprenant zéro), puis une dégradation
sur Weather OOD (+0,0542). Aucun des trois tests primaires n'est significatif
après Holm. Les contrôles secondaires ne remplacent pas ces résultats.

H2 ne valide pas la comparaison primaire à coût égal : le MC destiné à apparier
Neyman consomme1,879 fois son temps réel. Poids et estimateurs sont validés,
sans avantage pratique démontré. Cela ne prouve ni équivalence ni impossibilité
d'une autre méthode FPA. La narration C, résultats limités, est retenue.

Run : `result/incremental_campaign_20261126T132759Z/`.
Résultats courants : `analysis_v2/`, PDF six pages et29 tables d'origine
inchangées. H1 complet320/320, cinq datasets/trois domaines :
153 train,51 validation,52 test interne,64 Weather OOD.
H2 complet29/36, références N2000;11 fenêtres à dix répétitions,
9 London/9 Electricity/9 Weather/2 Traffic. Les7 autres fenêtres sont préservées
et exclues; le retrait équilibré prévu n'a pas été respecté.

Arrêt automatique27 novembre07 h28 Luxembourg, au plafond :
57 624,883 s enregistrées, soit24,883 s au-delà de16 h.
**Échec de conformité au temps**, sans nouvelle inférence. Environ486 Mo nouveaux
à la coupure, sous20 Gio. Les effectifs minimaux sont atteints, sans garantie
de puissance ou représentativité; sous-ensemble figé avant les cibles.

**Validé :**320 tests en217,35 s; audit des30 225 flux RNG,833 164 trajectoires,
2 026 cellules stratifiées/IS et alignement des349 cibles; conservation des
11 611 anciens fichiers, index Git et `.gitignore`. Source et gel du calcul
initial préservés après une erreur d'arrondi graphique; finalisation version2
limitée au tracé, sans changer une valeur des29 tables. Six figures inspectées.

**Limites :** un seul dataset OOD, canaux corrélés possibles, exposition
pré-entraînement in-domain, faibles nombres de datasets, pilote H2 partagé,
référence finie, échec d'appariement. L'audit mathématique ne supprime pas
ces biais de dessin. Le rapport quantifie les effets et les coûts.

Une seule suite proposée, **non autorisée/non exécutée** : diagnostic offline
d'appariement sur les pools naturels existants,0 s modèle, après revue chercheur.
Le handout courant est régénéré avec PDF/CSV explicites, sans archives.
Branche `main`, HEAD avant commit chercheur
`a5b6ef6743832f09bfa096078104b727dc84f373`; aucun Git write Codex.
Les [résultats précédents](../reference/FPA_EXPLORATORY_BENCHMARK_AND_FINDINGS.md)
et les artefacts historiques sont conservés.
