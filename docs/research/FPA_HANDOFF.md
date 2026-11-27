# Handoff — campagne H1/H2 terminée, revue chercheur, 27 novembre 2026

**Gate E terminé. STOP : aucune nouvelle inférence ou campagne.**
Lire le [rapport scientifique](../reference/FPA_INCREMENTAL_VALUE_AND_EVENT_SAMPLING.md),
puis les figures et CSV dans `result/incremental_campaign_20261126T132759Z/analysis_v2/`.
Le dossier `docs/chatgpt-handout.zip` rassemble les pièces courantes de revue.

## Conclusion

**Narration C : résultats limités.** H1 n'établit pas d'information prédictive
FPA robuste au-delà de SGA et des contrôles conventionnels. Le delta NEAURC
MASE M3−M1 est−0,0510 [−0,4285;0,2058] sur52 tests internes, mais+0,0542
[−0,0339;0,1462] sur64 Weather OOD. Les deux p ajustés Holm valent1.
M3 coûte en moyenne50,08 s composées contre9,72 s pour M1.
Les contrôles secondaires favorables ne remplacent pas le primaire.

H2 n'établit pas d'avantage à coût égal. Neyman480 a RMSE0,01638 en25,29 s;
le MC prévu apparié a0,00974 en47,78 s : coût1,879 fois plus grand,
aucune paire dans la tolérance. Ce défaut interdit la conclusion primaire
à coût égal. Le MC N480 fixé, secondaire, atteint0,01191 en27,71 s.
Les poids/estimateurs corrects ne suffisent pas à démontrer une utilité pratique.

## Exécution et preuves

Run : `result/incremental_campaign_20261126T132759Z/` (RUN).
Autorisation originale `AUTHORIZED_REQUEST.txt`; protocole/configuration figés
dans `methodology.json`, `allocation.json`, `frozen_config.json`, `frozen.json`.
Cohorte et splits : `cohort_and_splits.csv`, une fenêtre par ID original.

- Pilote5 fenêtres/7 620 chemins; H1 complet320, avec153 train/51 validation/
  52 test interne/64 Weather OOD;160 contrôles avec736 chemins supplémentaires.
- H2 complet29/36, références N2000;11 fenêtres à dix répétitions.
  Répartition9 London/9 Electricity/9 Weather/2 Traffic : l'ordre groupé a
  manqué le retrait équilibré prévu. Les7 autres sorties restent conservées.
- Arrêt27 novembre07 h28 Luxembourg. Temps57 624,883 s, dépassement24,883 s
  du plafond16 h : **conformité au temps en échec**, aucune inférence relancée.
  Environ486 Mo nouveaux à la coupure, sous20 Gio.
- Audit brut :30 225 flux distincts,833 164 trajectoires,2 026 cellules H2
  recalculées. Conservation validée pour11 611 fichiers, index Git et `.gitignore`.
- **320 tests réussis en217,35 s**, `gate_E_final_tests.*`.
  Six pages PDF/PNG inspectées. Liens du handout vérifiés par le générateur.

La première analyse a échoué après ses29 tableaux sur un arrondi Wilson
négatif dans une figure. Source/gel/log préservés sous
`analysis_v1_failed_plot_provenance/`; le finaliseur offline version2 corrige
le tracé seul. Les29 fichiers numériques sont identiques par SHA256.
`analysis_complete.json` et `analysis_v2_freeze.json` lient la version finale.
Ne pas relancer l'ancien `main` contre un source différent de son gel.
Les anciennes erreurs dans les logs sont de la provenance, pas l'état actuel.

## Limites et reprise

Un seul dataset OOD; dépendances physiques Weather inconnues; forte exposition
potentielle des cibles in-domain au pré-entraînement TSFM. Les IC maintiennent
les modèles ajustés fixes; quatre blocs dataset donnent des tests grossiers.
H2 est partiel; répétitions conditionnelles à un même pilote; référence N2000
finie. F6 peut inclure le saut forcé à b9, contrairement à W1/ED.
Les contrôles secondaires ont été fixés avant les cibles, sans changer le primaire.

**Unique suite proposée, non exécutée :** diagnostic offline des préfixes des
pools MC existants, choisis par leurs temps seuls. Plafond proposé2 h de travail/
30 min CPU offline/0 s modèle. Exiger≥80% d'appariements dans[0,8;1,25] et un
gain RMSE≥10% avec IC de delta MSE négatif; sinon pas de gain démontré.
Les données ont déjà été vues : analyse exploratoire. **Revue et approbation
du chercheur requises avant cette nouvelle tâche**, selon le gate de l'autorisation.

Branche `main`, HEAD avant commit chercheur
`a5b6ef6743832f09bfa096078104b727dc84f373`; modifications locales non commitées.
`RUN/GIT_HANDOFF.md` contient le statut complet, les chemins et propositions
de staging sélectif. Données/résultats/checkpoints/handout restent hors Git.
Aucun staging, commit ou push Codex; prochain SHA inconnu jusqu'au commit chercheur.
