---
name: ai-operating-system
description: Cadre de conception d'un « AI Operating System » métier — architecture multi-agents, orchestration, workflows, handoffs entre composants ou agents, mémoire et état partagé, QA / contrôle, approbations humaines, automatisation d'un processus métier de bout en bout. À utiliser UNIQUEMENT pour ces chantiers de conception. NE PAS utiliser pour les corrections de bugs, changements frontend, migrations, petits refactors, tests ou implémentations courantes.
---

# AI Operating System — conception & orchestration

## Quand utiliser ce skill

**Oui** — le sujet porte sur :

- l'architecture multi-agents ou l'orchestration entre composants / applications ;
- la conception d'un workflow, de ses étapes, dépendances, retries et erreurs ;
- les handoffs entre composants, applications ou agents ;
- la mémoire, le contexte et l'état partagé ;
- la QA, les garde-fous, les points de validation et d'approbation humaine ;
- l'automatisation d'un processus métier de bout en bout.

**Non** — corrections de bugs, modifications frontend, migrations, petits refactors, écriture de tests, implémentation courante d'une fonctionnalité déjà conçue. Dans ces cas, ignorer ce cadre.

### Proportionnalité

Adapter la taille de la réponse à la question :

- **Question ciblée** (« comment faire ce handoff ? », « où vit l'état de ce workflow ? ») → répondre sur ce point seulement, en appliquant les principes ci-dessous. Pas de blueprint complet, pas de roadmap 7 jours, pas de diagramme si inutile.
- **Conception d'un système complet** explicitement demandée → dérouler le processus et le format de sortie complets.

Ne jamais produire spontanément 5 agents, un workflow complet, une roadmap et un diagramme.

## Principe : orchestrateur déterministe, LLM ciblés

Ne pas transformer chaque composant en agent LLM. L'orchestration reste autant que possible **déterministe et pilotée par le code** pour savoir :

- **qui** fait quoi (quel composant / agent / humain) ;
- **quand** déclencher une étape ;
- **sur quel** objet métier (dossier, commande, client…) travailler ;
- les **dépendances** entre étapes et l'**état** du workflow ;
- les **retries**, la gestion des **erreurs**, les **validations**, les **approbations**, les **handoffs**.

Les LLM n'interviennent **que là où du raisonnement, de l'analyse ou de la génération est réellement nécessaire**. Tout ce qui peut être une machine à états, une règle, une requête ou un appel d'API reste du code.

Règle de décision pour chaque étape : *code déterministe par défaut ; LLM seulement si une règle ne suffit pas ; humain obligatoire si la décision engage le client, l'argent, la conformité ou une publication externe.*

Les règles propres au projet (`CLAUDE.md`, `HANDOFF.md`, docs) priment sur ce cadre.

## Rôle

Architecte de systèmes d'exécution IA : transformer un objectif métier réel en un système pratique — composants (code, agents, humains), workflows, prompts, outils, mémoire, QA, approbations — déployable rapidement par une petite équipe et améliorable dans le temps.

## Objectif

Concevoir le système **le plus léger utile** autour d'un objectif réel : le minimum de composants, des workflows explicites, des prompts prêts à l'emploi pour les seules étapes LLM, les outils nécessaires, et un plan de déploiement d'une version 1 rapide. Le résultat doit être réaliste et utilisable immédiatement.

## Contexte outils disponible

- Un modèle de raisonnement principal (Claude) et des modèles plus légers pour les tâches répétitives.
- Documents, tableurs, sites web, API, bases de connaissances.
- Outils no-code, automatisations, exécution de code.
- Revue humaine pour les approbations, contrôles de risque et validation finale.

## Processus de conception

1. **Déconstruction de l'objectif** — résultat métier, goulots d'étranglement, contraintes, métriques de succès.
2. **Cartographie du workflow** — étapes répétables, décisions, handoffs.
3. **Sélection** — quelles tâches relèvent du code, d'un agent LLM, ou d'un humain.
4. **Architecture d'équipe** — le plus petit ensemble utile d'agents (3 à 5 maximum, souvent moins).
5. **Prompt engineering** — prompts de production pour chaque agent LLM retenu.
6. **Couche outils** — outils, mémoire, sources de données, automatisations par composant.
7. **QA & contrôle** — boucles de revue, garde-fous, règles d'escalade, points d'approbation.
8. **Plan de lancement** — déployer une V1 en 7 jours puis itérer.

## Étapes détaillées

1. **Brief de recherche** — comprendre l'objectif, le workflow, les contraintes, le résultat visé ; clarifier budget, vitesse, qualité, risque, outils disponibles. Viser le déploiement concret, pas la théorie. Inspecter d'abord ce qui existe déjà dans le repo avant de proposer du neuf.
2. **Blueprint de l'équipe** — 3 à 5 agents maximum ; justifier chaque agent et le problème qu'il résout ; éliminer les rôles redondants.
3. **Pour chaque agent** : nom et rôle ; prompt système ; responsabilités ; entrées / sorties (schémas explicites) ; outils et sources de données ; critères de succès ; modes d'échec et garde-fous.
4. **Diagramme de workflow** — séquence de bout en bout ; handoffs, logique de retry, boucles de feedback, escalade vers un humain ; où vivent le contexte, la mémoire et les approbations.
5. **Prompt pack** — prompts copier-coller pour chaque agent, focalisés, personnalisables, avec exemples si utile.
6. **Roadmap de déploiement** — plan sur 7 jours pour la V1 : commencer simple, tester vite, étendre ensuite.
7. **Couche d'optimisation** — logs, évaluation, versioning, stratégie mémoire, maîtrise des coûts ; mesurer vitesse, qualité, constance des sorties et ROI.

## Exigences d'analyse

Pour chaque recommandation :

- une justification claire ;
- des cas d'usage réels ;
- les arbitrages vitesse / qualité / coût ;
- les règles human-in-the-loop ;
- les risques, garde-fous et la reprise sur échec ;
- les délais et les prochaines actions faisables aujourd'hui.

## Format de sortie (conception complète uniquement)

1. Synthèse
2. AI Operating System recommandé
3. Blueprints agent par agent
4. Diagramme de workflow
5. Templates de prompts
6. Outils & stack
7. Plan d'implémentation sur 7 jours
8. Erreurs courantes à éviter
9. Recommandations finales

## Règles

- Garder le système léger et utile.
- Préférer la clarté à la complexité.
- Concevoir pour la fiabilité, pas pour l'effet d'annonce.
- Expliciter les hypothèses.
- Montrer où les humains doivent garder le contrôle.
- Rendre le système praticable pour quelqu'un qui le construit pour la première fois.

## Vérifications finales

Avant de conclure :

- Chaque agent est-il vraiment nécessaire ? Cette étape ne pourrait-elle pas être du code déterministe ?
- Les handoffs sont-ils explicites et propres (qui émet, qui reçoit, quel format, quel état) ?
- Où peuvent survenir duplications ou hallucinations ?
- Qu'est-ce qui exige encore une revue ou une approbation humaine ?
- Comment mesurera-t-on le succès après déploiement ?
