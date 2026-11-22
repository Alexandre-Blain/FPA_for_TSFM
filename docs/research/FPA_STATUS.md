# État du projet — 22 novembre 2026

**Premier lot étendu terminé; STOP pour revue ChatGPT–chercheur.**
Lire le **[rapport courant](../reference/FPA_EXTENDED_BATCH_REPORT.md)** pour
les conclusions, incertitudes, coûts et preuves; le [handoff](FPA_HANDOFF.md)
pour reprendre la revue. Aucune seconde collecte autorisée.

Branche `main`, HEAD pré-commit et de collecte
`ea3d78a10280e83e65a2bd7474af3eaf8ee1a905`; arbre propre au départ.
Modifications finales non stagées/non commitées; aucun Git d'écriture par Codex.
Les sources modifiées exécutées sont archivées et hashées avant collecte.

## Expériences réellement terminées

| Étape | Périmètre exécuté | Preuve scientifique |
| --- | --- | --- |
| Phase 2 historique | 3 séries, 7 groupes, 1 400 trajectoires | [Rapport original](../reference/CHRONOS_PHASE2.md) |
| Phase 3 Deliverable A | Contrôles offline; Stage A modèle non exécutée | [Rapport original](../reference/CHRONOS_PHASE3_DESIGN.md) |
| Prompt 2 | M4/T000001, 2 060 trajectoires et timing distinct | [Benchmark](../reference/BENCHMARK_REPORT.md) |
| Pilote multi-séries | 6 séries, 10 cellules, 704 ensembles, 17 280 trajectoires | [Collecte](../reference/LOCAL_PILOT_REPORT.md) |
| Analyse précédente | N20/30/40/60, supports, propagation et CPD; zéro nouveau tirage | [Analyse offline](../reference/LOCAL_PILOT_OFFLINE_ANALYSIS.md) |
| Stage A courant | Comparaisons directes des deux baselines sur données du pilote; gate passé | [Rapport courant](../reference/FPA_EXTENDED_BATCH_REPORT.md) |
| Premier lot étendu | 8 nouvelles identités, 24 blocs denses N20, 44 ensembles frais N60; 34 980 trajectoires au total | [Rapport courant](../reference/FPA_EXTENDED_BATCH_REPORT.md) |

## État vérifié

Collecte complète dans `result/extended_batch_20261122T115422Z/`, terminée
le22 novembre à12:57:43 UTC; analyse terminée à13:07:46 UTC. Les gates de
justesse, des deux premières fenêtres et de reconstruction des pools passent.
Les1 661 ensembles ont chacun une identité RNG et une graine dérivée distinctes.
Reprise complète testée : zéro nouveau tirage et zéro lancement modèle.

**281 tests finaux passent en144.39 s**, six avertissements de retries Windows
réussis;9 tests handout passent en4.10 s. Liens, copies de revue et conservation
des preuves sont contrôlés dans `final_checks.json` et `preservation_after.json`.
Les données, anciens résultats, rapports scientifiques, index Git, `.gitignore`
et poids locaux sont préservés.

Le rapport distingue les rejets directs de baselines, les différences brutes,
la précision, le classement et la généralisation. La précision pratique et le
gain incrémental au-delà de probabilité/J restent ouverts; huit identités ne
sont pas huit sources indépendantes. Les analyses, CSV et figures courants
sont dans `analysis/`;39 assets explicites sont joints au handout renouvelé.

**Prochaine étape unique : revue scientifique45–60 min, zéro modèle.**
Décider seuils pratiques W1/ED, hypothèses confirmatoires, diversité des sources
et budget restant. Cette recommandation n'autorise aucune nouvelle expérience.
Les détails et critères de réfutation restent dans le rapport, source unique
des résultats de cette itération.
