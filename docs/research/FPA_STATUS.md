# État du projet — 20 novembre 2026

Branche `main`, HEAD de départ `b9c6a011e14a93235ed90cf88a11a25cead7264a`.
Commit extérieur `62271b156db9d56ffbbd673d24b4d111ccd75f7e` (`cleaning doc`)
avant le gel : **HEAD de collecte et actuel avant le prochain commit**.
Changements restants unstaged; aucune écriture Git par Codex.
`.gitignore` personnel préservé; index inchangé depuis le gel.

## Expériences réellement exécutées

| Étape | Faits observés | Source |
| --- | --- | --- |
| Phase 2 historique | 7 groupes, 1400 trajets, 3 séries, C512/H64/N50 | [Phase 2](../reference/CHRONOS_PHASE2.md) |
| Phase 3 Deliverable A | Contrôles offline; Stage A non exécutée | [Phase 3](../reference/CHRONOS_PHASE3_DESIGN.md) |
| Prompt 2 | Un contexte M4/T000001, N2/N20, 2060 trajets de collecte +78 emplacements de timing à graines réutilisées | [Benchmark](../reference/BENCHMARK_REPORT.md) |
| Pilote multi-séries terminé | **6 séries, 10 cellules, 704 ensembles, 17280 trajets**, 100 positions, 48 chemins capturés; zéro tentative échouée | [Rapport courant](../reference/LOCAL_PILOT_REPORT.md) |

Suite finale hors ligne : **264 tests passés en 108.24 s**.
Parité réelle : 2924 contrôles passés. Arbres modèle : 1165.002 s;
pic engagé des Jobs : 1.259 Gio. Aucun téléchargement ni changement de dépendances.
Inputs/sources figés avant collecte; objets et hashes dans
`result/local_pilot_20261120T184035Z/`. [Preuves détaillées](../reference/LOCAL_PILOT_EVIDENCE.json).

## Résultats et limites

- **Observé :** isolation fenêtre/graine, résidu et reconstruction des mesures
  validés; cap8 réel à quatre positions, couverture90 % manquée à deux positions,
  masse résiduelle conservée. Reprise complète sans modèle vérifiée.
- **Observé :** 60/186 alternatives primaires ont W1 ≤ leur contrôle indépendant.
  T000049 présente un IQR très faible face au changement de niveau : son grand
  W1/IQR est accompagné d'un null presque aussi grand.
- **Observé :** écarts entre estimateurs jusqu'à 0.35; aucun des 180 contrastes
  de calibration n'exclut zéro sous les bornes Hoeffding conservatrices calculées.
  Cela ne démontre pas l'absence de biais. 268/960 SE primaires sont nulles
  malgré une incertitude finie non nulle.
- **Observé :** rangs de branches N20 instables entre graines sur les deux fenêtres
  calibrées. Six séries distinctes ne garantissent pas indépendance statistique.
- **Suggéré / non vérifié :** asymétries et hétérogénéité possibles; information
  au-delà de J/p/entropie, motifs et rupture structurelle non établis.

Le [correctif N20](../reference/FPA_PROMPT02_EVIDENCE_ADDENDUM.json) préserve
l'original et confirme les 25 modules archivés. Le lanceur exact intermédiaire
historique reste une limite de provenance.

## Prochaine étape unique

**STOP pour revue scientifique hors modèle (45–60 min, zéro tirage).** Examiner
précision N20, normalisation et dépendance des séries avant toute campagne.
Le rapport propose 24 nouvelles séries /32 cellules, sans autorisation d'exécution.
Le [handoff](FPA_HANDOFF.md) fournit les pièces, limites et remise Git au chercheur.
