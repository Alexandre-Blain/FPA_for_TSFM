# Handoff — premier lot étendu terminé

**22 novembre 2026. STOP pour revue scientifique, aucune deuxième collecte.**
Lire le **[rapport principal](../reference/FPA_EXTENDED_BATCH_REPORT.md)** puis
ses CSV/PDF joints au handout. Il contient les résultats classés par niveau de
preuve, les limites, la liste des fichiers changés, l'état Git et les commandes
sélectives proposées au chercheur. [Autorisation terminée](../../codex-prompts/CURRENT_TASK.md).

## Provenance et achèvement

Branche `main`, HEAD pré-commit et de collecte
`ea3d78a10280e83e65a2bd7474af3eaf8ee1a905`; arbre initial propre.
Les22 chemins source/doc/test nouveaux ou modifiés restent non stagés et non
commités. Aucun staging/commit/push/pull/changement de branche par Codex;
le SHA du prochain commit chercheur est inconnu.

Checkpoint complet : `result/extended_batch_20261122T115422Z/`.
Stage A terminé, puis gel avant inférence à12:09:22.897 UTC; collecte complète
à12:57:43.087 UTC, analyse complète à13:07:46.223 UTC. Original Chronos-T5-mini,
révision `bd6a4fde8403b8469acd0abd52852b29dbe61c7b`, C512/H32, b0..9,
q50 inchangé. La révision N60 concerne ce lot seulement; le pilote historique
reste inchangé.

Huit nouvelles identités : M4 T000029/T000008/T000092/T000028;
ERCOT SOUTH_C/WEST; devises currency_8/currency_6. Exclusions élargies aux scans
historiques; une fenêtre/source. Les séries ERCOT/devises restent dépendantes.
24 blocs denses N20, sélection sur bloc0 exclusivement, holdout N40;
16 alternatives et8 contrôles aléatoires. Les16 alternatives reçoivent un N60
frais, avec références/nulls partagés explicitement si même position.

Total **1 661 ensembles, 34 980 trajectoires**,1 661 flux RNG et graines
distincts;32 tentatives modèle, zéro échec,64 chemins white-box capturés.
Coût modèle cumulé47 min17.954 s, pic Job1.311 Gio; Stage A144.460 s et
analyse434.896 s hors modèle. Cellules474.36 Mo, validations0.78 Mo,
analyse16.82 Mo, hors journaux et ZIP. Reprise complète exécutée avec lancement
modèle interdit : zéro lancement/tirage,3 844 fichiers expérimentaux inchangés.

## À transmettre et à conserver

`frozen.json` lie sélection/contextes, plans des cellules/RNG, environnement,
cache modèle et gate A. `source_manifest.json` et `source_at_collection/`
conservent exactement les sources exécutées non commitées. `batch_complete.json`
lie les marqueurs denses et frais; `first_two_gate.json` et `stage_a_gate.json`
documentent les contrôles avant progression.

Dans `analysis/`, lire d'abord `scientific_summary.json`,
`independent_validation.csv`, `precision_summary.csv`, `rank_stability.csv` et
`EXTENDED_BATCH_FIGURES.pdf`; le rapport indique les autres preuves thématiques.
Les tables distinguent unités brutes et IQR, supports, blocs et familles Holm.
Un rejet de baseline n'établit pas une importance pratique; un non-rejet ne
prouve pas l'équivalence. Le classement global N60/N60 n'a pas été mesuré.

**281 tests offline finaux passent/144.39 s**, six avertissements de retries
Windows réussis; tests analyse2/6.19 s, handout9/4.10 s. `final_checks.json`
contient liens, tests, Git, hashes des copies/assets/ZIP; `preservation_after.json`
vérifie les2 956 fichiers data/result antérieurs, index, `.gitignore` et cache.
Les anciens rapports et le protocole scientifique d'origine restent préservés.

Upload facile : `docs/chatgpt-handout.zip` ou
`docs/chatgpt-handout/CHATGPT_HANDOUT.md`, accompagnés des39 assets scientifiques
explicites. Les archives ne sont pas exportées automatiquement. Ces copies,
les sorties `result/`, données, caches et `.venv/` restent ignorés par Git.

## Prochain gate unique

**Recommandation non approuvée : revue ChatGPT–chercheur45–60 min, zéro tirage.**
Fixer les seuils pratiques W1/ED, les hypothèses confirmatoires, la précision
nécessaire et la diversité/taille restante. L'intérêt d'étendre la grille serait
réfuté si le gain attendu reste sous le bruit ou si les sources supplémentaires
ne fournissent pas les unités indépendantes requises. Le stock local restant
est48 M4, zéro ERCOT, une devise; ne pas substituer des fenêtres voisines à de
nouvelles séries. Toute collecte supplémentaire demande une nouvelle tâche
explicitement autorisée. Aucun superviseur ni nouvelle campagne à reprendre.
