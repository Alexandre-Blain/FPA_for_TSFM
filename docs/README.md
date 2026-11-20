# Chronos FPA Documentation

Point d'entree pour ne pas se perdre dans le projet.

## Documents courants et transmission a ChatGPT

- [Workflow de recherche actuel](research/README_WORKFLOW_V2.md),
  [statut verifie](research/FPA_STATUS.md),
  [decisions](research/FPA_DECISIONS.md) et [dernier handoff](research/FPA_HANDOFF.md).
- [Bilan Prompt 2](research/BENCHMARK_REPORT.md), [preuves](research/FPA_PROMPT02_EVIDENCE.json)
  et [grille proposee non autorisee](research/FPA_PROPOSED_GRID.json).
- Dossier temporaire genere : `docs/chatgpt-handout/`. Ouvrir son
  `CHATGPT_HANDOUT.md` ou transmettre `docs/chatgpt-handout.zip` a ChatGPT.
  Les copies sont remplacees apres chaque prompt; les originaux restent ici.
- Pour regenerer : `.venv/Scripts/python.exe scripts/maintenance/prepare_chatgpt_handout.py`.
  Le manifeste identifie les chemins sources, hashes et commit de depart.

Les guides ci-dessous restent utiles pour leur objet. Les anciens bilans ne
definissent pas a eux seuls le statut courant ni une autorisation de calcul.

## Guides Principaux

- [Paper 1 : proposition Phase 3](CHRONOS_PHASE3_DESIGN.md)
  Controles par permutation/subsampling, interpretation et budgets soumis a approbation.

- [Paper 1 : pilote Phase 2 termine](CHRONOS_PHASE2.md)
  Sept groupes valides : bruit de sampling, W1/ED, entropie, figures et limites.

- [Workflow Chronos](../README_CHRONOS.md)
  Commandes pratiques, options CLI, outputs, checkpoints, refinement et visualisations.

- [Configs de run](../configs/chronos_benchmark_scan/README.md)
  Fichiers JSON pour lancer les scans sans longues lignes d'arguments.

- [Structure du projet](PROJECT_STRUCTURE.md)
  Organisation des dossiers `code/`, `scripts/`, `configs/`, `data/` et `result/`.

- [Metriques Chronos FPA](CHRONOS_METRICS.md)
  Definitions mathematiques des scores, normalisations, metriques logits et
  metriques temporelles.

- [Guide des graphes](graphes/README.md)
  Explication de chaque figure et de ce qu'il faut regarder.

- [Documentation recherche](recherche/README.md)
  Contexte, etat actuel, resultats recents, axes futurs, biais et controles.

- [Audit math](CHRONOS_MATH_AUDIT.md)
  Verifications de coherence mathematique et smoke tests valides.

## Ordre De Lecture Conseille

1. Lire le [workflow](../README_CHRONOS.md) pour lancer un run.
2. Choisir ou copier une [config de run](../configs/chronos_benchmark_scan/README.md).
3. Lire les [metriques](CHRONOS_METRICS.md) pour comprendre les CSV.
4. Lire le [guide des graphes](graphes/README.md) pour interpreter les figures.
5. Lire la [documentation recherche](recherche/README.md) pour comprendre ou va le projet.
6. Lire l'[audit math](CHRONOS_MATH_AUDIT.md) si une metrique semble suspecte.

## Sources Experimentales Historiques

Le scan propre historique de septembre est :

```text
result/clean_confirm_no_refinement_20260915_114823
```

Le refinement partiel reste une source experimentale utile :

```text
result/refinement_faster_global_20260728_125930
```

Voir [l'audit de maintenance](maintenance/CLEANUP_REPORT.md), les
[tests](../tests/README.md) et l'inventaire d'integrite. Les runs partiels ne
sont ni supprimes ni declasses scientifiquement par leur seule incompletion.

Certains anciens runs Chronos avaient deja ete archives dans :

```text
result/archive/obsolete_chronos_runs/
```

