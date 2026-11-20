# Contexte recherche

## Point de depart

La FPA consiste a forcer un choix local alternatif dans un processus de
generation, puis a observer comment la suite se deforme.

Pour Chronos v1, cette idee est naturelle car le modele transforme une serie
temporelle en tokens de valeurs, puis genere le futur token par token.

Question de base :

```text
Si Chronos choisit un autre token a un step de forecast donne,
a quel point la distribution future change-t-elle ?
```

## Ce que l'on ne cherche pas a faire

Le but immediat n'est pas de prouver que Chronos predit mieux qu'une baseline.

La pipeline sert plutot de sonde de sensibilite :

1. ou la prevision est-elle stable ?
2. ou une decision locale change-t-elle fortement le futur ?
3. ces changements correspondent-ils a une incertitude utile ou a une fragilite ?

## Pourquoi Chronos

Chronos v1 est interessant parce que :

1. il est univarie dans l'usage courant des benchmarks,
2. il fonctionne avec une tokenisation explicite des valeurs,
3. il produit une sequence autoregressive de tokens futurs,
4. on peut forcer un token precis pendant le decodage.

Cela donne un pont conceptuel :

```text
FPA sur langage naturel
  -> forcer un token textuel

FPA sur series temporelles avec Chronos
  -> forcer un token de valeur
```

## Hypothese de recherche

Formulation prudente :

> Une adaptation token-level de la FPA a Chronos permet d'identifier des zones
> de sensibilite locale dans les previsions.

Formulation plus ambitieuse, encore a tester :

> Le branching token-level peut servir d'indicateur d'incertitude structurelle
> dans les modeles de prevision tokenises.

## Question centrale actuelle

Les gros shifts observes sont-ils :

1. des bifurcations naturelles dans des zones ou Chronos hesite deja,
2. des stress tests provoques par des tokens improbables,
3. des artefacts d'echelle,
4. du bruit de sampling,
5. ou des consequences d'une mauvaise prevision de base ?
