# Chronos Targeted Refinement Configs

Les cles optionnelles `trajectory_metrics` (false), `save_trajectories` (false)
et `sampling_seed` (0) sont disponibles. La sauvegarde implique W1/ED et un
controle independant ; utiliser `branch_modes: "single"`. Voir
[schema et formules](../../docs/reference/CHRONOS_PHASE1.md).

Ces configs lancent uniquement le refinement cible a partir d'un run deja
existant.

Commande :

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_targeted_refinement.py `
  --config configs\chronos_targeted_refinement\default.json
```

Avant de lancer, modifier `source_run` dans le JSON.

## Parametres

- `source_run`
  Dossier resultat du scan principal qui contient `chronos_scan_summary.csv`.

- `benchmark_folder`
  Dossier local des datasets exportes.

- `model_id`, `device`, `dtype`
  Parametres de chargement Chronos.

- `context_len`, `horizon`, `slide_step`, `adaptive_context`, `min_context_len`
  Doivent rester compatibles avec le scan source pour retrouver les memes
  fenetres.

- `branch_modes`
  Modes testes dans le refinement. Recommande : `single`.

- `refine_branch_steps`
  Steps plus fins a tester. Recommande : `0,2,4,6,8,10,12,16`.

- `refine_top_k`
  Nombre de rangs token testes. Recommande : `15`.

- `num_samples`
  Nombre de continuations par branche. Recommande : `40`.

- `global_top_windows`
  Nombre de fenetres top global selectionnees depuis le run source.

- `per_dataset_top_windows`
  Nombre de fenetres top par dataset.

- `rank_score_column`
  Vide = score normalise `context_iqr`. Si le run source n'a pas cette colonne,
  choisir explicitement une colonne presente et comparable. Aucun fallback.

- `output_root`, `run_name`, `resume_from`
  Controle du dossier resultat et de la reprise.

- `visualisation`, `visualisation_top_n`, `visualisation_score_column`
  Generation des figures du refinement. `visualisation_score_column` vide =
  score `context_iqr`. Renseigner une colonne pour forcer une
  normalisation alternative dans les graphes.

- `checkpoint_every_branch_groups`
  Frequence d'ecriture du checkpoint JSON. Chaque groupe est toujours publie
  atomiquement ; les CSV sont des exports. La selection des fenetres est figee.

- `no_progress`
  Masque les barres de progression.

