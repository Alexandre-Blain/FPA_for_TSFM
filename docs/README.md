# Chronos FPA - Documentation

Lire les documents courants avant les anciens bilans. Les dossiers sont
organises par usage; les rapports historiques conservent leur chemin et leur
contenu scientifique.

## 1. Recherche courante

| Besoin | Document |
| --- | --- |
| Travail termine, limites et prochaine etape | [Statut verifie](research/FPA_STATUS.md) |
| Transmission a ChatGPT | [Dernier handoff](research/FPA_HANDOFF.md) |
| Resultats techniques de Prompt 2 | [Benchmark](research/BENCHMARK_REPORT.md), [preuves](research/FPA_PROMPT02_EVIDENCE.json), [tests](research/FPA_PROMPT02_TESTS.txt) |
| Cadre scientifique | [North star](research/FPA_NORTH_STAR.md), [hypotheses](research/FPA_HYPOTHESES.md), [protocole candidat](research/FPA_PROTOCOL_EXPLORATORY.md) |
| Decisions et autorisations | [Decisions](research/FPA_DECISIONS.md), [workflow](research/README_WORKFLOW_V2.md) |
| Proposition non autorisee | [Grille exploratoire](research/FPA_PROPOSED_GRID.json) |
| Organisation et liens des documents | [Bilan de nettoyage](maintenance/DOCUMENTATION_LINKS.md) |

Pour ChatGPT, utiliser le fichier local
`docs/chatgpt-handout/CHATGPT_HANDOUT.md` ou `docs/chatgpt-handout.zip`.
Ces fichiers generes sont ignores par Git : leurs chemins restent en texte
pour ne pas creer de liens GitHub vers des fichiers absents du depot.
Ces copies temporaires sont remplacees apres chaque prompt par
`.venv/Scripts/python.exe scripts/maintenance/prepare_chatgpt_handout.py`.
Le document combine utilise des liens internes; le ZIP inclut les guides
Markdown references et les fichiers documentaires associes.

## 2. Utilisation et methodes

| Besoin | Document |
| --- | --- |
| Commandes et configuration | [Guide pratique](../README_CHRONOS.md), [scan](../configs/chronos_benchmark_scan/README.md), [refinement](../configs/chronos_targeted_refinement/README.md) |
| Emplacement du code et des fichiers | [Structure du projet](PROJECT_STRUCTURE.md) |
| Definitions et calculs | [Metriques](CHRONOS_METRICS.md), [audit mathematique](CHRONOS_MATH_AUDIT.md) |
| Figures et interpretation | [Index des figures](graphes/README.md), [guide detaille](graphes/CHRONOS_FIGURES_GUIDE.md) |
| Validation hors ligne | [Guide des tests](../tests/README.md) |

## 3. Rapports historiques et provenance

| Periode / objet | Document |
| --- | --- |
| Phase 1 : implementation des distances | [Phase 1](CHRONOS_PHASE1.md) |
| Phase 2 : pilote termine | [Phase 2](CHRONOS_PHASE2.md) |
| Phase 3 : controles offline et proposition de replication | [Phase 3](CHRONOS_PHASE3_DESIGN.md) |
| Integration documentaire du 19 novembre | [Rapport](research/FPA_INTEGRATION_REPORT.md), [audit initial](research/FPA_IMPLEMENTATION_AUDIT.md) |
| Anciennes analyses et pistes | [Notes historiques](recherche/README.md) |
| Plan scientifique anterieur | [Plan historique](<future works/FPA_CHRONOS_RESEARCH_PLAN (1).md>) |
| Ancien handoff et idees | [Handoff CET1](../FPA_CET1_RESEARCH_HANDOFF.md), [idees historiques](../CHRONOS_FPA_FUTURE_IDEAS.md) |
| Nettoyage anterieur du depot | [Audit de maintenance](maintenance/CLEANUP_REPORT.md) |

Les expressions "actuel" ou "en cours" dans les anciens documents se rapportent
a leur date d'origine. Elles ne remplacent pas le statut courant et ne donnent
aucune nouvelle autorisation de calcul.

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

