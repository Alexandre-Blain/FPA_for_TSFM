# Documentation FPA / Chronos

Pour comprendre et reprendre le projet, lire **l'objectif, le statut puis le
handoff**. Les six documents actifs ci-dessous font autorité pour le workflow
courant. Les rapports et archives ne constituent pas des ordres d'exécution.

## Documentation active — docs/research/

| Question | Source de vérité |
| --- | --- |
| Quel est l'objectif scientifique ? | [Objectif et contributions candidates](research/FPA_NORTH_STAR.md) |
| Quel protocole utiliser ? | [Protocole expérimental](research/FPA_PROTOCOL_EXPLORATORY.md) |
| Qu'a-t-on réellement exécuté et appris ? | [Statut et limites](research/FPA_STATUS.md) |
| Où reprendre et quelle est la prochaine étape ? | [Handoff](research/FPA_HANDOFF.md) |
| Quelles décisions ont été validées ? | [Journal chronologique](research/FPA_DECISIONS.md) |
| Comment travailler entre chercheur, Codex et ChatGPT ? | [Workflow](research/README_WORKFLOW_V2.md) |

Le pilote multi-séries est **en pause à la demande du chercheur**.
Son autorisation détaillée est conservée dans
[la tâche courante](../codex-prompts/CURRENT_TASK.md).

## Documentation de référence — docs/reference/

- [Hypothèses et explications concurrentes](reference/FPA_HYPOTHESES.md),
  [sources scientifiques](reference/FPA_REFERENCES.md).
- [Définitions des métriques](reference/CHRONOS_METRICS.md),
  [audit mathématique](reference/CHRONOS_MATH_AUDIT.md),
  [contrats techniques](reference/FPA_TECHNICAL_GATES.md).
- [Benchmark Prompt 2](reference/BENCHMARK_REPORT.md),
  [preuves originales](reference/FPA_PROMPT02_EVIDENCE.json),
  [tests de ce benchmark](reference/FPA_PROMPT02_TESTS.txt).
- Rapports scientifiques : [Phase 1](reference/CHRONOS_PHASE1.md),
  [Phase 2 terminée](reference/CHRONOS_PHASE2.md),
  [Phase 3 : contrôles offline et ancien design](reference/CHRONOS_PHASE3_DESIGN.md).
- [Guide pratique](reference/README_CHRONOS.md),
  [structure du code](reference/PROJECT_STRUCTURE.md),
  [tests](../tests/README.md), [figures](reference/CHRONOS_FIGURES_GUIDE.md).

## Archives — docs/archive/

[Anciens travaux et preuves de maintenance](archive/) : plans remplacés,
prompts terminés, notes historiques et audits. Ils conservent leur provenance
et ne gouvernent pas le travail actuel. Les anciens chemins dans les manifestes
figés décrivent leur instantané d'origine. Les données et résultats n'ont pas
été déplacés.

## Transmission à ChatGPT

`docs/chatgpt-handout/CHATGPT_HANDOUT.md` et `docs/chatgpt-handout.zip` sont
des copies locales jetables, ignorées par Git. Les régénérer avec :

```powershell
.venv/Scripts/python.exe scripts/maintenance/prepare_chatgpt_handout.py
```

Le générateur exporte les documents actifs et les références nécessaires,
avec des liens vérifiés. **Les archives ne sont pas exportées automatiquement.**

