# Définitions expérimentales — Chronos H32

**Variante autorisée le26 novembre 2026 :** la campagne H1/H2 emploie les
estimands de distance ci-dessous, avec le dessin et les événements spécifiques
du [rapport courant](../reference/FPA_INCREMENTAL_VALUE_AND_EVENT_SAMPLING.md)
et de `configs/chronos_incremental/campaign_v1.json`. H1 : sparse0/4/9,
cap5, deux N20 par loi, nullN20 et naturel3N20. H2 : stratification exhaustive
et première déviation b0..4, références indépendantes et allocations figées.
Ces variantes sont explicitement autorisées par le chercheur. Les sections
de collecte dense et CPD ci-dessous définissent les pilotes historiques et
n'imposent aucune collecte dense/CPD supplémentaire à cette campagne.

Ce document est la source des définitions scientifiques. L'autorisation
d'exécution est distincte : [tâche courante](../../codex-prompts/CURRENT_TASK.md)
et [décisions](FPA_DECISIONS.md). L'[état d'exécution](FPA_STATUS.md) est distinct
des définitions; le protocole seul ne déclenche aucune inférence.

## Modèle et unités

Chronos-T5-mini `amazon/chronos-t5-mini`, révision
`bd6a4fde8403b8469acd0abd52852b29dbe61c7b`.
Contexte **512**, horizon **32**, positions d'intervention **b0..9**.
Hiérarchie : dataset → série originale → fenêtre → position → ensemble → trajet.
Les fenêtres d'une même série et les tokens d'une même fenêtre ne sont pas des
réplications indépendantes entre séries.

## Échantillonnage

- **N20** continuations par token imposé; référence greedy et contrôle greedy
  indépendant utilisent des flux aléatoires distincts.
- **q50** : masque des tokens numériques valides, température 1, top-k 50,
  top-p 1. Les égalités au seuil top-k sont conservées : le support peut
  dépasser 50 IDs. **p_sel** est la softmax valide non tronquée, stockée séparément.
- Sélection greedy d'abord, puis q50 décroissant et ID croissant en cas
  d'égalité; arrêt à **90 %** de masse ou **8 tokens incluant greedy**.
- Le résidu contient toute la masse q50 positive non sélectionnée. Si elle
  est positive, un ensemble N20 tire son premier token conditionnellement au
  résidu, puis reprend q50 ordinaire. Poids sélectionnés + résidu = 1.
- Le décodeur conditionne toujours sur tous les tokens précédents. Caches,
  batching et replay doivent conserver la loi et le support de sampling.
- Conserver les chemins numériques **et** tous les IDs de tokens, paramètres,
  préfixes, probabilités, graines, échelles et hashes.

## Distances et saut direct

Pour un préfixe greedy fixe et un token imposé à b, comparer les lois des
coordonnées **b+1..31**, en excluant le token imposé. Rapporter séparément
le saut signé J et |J|. Exporter deux supports : suffixe restant complet
(longueur 31..22) et **premières 22 coordonnées strictement post-fork**.

W1 : distance empirique marginale exacte à chaque horizon, puis moyenne sur
le support déclaré. ED : V-statistique
`2 E rho(A,B) - E rho(A,A') - E rho(B,B')`, avec
`rho(u,v)=||u-v||_2/sqrt(L)`, diagonales incluses, sans racine finale.
Les [définitions détaillées](../reference/CHRONOS_METRICS.md) et
[l'audit mathématique](../reference/CHRONOS_MATH_AUDIT.md) complètent ces conventions.

Rapporter valeurs brutes et divisées par l'IQR du **contexte**. Une échelle
invalide entraîne exclusion/diagnostic, sans normalisation de remplacement.
Le contrôle indépendant same-token fournit un niveau de bruit, pas un seuil
universel ni un test à lui seul. Aucun score composite nouveau.

## Lois d'issues fixes P0..P15

Même issue sur toute la fenêtre : écart absolu à la trajectoire greedy figée,
soit au terminal Y31, soit moyen sur les huit coordonnées 24..31; division
par l'IQR du contexte. Seuils : **0.05, 0.10, 0.25, 0.50, 1.00**.
Conserver aussi les valeurs continues.

- P0..P9 : mélange des ensembles conditionnels, pondéré par q50, résidu inclus.
- P10 : réutilisation de la référence greedy imposée à b9.
- P11..P15 : **N60** continuations directes indépendantes depuis chaque préfixe.
- Calibration : tirages directs N60 supplémentaires à P0, P9 et P10.

L'identité théorique `P(t,greedy)=P(t+1)` ne signifie pas égalité bit à bit de
deux échantillons indépendants. La réutilisation induit de la covariance.
Les erreurs Monte Carlo conditionnelles ne sont pas des intervalles de
confiance entre séries; les estimateurs changent de variance à P10/P11.
Ne pas conclure à une rupture structurelle sur cette seule frontière.
Aucun ajustement BEAST/PELT n'est lancé par ce protocole.

## Sélection, conservation et interprétation

Définir et figer population éligible, origine, règles, strates représentative
et diversité, graines et exclusions **avant** les nouveaux résultats FPA.
La sélection et l'échelle n'utilisent que le contexte, jamais le futur ni
un score FPA favorable. Conserver les clusters de séries et l'exposition
antérieure; un contexte déjà étudié n'est pas une nouvelle réplication.

Privilégier la capture exhaustive faisable; distinguer clairement ce qui est
capturé immédiatement et reconstructible par replay. Aucun trajet/token
essentiel n'est supprimé. Les objets incomplets restent invisibles aux analyses.
Les [contrats techniques](../reference/FPA_TECHNICAL_GATES.md) décrivent les tests.

Comparer les effets à J, q50, p_sel, entropie, bruit same-token, propagation
numérique et géométrie des bins. Inspecter les deux ensembles pour la morphologie.
Les résultats du petit pilote seront descriptifs, sans prévalence de population.
La réplication historique Stage A **H64/N50 seed2718** reste séparée et non exécutée.
