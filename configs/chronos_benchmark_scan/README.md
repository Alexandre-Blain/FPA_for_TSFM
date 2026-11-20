# Chronos Benchmark Scan Configs

Ces fichiers remplacent les longues lignes d'arguments.

## Paper 1 (Optionnel)

`trajectory_metrics` (false) ajoute W1/ED strictement apres le fork et un
controle independant avec le meme token. `save_trajectories` (false) sauvegarde
les samples individuels et implique ces metriques. `sampling_seed` (0) fixe
les flux RNG par fenetre/fork/token. Ces options necessitent `branch_modes`
egal a `single` et se transmettent au refinement automatique. Elles ne changent
pas le score historique. Voir [schema et formules](../../docs/reference/CHRONOS_PHASE1.md).

Commande :

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_benchmark_scan.py `
  --config configs\chronos_benchmark_scan\broad_with_refinement.json
```

Les valeurs sont dans l'objet JSON `parameters`. Les noms sont les noms Python
`argparse`, donc avec `_` au lieu de `-`.

Exemple :

```text
num_samples              -> --num-samples
auto_refinement          -> --auto-refinement
refinement_branch_steps  -> --refinement-branch-steps
```

Un argument donne explicitement dans la CLI override le fichier JSON.

Chaque run sauvegarde :

```text
input_config.json
config.json
checkpoint.json
run_state.json
branch_groups/
```

`input_config.json` est la config demandee. `config.json` est la config resolue
avec tous les parametres effectivement utilises. `run_state.json` est ecrit
avant le calcul ; `branch_groups/` contient les sauvegardes atomiques faisant
foi. Les CSV globaux peuvent etre reconstruits a la reprise.

## Fichiers Disponibles

- `smoke.json`
  Test minimal pour verifier que la pipeline marche.

- `default.json`
  Scan raisonnable sans refinement automatique.

- `broad_with_refinement.json`
  Scan de travail recommande : scan large puis refinement automatique cible.

## Parametres Scan Principal

- `model_id`
  Modele Chronos utilise. Garder `amazon/chronos-t5-mini` pour l'instant.

- `device`
  `cpu`, `cuda`, ou `null` pour laisser le loader choisir.

- `source`
  `benchmark-folder` pour les exports Chronos locaux, `csv-folder` pour un
  dossier CSV custom.

- `benchmark_folder`
  Dossier contenant les JSONL exportes une fois.

- `csv_folder`
  Dossier CSV custom si `source=csv-folder`.

- `target_columns`
  Colonnes a lire dans les CSV custom. Vide = detection automatique.

- `datasets`
  Liste separee par virgules, par exemple `dominick,m4_daily`. Vide = tous les
  datasets eligibles selon les limites.

- `context_len`
  Longueur contexte demandee.

- `adaptive_context`
  Si `true`, reduit le contexte pour les series courtes.

- `min_context_len`
  Contexte minimum accepte quand `adaptive_context=true`.

- `horizon`
  Nombre de points futurs predits.

- `slide_step`
  Pas de fenetre glissante. `null` = `horizon // 2`.

- `branch_modes`
  `single`, `bundle`, ou `single,bundle`.

- `branch_steps`
  Steps de forecast ou on force un token.

- `top_k`
  Nombre de rangs de tokens testes dans le scan principal.

- `bundle_size`
  Nombre de tokens forces consecutivement en mode bundle.

- `bundle_continuation_ranks`
  Scenarios de continuation bundle, par defaut `1,5,10`.

- `num_samples`
  Nombre de continuations samplees par branche forcee.

- `temperature`
  Temperature du sampling Chronos.

- `sample_top_k`
  Top-k utilise pendant le sampling de continuation. `0` desactive la troncature.

- `bad_base_threshold`
  Seuil de warning quand Chronos base est mauvais.

- `max_datasets`
  Nombre max de datasets scannes.

- `max_series_per_dataset`
  Nombre max de series par dataset.

- `max_windows_per_series`
  Nombre max de fenetres par serie.

- `max_total_windows`
  Stop global apres ce nombre de fenetres terminees.

- `rank_score_column`
  Colonne de ranking. Vide = `context_iqr_scaled_progressive_token_bin_forking_score`.
  Aucun fallback silencieux. Pour changer d'unite, choisir explicitement la
  meme colonne dans toutes les analyses comparees.

- `run_name`
  Prefixe lisible du dossier resultat.

- `output_root`
  Dossier parent des resultats.

- `resume_from`
  Dossier resultat au nouveau format a reprendre. Les parametres sauvegardes
  sont restaures ; les changements scientifiques incompatibles sont refuses.
  Les anciens runs CSV-only restent conserves mais ne sont pas migres en place.

- `checkpoint_every_branch_groups`
  Frequence d'ecriture du `checkpoint.json`. Chaque groupe est toujours publie
  atomiquement dans `branch_groups/` ; les CSV sont des exports reconstruisibles.

- `visualisation`
  Genere les figures a la fin du run.

- `visualisation_top_n`
  Nombre de top branches affichees dans certaines figures.

- `visualisation_score_column`
  Colonne de score utilisee dans les figures. Vide = `context_iqr`.
  Mettre explicitement la meme valeur
  que `rank_score_column` si on veut forcer une normalisation alternative.

- `no_progress`
  Masque les barres de progression.

## Parametres Auto-Refinement

- `auto_refinement`
  Lance automatiquement un second run cible apres le scan principal.

- `refinement_global_top_windows`
  Nombre de fenetres selectionnees globalement.

- `refinement_per_dataset_top_windows`
  Nombre de fenetres selectionnees par dataset.

- `refinement_branch_steps`
  Grille plus fine de steps pour le refinement.

- `refinement_top_k`
  Nombre de rangs de tokens testes dans le refinement.

- `refinement_num_samples`
  Nombre de samples par branche dans le refinement.

- `refinement_branch_modes`
  Modes du refinement. Garder `single` sauf mini-run cible.

- `refinement_run_name`
  Prefixe du dossier refinement.

- `refinement_output_root`
  Vide = sous-dossier `refinement/` dans le run principal.

- `refinement_resume_from`
  Dossier refinement a reprendre.

- `refinement_visualisation`
  Genere les figures du refinement.

