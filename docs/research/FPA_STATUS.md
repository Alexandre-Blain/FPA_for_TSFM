# État du projet — 22 novembre 2026

Branche `main`; HEAD de cette analyse, avant tout nouveau commit du chercheur :
`ad64422b973aa77a33e99827ced9bdae903b15cb`. Arbre propre au départ; modifications
courantes non stagées. Aucun Git d'écriture par Codex. Index et `.gitignore`
préservés. Le HEAD de **collecte** du pilote reste `62271b156db9d56ffbbd673d24b4d111ccd75f7e`.

## Travail réellement exécuté

| Étape | Faits observés | Source |
| --- | --- | --- |
| Phase 2 historique | 7 groupes, 1400 trajets, 3 séries, C512/H64/N50 | [Phase 2](../reference/CHRONOS_PHASE2.md) |
| Phase 3 Deliverable A | Contrôles offline; Stage A non exécutée | [Phase 3](../reference/CHRONOS_PHASE3_DESIGN.md) |
| Prompt 2 | Un contexte M4/T000001, N2/N20, 2060 trajets +78 emplacements de timing à graines réutilisées | [Benchmark](../reference/BENCHMARK_REPORT.md) |
| Pilote multi-séries terminé | 6 séries, 10 cellules, 704 ensembles, 17 280 trajets; 48 chemins capturés | [Collecte et preuves](../reference/LOCAL_PILOT_REPORT.md) |
| Analyse scientifique hors modèle terminée | Reconstruction brute, N20/30/40/60, propagation, supports W1/ED, CPD continue/compensation et variance corrigée | **[Rapport courant](../reference/LOCAL_PILOT_OFFLINE_ANALYSIS.md)** |

Analyse autorisée du 22 novembre : **zéro inférence, téléchargement ou installation**.
Toutes les identités et empreintes des cellules complètes sont vérifiées avant pooling;
704 flux RNG et graines dérivées distincts. Les sorties nouvelles sont dans
`result/local_pilot_20261120T184035Z/offline_analysis_20261122/`;
la collecte et son ancien dossier `analysis/` restent inchangés.

**272 tests offline passent en107.67 s**, un avertissement de retry Windows.
Huit nouveaux tests mathématiques; contrôles documentaires/handout ciblés au
handoff. Les figures et CSV courants sont joints explicitement au handout.
Le dossier d'analyse contient plans, code hashé, contrôles de conservation et tests.

## Résultats actuels et limites

- **Observé :** distances historiques reproduites à l'arrondi; 60/186 alternatives
  ont W1 complet ≤ null. Early8/late8 :160/186 W1 alternatives croissent,
  58/60 nulls et61/186 excès descriptifs. Les nombres préliminaires157/59/59
  ne sont pas reproduits sous les trois coupures explicites testées.
- **Observé :** N40/N60 réduisent le bruit; les deux N30 disjoints ont des
  corrélations W1 de.064 T000063 et.495 SOUTHERN. Aucune réplication N60/N60
  indépendante. N20 ne permet pas de classement fin fiable.
- **Observé :** quatre branches sélectionnées sur graine0 passent les tests W1/ED
  sur N40 indépendant, Holm sur12 branches. Une différence ne démontre pas une
  importance pratique ni une information au-delà de J/p/entropie.
- **Suggéré :** SOUTHERN b0/2229 garde une différence de forme après centrage;
  pente et variance restent des explications. Aucun cas robuste isolant la seule
  loi jointe à moyennes similaires sur les trois graines.
- **Observé :** compensation ≥50 % dans92/441 contrastes binaires non nuls,
  sans preuve de compensation systématique; biais between important,120/480
  estimates finales corrigées négatives. Dérive CPD souvent comparable au bruit
  entre estimateurs; aucune rupture structurelle établie.
- **Observé :** T000049 reste pathologique sous IQR (.065); sensibilités std/range
  explicitement séparées, sans modification du protocole. Six séries ne sont pas
  une grande population indépendante; ERCOT/devises peuvent dépendre entre elles.

Les preuves originales et le [correctif historique N20](../reference/FPA_PROMPT02_EVIDENCE_ADDENDUM.json)
restent des références distinctes; elles ne décrivent pas une nouvelle exécution.

## Prochaine étape unique

**STOP pour revue ChatGPT–chercheur,45–60 min, zéro modèle.** Recommandation
non approuvée : nouvelles séries prospectives N20 dense, validation indépendante
N60 de contrastes gelés et de témoins aléatoires. Définir importance pratique,
précision cible, sélection et multiplicité avant toute nouvelle collecte.
Aucune campagne, modification de N ou Stage A autorisée par ce résultat.
Le [handoff](FPA_HANDOFF.md) fournit les pièces et la remise Git sélective.