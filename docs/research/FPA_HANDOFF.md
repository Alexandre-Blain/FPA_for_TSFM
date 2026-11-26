# Handoff — 26 novembre 2026

**TERMINÉ; STOP pour revue scientifique.** Commencer par le
[rapport courant](../reference/FPA_EXPLORATORY_BENCHMARK_AND_FINDINGS.md),
qui contient résultats, littérature, audit, limites et commandes offline.
Le [lot précédent](../reference/FPA_EXTENDED_BATCH_REPORT.md) était déjà terminé
le22 novembre; ses preuves sont préservées. Le complément du superviseur
n'a ajouté aucune expérience UCR/Kronos.

## État et preuves

Branche `main`; HEAD initial et pré-commit
`302b98782cd5ed5a25754c44501526d85b2226cb`; arbre initial propre.
Aucun stage/commit/push/pull/changement de branche par Codex.
Un nouveau SHA est inconnu jusqu'au commit du chercheur.

Run : `result/exploratory_benchmark_20261124T095906Z/`.
Collecte le24 novembre, terminée à11:23:23 UTC; synthèse finale le26 novembre.
Chronos-T5-mini original CPU float32, quatre threads, batch8, révision
`bd6a4fde8403b8469acd0abd52852b29dbe61c7b`.

Deux datasets nouveaux, Londres/Australie : six séries originales C512/H32,
b0..9,3N20 par loi;8 contrastes frais N120 (6 scientifiques,2 contrôles);
6 références naturelles N120 réservées. H64 :3 contextes réutilisés,31 préfixes
×3N20 et9 transitions,17 lois fraîches N120. Total1 916 ensembles et43 020
trajectoires;1 916 flux et graines dérivées distincts.44 processus modèle,
62,70 min cumulées, zéro échec; pic Job1,26 Gio. Aucun entraînement ni expansion.

Gels : `frozen.json`, `source_at_collection/`, `validation_plan.json`,
`benchmark_plan.json`, `source_at_validation/`; provenance, RNG et captures
dans le run. `remaining_execution.json` confirme la fin de toutes les phases.
Replays : `whitebox/pass1.json`, `pass2.json`, exacts sur deux processus.
Les tenseurs du sampling online initial n'existent pas : pas de preuve
d'équivalence rétroactive online. Rapports historiques intacts.

## Ce que nous avons appris

**Observé :** T000004 b1/2204, écart de direction_reversal +0,55, reproduit
holdout et N120, Holm8=0,0016. Cet événement existe déjà dans31/120 chemins
naturels; ce n'est pas un gain de découverte ou de décision démontré.
La plupart des autres contrastes sélectionnés s'atténuent; CPD0/9 validé.

**Non établi :** supériorité FPA de fiabilité, précision ou utilité aval.
SGA adapté H32 classe mieux les erreurs ici (NEAURC0,103 vs FPA W1 0,961),
sur seulement six sources dépendantes et deux datasets. Pas de mémorisation
démontrée, ni d'explication causale par les cartes d'attention.

**Hypothèse :** localiser des décisions plausibles changeant une conséquence
utile, puis démontrer un gain de risque ou de décision face à SGA à coût égal.
UCR et Kronos sont des pistes de faisabilité dans le rapport, pas des acquis.

## Vérifications et fichiers

299 tests offline passent en97,69 s;11 tests handout en3,27 s.
11 contrôles d'audit réels passent; partition q50, indices, plafonds, sélection
bloc0, préfixes, RNG, W1 et replay vérifiés. Les6 998 fichiers préexistants
data/result, poids, `.gitignore` et index Git sont inchangés.
Preuves : `analysis/postcollection_audit.json`, `tests_final.txt`,
`preservation_after.json`, `resume_verification.json`, `final_checks.json`.

`git status --short` exact : `RUN/git_status_final.txt` (RUN=chemin ci-dessus).
Nouveaux : descripteurs discovery, configuration datée, préparateur, collecteur,
replay, quatre analyses/figures, quatre tests et rapport. Modifiés : navigation,
documents actifs, tâche, générateur/tests handout. Aucun fichier supprimé.
Les chemins complets et commandes `git add --` sélectives proposées sont dans
le rapport; ne pas utiliser `git add -A`. Message proposé :
`Add bounded FPA discovery benchmarks and critical application review`.
Le chercheur relit et exécute lui-même ces commandes.

Handout jetable : `docs/chatgpt-handout/CHATGPT_HANDOUT.md` et
`docs/chatgpt-handout.zip`, avec PDF7 pages et CSV scientifiques explicites.
Garder data/result, poids, venv et handout hors Git.

## Prochain gate unique

Revue chercheur–superviseur avant toute nouvelle inférence. Recommandation
proposée : benchmark prospectif commun FPA/SGA/sampling,24 séries nouvelles
sur au moins4 datasets éligibles, politiques figées et coût total mesuré.
Préparation4–8 h, plafond proposé1 h CPU modèle après timing.
Falsificateur : aucun gain incrémental reproductible au-delà des baselines
et de son coût. Aucun choix d'application ni ce budget n'est encore autorisé.
