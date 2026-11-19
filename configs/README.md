# Run Configs

Les runs Chronos doivent maintenant etre lances avec un fichier JSON quand c'est
possible.

## Dossiers

- `chronos_benchmark_scan/`
  Configs pour le scan principal. C'est le point d'entree normal.

- `chronos_targeted_refinement/`
  Configs pour lancer uniquement un refinement a partir d'un run existant.

## Commande Recommandee

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_benchmark_scan.py `
  --config configs\chronos_benchmark_scan\broad_with_refinement.json
```

## Override Rapide

Tu peux garder la config et changer juste un parametre :

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_benchmark_scan.py `
  --config configs\chronos_benchmark_scan\broad_with_refinement.json `
  --max-total-windows 20 `
  --run-name debug_refinement_20_windows
```

## Tracabilite

Chaque dossier resultat garde :

```text
input_config.json
config.json
checkpoint.json
```

- `input_config.json` : le fichier demande au lancement.
- `config.json` : les parametres resolus apres overrides CLI.
- `checkpoint.json` : l'etat de reprise.


