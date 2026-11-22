# Handoff — analyse offline terminée, revue de campagne attendue

**22 novembre 2026.** Lire le **[rapport courant](../reference/LOCAL_PILOT_OFFLINE_ANALYSIS.md)**,
puis le [statut](FPA_STATUS.md). Le [rapport de collecte original](../reference/LOCAL_PILOT_REPORT.md)
et ses [preuves](../reference/LOCAL_PILOT_EVIDENCE.json) sont conservés.

Branche `main`; HEAD pré-commit de l'analyse :
`ad64422b973aa77a33e99827ced9bdae903b15cb`, arbre initial propre.
HEAD historique de collecte : `62271b156db9d56ffbbd673d24b4d111ccd75f7e`.
Modifications actuelles non stagées; aucun Git d'écriture par Codex.
Le prochain SHA dépend du commit du chercheur. Index et `.gitignore` préservés.

## Exécution et pièces

Analyse autorisée des ensembles complets : **zéro nouveau tirage**, zéro
inférence/replay, téléchargement, installation ou modification du protocole.
Les six séries/dix cellules/704 ensembles/17 280 trajets historiques sont intacts.
Identités conditionnelles, candidats/poids, préfixes et empreintes contrôlés;
704 flux RNG et graines dérivées distincts. Deux fenêtres ont trois N20 chacune.
399 bootstrap par trajectoire et3999 permutations par comparaison; aucun
rééchantillonnage ne crée une nouvelle réplication de série ou de modèle.

Nouveau dossier : `result/local_pilot_20261120T184035Z/offline_analysis_20261122/`.

- `AUTHORIZED_REQUEST.txt`, `analysis_plan.json`, `provenance.json` et snapshots
  de code : autorisation, définitions, pools et hashes.
- CSV précision, supports, propagation, lois continues, compensation et variance;
  `OFFLINE_REVIEW_FIGURES.pdf` : trois pages de diagnostic.
- `preservation_before.json`/`preservation_after.json` : SHA/taille/mtime des
  2 898 fichiers data/result préexistants; `final_checks.json` : remise exacte.
- `offline_tests.txt` : **272 tests passés en107.67 s**, un avertissement de retry
  de publication Windows. Huit nouveaux tests mathématiques; tests handout/liens
  complétés à la remise. Les analyses ne chargent aucun modèle de prévision.

## Conclusions à relire

**Observé :** distances historiques reproduites. Early8/late8 :160/186 W1
alternatives croissants,58/60 nulls,61/186 excès descriptifs. Les nombres
préliminaires dépendent d'une coupure non précisée; trois définitions documentées.
Le null croît avec la dispersion; sa soustraction n'est pas un effet sans biais.

**Observé :** précision améliorée à N40/N60, rangs encore instables. Deux N30
indépendants : rho W1=.064 T000063,.495 SOUTHERN. N60 n'a pas de réplication
indépendante. Quatre branches sélectionnées par graine0 passent Holm sur12
branches avec N40 laissé de côté; d'autres grands N20 s'effondrent au classement.
N20 sert à explorer, pas à confirmer un classement fin.

**Suggéré :** SOUTHERN b0/2229 garde une différence après centrage/différenciation;
aucune preuve isolant la dépendance jointe. Compensation forte dans92/441
contrastes non nuls, sans loi systématique établie. Between corrigé souvent
faible/négatif; dérive continue du même ordre que des écarts de calibration.
Aucune rupture CPD établie. T000049 est très sensible à son petit IQR; les
sensibilités explicites ne changent pas le protocole. Dépendance des séries,
probabilités/J/bins et sélection empêchent une conclusion générale.

## Remise et arrêt

Nouveaux fichiers : module `analysis/chronos_offline_precision.py`, script
`analyze_chronos_pilot_offline.py`, test `test_offline_precision.py`, rapport courant.
Modifiés : index, statut/handoff/décisions, tâche, workflow, guides pratique,
structure/tests et priorité du générateur handout. La liste exacte et les
commandes `git add` sélectives pour le chercheur sont dans le rapport et
`final_checks.json`. Message proposé :
`analysis: assess pilot Monte Carlo precision and campaign sampling`.
Garder hors staging data/result, checkpoints, `.venv`, ZIP et handout.

Handout renouvelé avec le nouveau rapport et pièces PDF/CSV actuelles choisies;
archives exclues. ZIP : `docs/chatgpt-handout.zip`;
entrée : `docs/chatgpt-handout/CHATGPT_HANDOUT.md`.

**Une prochaine étape : revue scientifique ChatGPT–chercheur,45–60 min, zéro modèle.**
Recommandation soumise à approbation : davantage de séries prospectives N20 dense,
puis N60 indépendant pour au plus deux contrastes gelés par fenêtre et témoins
aléatoires. Scénario24 cellules N20 avec marge×2≈1 h33; deux contrastes validés
par fenêtre ajoutent≈16 min20 de génération avec marge, hors chargement/contrôles.
Capture bornée24 primaires≈1.52 Gio bruts. Ce sont des extrapolations, pas un budget
accordé ni une taille suffisante démontrée. Rejeter/adapter le plan si importance
pratique, précision et sélection indépendante ne sont pas fixées. **STOP : aucun
nouveau trajet ou campagne avant décision explicite.**