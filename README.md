# FPA_for_TSFM

Forking Paths Analysis des décisions de tokens générés par Chronos :
mesurer leurs conséquences sur les distributions de trajectoires futures.

Commencer par **[docs/README.md](docs/README.md)** : objectif, protocole,
résultats réellement obtenus, reprise du travail et archives.

Installation et tests hors ligne :

```powershell
uv sync --group dev
.\.venv\Scripts\python.exe -m pytest
```

Le [guide pratique](docs/reference/README_CHRONOS.md) décrit les commandes.
Le code est dans `code/chronos_fpa/`; données et résultats restent hors Git.
Seul le chercheur effectue les opérations Git d'écriture.
