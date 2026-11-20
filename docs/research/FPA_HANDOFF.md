# Handoff — pilote local en pause

**20 novembre 2026.** Branche `main`, HEAD de départ :
`b9c6a011e14a93235ed90cf88a11a25cead7264a`. Codex n'a effectué aucune écriture
Git. La modification personnelle de `.gitignore` est préservée.

Le chercheur a autorisé [le pilote local](../../codex-prompts/CURRENT_TASK.md) :
six séries originales, jusqu'à dix cellules fenêtre-graine au total
(six primaires + quatre réplications sur deux fenêtres). Il a ensuite demandé
une **pause pour simplifier la documentation**. Aucune inférence nouvelle n'a
été lancée; aucune sélection n'est figée. La tâche reste à reprendre.

## Point de reprise

Checkpoint local : `result/local_pilot_20261120T184035Z/RESUME.json`.
Il conserve l'autorisation originale, les hashes des six fichiers scientifiques
en cours et les étapes restantes.

Déjà fait : stockage isolé par fenêtre/graine, contrôle des objets étrangers,
tests d'exécution entrelacée/interruption/reprise, cas cap8 avec résidu 84 %,
supervision Windows sans ancien plafond arbitraire. Le module de sélection
context-only et sa configuration sont rédigés mais non validés/figés.
**15 tests ciblés passés en 74.49 s**; aucune nouvelle suite complète.

## Prochaine étape à la reprise

Terminer et tester la sélection/QC, puis figer les six fenêtres **avant modèle**.
Ne pas refaire l'audit général ni reprendre depuis zéro. Ensuite : addendum
de provenance N20, driver multi-fenêtres, suite complète, deux cellules validées
avant les quatre autres et les quatre réplications autorisées, calibration et
analyse. Les détails opérationnels et formules sont dans le checkpoint.

Le champ `target_N20` des preuves historiques a été écrasé par une variable
de parsing de liens lors de leur rédaction; le résumé N20 brut est intact.
L'original figé est conservé et le driver intermédiaire N20 n'a pas été
archivé indépendamment : ces limites restent à documenter explicitement.

## Documents et Git

L'[index unique](../README.md) donne les six sources actives, références et
archives. Les définitions restent dans le protocole; les résultats historiques
dans leurs rapports. Le handout exclut les archives par défaut.

Pour le chercheur uniquement : examiner `git status --short` et `git diff`,
puis sélectionner les déplacements documentaires et le générateur/tests.
Ne pas stage les fichiers scientifiques du pilote en pause sans leur revue.
Commandes documentaires suggérées, jamais exécutées par Codex :

```powershell
git add -- README.md AGENTS.md docs codex-prompts project-chatgpt
git add -u -- README_CHRONOS.md CHRONOS_FPA_FUTURE_IDEAS.md FPA_CET1_RESEARCH_HANDOFF.md
git add -- scripts/maintenance/prepare_chatgpt_handout.py tests/chronos_fpa/integration/test_chatgpt_handout.py
git add -- configs/chronos_benchmark_scan/README.md configs/chronos_controlled_pilot/README.md configs/chronos_targeted_refinement/README.md
git diff --cached
```

Message proposé : `docs: simplify active research documentation and archive provenance`.
Le SHA d'un prochain commit n'existe pas encore. Les données, résultats,
checkpoints, source ZIP et handouts générés restent hors staging.
