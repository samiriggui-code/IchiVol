# IchiVol — Trading workspace

Interface complète : 11 pages, Desk enrichi, thème IchiVol et interactions.

## Ouvrir
Décompresser le ZIP puis ouvrir index.html dans un navigateur.
Alternative : python -m http.server 8000, puis http://localhost:8000.
Les polices Google Fonts nécessitent Internet ; des polices de secours sont prévues.

## Fichiers
- index.html : structure commune.
- style.css : thème et responsive.
- app.js : les 11 vues et leurs interactions, navigation par fragment URL.
- world-map.svg : carte géographique des sessions.

## Pages
Desk, Marché, Opportunités, Portefeuille, Strategy Lab, Journal, Contexte,
Copilot, Agents, Opérations, Paramètres.

## Intégration dans le dépôt IchiVol
Placer ce dossier dans design-reference/ichivol-workspace/ pour servir de référence.
Demander à Cursor ou Claude Code de porter les composants vers le front existant,
en conservant les fonctionnalités, les routes et le moteur Python.
Brancher les valeurs et états sur les API réelles, après inspection du dépôt.
Les chiffres, graphiques, sessions et réponses du Copilot sont des démonstrations.
Aucun moteur Python ni connexion broker ne sont inclus.
Les notes, favoris et brouillons sont enregistrés localement dans le navigateur.

Carte : géométrie issue de https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson
