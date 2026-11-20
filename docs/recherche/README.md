# Documentation recherche - Chronos FPA

**Notes historiques :** les resultats et pistes ci-dessous sont conserves comme
sources. Pour le travail courant, lire le [statut](../research/FPA_STATUS.md),
les [decisions](../research/FPA_DECISIONS.md) et le
[workflow versionne](../research/README_WORKFLOW_V2.md). Les formulations anciennes
« actuel » ou « en cours » restent datees de leur rapport d'origine.

Ce dossier sert de fil conducteur pour le projet. Il separe le contexte, l'etat
de la pipeline, les resultats, les limites et les prochaines idees.

## Paper 1 : Etat Au 2026-11-17

Le [bilan Phase 2](../CHRONOS_PHASE2.md) est le point d'entree actuel pour les
nouvelles distances W1/ED et leurs controles independants. Le pilote reduit est
termine : 7/7 groupes, trois series, douze forks alternatifs distincts. Les
analyses finales sont dans
`result/phase2_controlled_pilot_20261116_195533/analysis_half/`.
Les conclusions historiques ci-dessous ne doivent pas etre confondues avec
ce nouveau protocole. La Phase 3 reste une proposition non lancee.
Voir les [controles offline et le design Phase 3](../CHRONOS_PHASE3_DESIGN.md) :
permutations de trajectoires entieres, stabilite, descripteurs morphologiques
simples et budget de replication. Aucune nouvelle inference n'a ete lancee.

## Ordre de lecture

1. [Contexte recherche](01_CONTEXTE_RECHERCHE.md)
2. [Etat actuel](02_ETAT_ACTUEL.md)
3. [Resultats recents](03_RESULTATS_RECENTS.md)
4. [Axes futurs](04_AXES_FUTURS.md)
5. [Biais, limites et controles](05_BIAIS_LIMITES_CONTROLES.md)
6. [Analyse du refinement faster_global 20260728](06_REFINEMENT_FAST_GLOBAL_20260728.md)
7. [Incertitude modele vs FPA](07_INCERTITUDE_MODELE_VS_FPA.md)
8. [Scenarios decisionnels generiques](08_SCENARIOS_DECISIONNELS.md)

## Documents techniques associes

- [Workflow pratique Chronos](../../README_CHRONOS.md)
- [Definition des metriques](../CHRONOS_METRICS.md)
- [Audit mathematique](../CHRONOS_MATH_AUDIT.md)
- [Structure du projet](../PROJECT_STRUCTURE.md)

## Runs de reference

Scan large propre :

```text
result/topology_temporal_single_20260724_175602
```

Refinement cible en cours :

```text
result/refinement_faster_global_20260728_125930
```

Presentation associee :

```text
presentations/chronos_fpa_findings_topology_temporal.pptx
```
