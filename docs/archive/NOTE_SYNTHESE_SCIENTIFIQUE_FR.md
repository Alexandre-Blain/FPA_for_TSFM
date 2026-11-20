# Synthèse scientifique de référence - FPA / Chronos Paper 1

**Annotation d'intégration - 2026-11-19 :** les résultats antérieurs ci-dessous
sont **observed (rapports sources)**, les mécanismes proposés sont
**hypothesis**, les protocoles et tests sont **suggested**. Les vérifications
locales portent sur les fichiers, manifestes et sources, sans nouvelle
inférence ni recalcul statistique. Voir le [statut](../research/FPA_STATUS.md), le
[rapport complet](FPA_INTEGRATION_REPORT.md) et l'[audit](FPA_IMPLEMENTATION_AUDIT.md).

**19 novembre 2026 | Version de cadrage, non résultat de campagne.** Ce document vise à transmettre nos arbitrages sans dépendre de l’historique d'un chat. Les protocoles et rapports originaux font foi pour les details.

## Une question, trois contributions possibles

**Question centrale :** que révèle l’intervention sur des décisions locales de tokens de sortie de Chronos concernant les lois de trajectoires futures, que les probabilités locales, l’entropie et la magnitude du saut immédiat ne caractérisent pas suffisamment ?

1. Mesure : FPA probabiliste numerique avec préfixe greedy partage, continuations stochastiques, W1 marginal et Energy Distance sur suites strictement post-fork, control same-token et documentation de la politique effective.
2. Description : existence, intensité, prévalence conditionnelle à la sélection, hétérogénéité entre jeux de données et séries originales, effets de position, de contexte, de J, d’entropie et de probabilité.
3. Interprétation : trajectoires conditionnelles interprétées comme ensembles, persistance/transience, tendance, niveau, largeur d’incertitude, direction et événements, avec résultats négatifs.

Il n’est pas établi que ces trois contributions seront toutes défendables. L’asymétrie M4 et la localisation ERCOT sont des signaux exploratoires choisis après observation, pas le sujet exclusif de l’article.

## Ce que FPA n'est pas

Une attribution sur l’historique d'une serie UCR ou la decision d'un classifieur ne mesure pas le meme objet que le forking d'un token genere. L'idee UCR reste une possibilite de future validation **a condition d'etablir un comparateur sur une cible commune**, pas le benchmark necessaire de Paper 1. FPA reste une analyse post hoc d'un processus génératif, mais avec une intervention sur ses propres choix autorégressifs.

Un benchmark de screening peut comparer les politiques permettant d'identifier rapidement les forks importants (aléatoire, entropie, probabilite, saut J, latents, pooling). Ce benchmark mesure la valeur prédictive et le coût par rapport a une reference FPA, mais **ne prouve pas à lui seul l’utilité externe de FPA**, car la définition de la cible est issue de FPA.

## Campagne exploratoire puis campagne finale

La prochaine campagne est exploratoire, extensible et stoppable, avec checkpoints, analyse des groupes terminés et conservation exhaustive des données utiles. Elle sert a découvrir les principales contributions et à préparer un protocole final de confirmation sur de nouvelles séries et de nouveaux contextes. **Elle n’a pas commencé.**

Paramètres candidats : Chronos-T5-mini revision fixee, contexte 512, horizon 32, positions FPA 0 à 9 **toutes testees pour chaque fenêtre**, N=20 par ensemble, au plus 8 tokens (greedy inclus) ou couverture de 90% de q50 si atteinte plus tôt, complément résiduel conditionnel, contrôle greedy indépendant. Mesures strictes sur les 22 premiers horizons post-fork, plus profils complets lorsque disponibles. Panel de fenêtres représentatives + panel de diversité. Déplacement préféré de 256 observations pour des fenêtres d’une même série ; ce n'est pas une preuve d’indépendance.

CPD Bigelow : une courbe par fenêtre, sur **seize lois d'issue P0..P15**. Reconstruction des P0..P9 par mélanges de branches FPA pondérés par q50, P10 depuis la branche greedy de la position 9, P11..P15 depuis 60 continuations directes chacune. Deux issues interpretables fixes sur la meme fenetre : ecart a la dernière valeur greedy et ecart moyen sur les huit dernières valeurs, normalisés par l’IQR historique avec plusieurs seuils. Le CPD sur profils W1 le long des horizons futurs est une autre analyse. Le changement d'estimateur entre la partie dense et la partie directe doit être contrôlé.

Le large panel n’implique pas une inférence statistique indépendante sur les fenetres. Prévalence représentative et recherche de cas diversifiés sont deux objets différents. Priorité aux séries originales différentes et aux régimes variés ; conserver la procédure de sélection.

## White-box et efficacite

Collecter, au maximum faisable après benchmark, les IDs de tokens, logits q50/p_sel, trajectoires numeriques, encodeur et decodeur : toutes les couches, états internes, self-attentions et cross-attentions avant et apres les forks. Les tokens enregistrés doivent permettre un replay déterministe de la trajectoire pour compléter la capture plus tard. Les cartes d’attention ne sont pas des explications causales par elles-mêmes.

Calculer l’encodeur une seule fois par contexte si cela n’est pas déjà fait. Reutiliser cache du decodeur pour préfixes greedy et branches, sans supprimer la dépendance aux tokens passés. Batching/cache/attention doivent etre testes pour la parité des logits et la vitesse réelle ; une collecte exhaustive peut changer kernels, temps, RAM et disque. Elle sera allegee seulement apres des mesures et une decision explicite.

La référence FPA dense des positions 0..9 sert a simuler offline des strategies sparse et quantifier les forks ratés. Les labels a N20 restent bruités et ne constituent pas des vérités absolues ; sélection et évaluation ne doivent pas partager clandestinement les informations des positions masquees.

## Résultats acquis et limites

Phase 2 : 7 groupes/1 400 trajectoires sur 3 series, H64 N50. Phase 3 : statistiques offline sans nouvelle inférence. M4 b0 : effets différents pour deux tokens opposés de |J| comparable, dans un cas selectionne; ERCOT b0 : contraste debut/fin sur deux seeds, pour un cas choisi post hoc; Exchange Rate : separations parfois fortes mais classements instables. Les relations de la sensibilite a l’entropie sont encore confondues par les effets de dataset et de série. Les descriptions morphologiques restent principalement exploratoires. Stage A M4 H64/N50 avec nouvelle seed est envisage comme cellule separee, **non exécutée**.

Anciennes données : les trajectoires brutes du pilote récent peuvent être tronquées/réanalysées avec les nouvelles distances ; les scores composites de scans anciens ne sont pas convertibles automatiquement en W1/ED à partir de simples agrégats. L'horizon H32 ne suffit pas a montrer la persistance à 64 pas.

## Tests scientifiques prioritaires

1. Quel niveau de séparation survit au contrôle same-token et aux échantillons indépendants ?
2. J signe/absolu, probabilite, entropie, contexte et modele autoregressif simple expliquent-ils la séparation en aval ?
3. Quels effets de propagation et quels descripteurs temporels sont robustes ?
4. Les lois d'issue changent-elles de maniere informative pendant la fixation progressive du préfixe greedy, au-dela du bruit d'estimation et des effets terminaux mecaniques ?
5. Les méthodes sparse recuperent-elles les forks consequents a budget de calcul egal, sans information cachee ?
6. Les latents/attentions apportent-ils une information prédictive incrementalement utile sur de nouvelles series ?

## Décision de workflow

Git et manifestes bruts = source de vérité. Codex fait l'implémentation, tests, runs **après accord**, checkpoints et rapports. ChatGPT fait audit scientifique critique, synthese, objections, proposition de prochain prompt borne. L’utilisateur arbitre. Les fichiers du Projet ChatGPT sont des instantanés, pas une synchronisation automatique des modifications dans VS Code. À chaque itération, mettre a jour statut, journal de décisions et handoff, puis faire relire les résultats avant un nouveau run.
