# Handoff — pilote terminé, revue scientifique attendue

**20 novembre 2026.** Branche `main`; départ `b9c6a011e14a93235ed90cf88a11a25cead7264a`.
Un commit extérieur `62271b156db9d56ffbbd673d24b4d111ccd75f7e` (`cleaning doc`)
est intervenu avant le gel : **HEAD de collecte et actuel avant le prochain
commit du chercheur**. Les manifestes l'enregistrent. Aucune écriture Git par
Codex. `.gitignore` personnel préservé; index identique à celui du gel.

Lire le [rapport courant](../reference/LOCAL_PILOT_REPORT.md), ses
[preuves](../reference/LOCAL_PILOT_EVIDENCE.json), puis le
[statut](FPA_STATUS.md). Six sources actives dans `docs/research/`, références
et rapports dans `docs/reference/`, plans remplacés dans `docs/archive/`.

## Exécution et artefacts

Pilote autorisé terminé : **6 séries originales, 10 cellules, 704 ensembles,
17280 trajets**, dont 10200 primaires et 7080 de calibration; 100 positions b0..9.
Deux fenêtres préchoisies ont trois graines, sans nouvelles séries induites.
H32/C512/N20, résidu, null indépendant, P0..15 et overlaps conservés.
Inputs figés avant modèle; les deux premières fenêtres ont passé le gate avant
les suivantes. Zéro tentative échouée; reprise des dix cellules sans modèle.

Dossier : `result/local_pilot_20261120T184035Z/`.

- `frozen.json`, `selection_manifest.json`, `selected_contexts.npz`, `cell_plan.json` :
  population, rejets, six contextes et dix cellules.
- `source_at_collection/`, `source_manifest.json`, `environment.json`, `model_cache.json` :
  32 fichiers de collecte archivés, environnement et poids épinglés/hashés.
- `first_two_gate.json`, `cells/<id>/complete.json`, `pilot_complete.json` : objets
  locaux finalisés avec hashes, pas des commits Git.
- `analysis/summary.json`, CSV et `analysis/PILOT_FIGURES.pdf` : 23 pages de figures.
- `attempts/` : ressources Windows; `resume_verification.json` et logs pytest.
  L'ancien `RESUME.json` conserve le point de pause historique, désormais dépassé.

**264 tests hors ligne passent en 108.24 s; 2924 contrôles réels de parité passent.**
Arbres modèle : 1165.002 s (19 min 25 s), pic engagé 1.259 Gio; RAM système libre
minimale 584.8 Mo. Aucun téléchargement, installation, second modèle ou Stage A.
48 chemins choisis avant leurs issues capturent toutes couches/têtes/32 queries;
tous les autres tokens/valeurs et prérequis de replay sont conservés.

## Conclusions utiles et limites

Isolation/persistance/mesures validées sur ce panel. 60/186 distances W1 sont
≤ leur null indépendant. T000049 a un IQR pathologique face au changement de
niveau; grand W1/IQR et grand null se suivent. Les rangs N20 ne sont pas stables
sur les graines calibrées. Écarts d'issues jusqu'à 0.35, compatibles avec les
bornes conservatrices calculées; aucune preuve d'égalité ou absence de biais.
Covariance P9/P10 et variance P10/P11 explicitement analysées.

Séries distinctes mais domaines dépendants; deux séries par dataset, diversité
sélectionnée, chevauchement d'entraînement possible. Information au-delà de
J/p/entropie, motif et causalité interne restent non vérifiés.
Le [correctif historique](../reference/FPA_PROMPT02_EVIDENCE_ADDENDUM.json)
préserve l'original; le lanceur N20 intermédiaire exact reste non archivé.

## Remise et arrêt

Changements restants unstaged; maintenance et préparation partiellement
intégrées par le commit extérieur.
`git status --short` exact et tous chemins/reasons/hashes sont dans les preuves;
commandes `git add` sélectives proposées dans le rapport, pour le chercheur seul.
Ne pas stage données, résultats, checkpoints, `.venv`, source ZIP ou handout.
`.gitignore` n'a aucun nouveau diff. Message proposé :
`feat: validate six-series FPA pilot and Monte Carlo estimators`.
Le SHA d'un prochain commit reste inconnu tant que le chercheur ne l'a pas créé.

Handout régénéré avec PDF/CSV nommés par `--review-assets`; archives exclues.
ZIP courant : `docs/chatgpt-handout.zip`; entrée lisible :
`docs/chatgpt-handout/CHATGPT_HANDOUT.md`.

**Une prochaine recommandation : revue scientifique 45–60 min, zéro modèle.**
Rejeter un lancement si cible de précision absente, conclusion seulement portée
par l'IQR de T000049, ou prétention de rang stable contredite par les graines.
Le plan proposé de 24 nouvelles séries/32 cellules (~2 h 04 avec marge) exige
une autorisation séparée. Aucun calcul supplémentaire ne suit ce handoff.
