# Objectif scientifique

**Question de Paper 1 :** qu'apprend-on sur les distributions de trajectoires
numériques futures en imposant un token de sortie plausible à un TSFM
autorégressif, au-delà de sa probabilité locale, de l'entropie et du saut
numérique immédiat ?

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
axes exploratoires; aucun nouveau score composite n'est recherché.
