# État du projet — 20 novembre 2026

Branche `main`, HEAD de départ de l'itération :
`b9c6a011e14a93235ed90cf88a11a25cead7264a`.
Les changements restent unstaged; Codex n'effectue aucune écriture Git.

## Expériences effectivement exécutées

| Étape | Faits observés | Source |
| --- | --- | --- |
| Phase 2 historique | 7 groupes, 1 400 trajets, 3 séries, C512/H64/N50 | [Rapport Phase 2](../reference/CHRONOS_PHASE2.md) |
| Phase 3 Deliverable A | Contrôles offline; Stage A non exécutée | [Rapport Phase 3](../reference/CHRONOS_PHASE3_DESIGN.md) |
| Prompt 2 | Un seul contexte M4/T000001; cellules N2 et N20, 2 060 trajets de collecte + 78 emplacements de timing à graines réutilisées | [Benchmark et limites](../reference/BENCHMARK_REPORT.md) |
| Pilote multi-séries courant | Implémentation partielle, 15 tests ciblés passés; sélection non figée, **0 nouvelle cellule/inférence** | [Handoff de reprise](FPA_HANDOFF.md) |

Le dernier test complet du prototype historique comptait 250 tests passés.
Les 15 tests de la tâche courante ne remplacent pas une nouvelle suite complète.

## Ce qui reste ouvert

Les observations historiques sélectionnées (asymétrie M4, localisation ERCOT,
classements instables et effets proches du contrôle) ne démontrent pas une
information générale au-delà de probabilité/entropie/J. La fiabilité des
mélanges d'issues, la frontière P10/P11, la covariance et la généralisation
entre séries restent à étudier. Voir [les hypothèses](../reference/FPA_HYPOTHESES.md).

Une anomalie de sérialisation du champ `target_N20` dans les
[preuves Prompt 2 figées](../reference/FPA_PROMPT02_EVIDENCE.json) a été identifiée;
un addendum est à produire à la reprise, sans réécrire l'original.

**Tâche courante : pilote en pause à la demande du chercheur.**
La maintenance documentaire n'a modifié ni ses fichiers scientifiques en cours,
ni les données, configurations expérimentales ou résultats. Le point de reprise
et la prochaine étape unique sont dans le [handoff](FPA_HANDOFF.md).
