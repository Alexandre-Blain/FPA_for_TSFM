# Workflow de recherche

L'index documentaire unique est [docs/README.md](../README.md).
Il distingue six documents actifs, les références et les archives.

1. **État local.** Codex lit l'objectif, le statut, le journal de décisions,
   le protocole et le handoff. Les manifestes et objets expérimentaux complets
   prévalent sur les résumés narratifs.
2. **Autorisation.** Le chercheur définit la tâche, les cellules ou ressources
   permises et les critères d'arrêt. La tâche actuelle est
   [le pilote local](../../codex-prompts/CURRENT_TASK.md), momentanément en pause.
   Aucun ancien prompt archivé ne vaut autorisation.
3. **Travail.** Codex implémente, teste et exécute seulement le périmètre autorisé.
   Les résultats complets sont publiés atomiquement; les analyses lisent des
   instantanés immuables. Les fichiers historiques ne sont pas régénérés.
4. **Handoff.** Mettre à jour le statut et le handoff; ajouter seulement les
   décisions réelles au journal. Les définitions scientifiques restent dans
   le protocole, les détails d'un résultat dans son rapport.
5. **Git et revue.** Le chercheur seul stage, commit et push. Codex fournit les
   changements et tests. ChatGPT relit le handoff, le rapport courant et ses
   preuves; les fichiers du Projet sont des instantanés, pas un miroir du disque.
6. **Suite.** Une revue scientifique détermine la prochaine tâche autorisée.
   Aucun élargissement automatique du pilote à une campagne.

Après chaque étape terminée, régénérer le handout avec
`scripts/maintenance/prepare_chatgpt_handout.py`. Il contient les sources actives
et références utiles, sans archives. Les copies sont remplacées après contrôle
des hashes; un fichier inattendu ou modifié manuellement bloque leur suppression.
Le mode `--check-links` vérifie les liens locaux sans modifier les documents.

Pour ChatGPT, utiliser les [instructions du Projet](../../project-chatgpt/PROJECT_INSTRUCTIONS.md).
Les hypothèses et rapports utiles sont accessibles depuis l'index; ne pas
réimporter systématiquement tous les anciens plans et audits.
