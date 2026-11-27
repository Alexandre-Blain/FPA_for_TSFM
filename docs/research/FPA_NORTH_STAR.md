# Objectif scientifique

**Question de Paper 1, cadrage exploratoire du24 novembre2026 :** l'exploration
par interventions d'un TSFM autorégressif révèle-t-elle des informations utiles
sur les trajectoires, les décisions conséquentes ou l'incertitude prédictive
que les méthodes conventionnelles retrouvent moins efficacement à coût comparable ?

Le complément du superviseur, reçu le 26 novembre 2026, donne priorité à une
**valeur ajoutée mesurable sur une tâche commune, à coût comparable**.
Fiabilité, découverte de scénarios, précision des prévisions et qualité des
décisions sont quatre affirmations distinctes. Aucune amélioration n'est acquise.
UCR et Kronos sont des applications candidates à étudier, sans autorisation
d'implémentation dans l'itération terminée.

La question mécanistique reste : qu'apprend-on en imposant un token de sortie
plausible, au-delà de sa probabilité locale, de l'entropie et du saut numérique
immédiat ? Les benchmarks doivent permettre une réponse négative : FPA peut
être inutile ou trop coûteuse pour certaines tâches.

Le modèle actuel est Chronos-T5-mini. L'intervention porte sur un **token
généré**, conditionnellement à un préfixe greedy fixe. Les continuations sont
échantillonnées. Ce n'est ni une mesure directe de précision prédictive,
ni une intervention causale sur le système réel.

Trois contributions sont candidates, sans résultat positif présupposé :

- **C1 : mesure** correcte des lois conditionnelles, distances W1/ED et bruit
  Monte Carlo.
- **C2 : caractérisation** de l'hétérogénéité entre séries, positions et tokens,
  face aux explications par probabilité, entropie et déplacement immédiat.
- **C3 : interprétation temporelle** des différences entre ensembles complets,
  avec contre-exemples et limites.

Le [protocole](FPA_PROTOCOL_EXPLORATORY.md) fixe les estimands.
La [matrice des hypothèses](../reference/FPA_HYPOTHESES.md) porte les falsificateurs
et explications concurrentes. Le [statut](FPA_STATUS.md) distingue les résultats
observés des propositions.

L'unité indépendante principale est la série originale. Les résultats négatifs
et effets proches du contrôle doivent être conservés. Attention et hidden
states ne suffisent pas à établir une explication causale. UCR n'est pas une
validation obligatoire de Paper 1. CPD, white-box et efficacité restent des
axes exploratoires. La campagne explicitement autorisée le26 novembre teste
deux voies : valeur prédictive incrémentale H1 via une calibration supervisée
équitable, et variance/coût d'estimation des conséquences H2. Le modèle de
risque simple est autorisé; aucun score arbitraire choisi sur le test n'est admis.
