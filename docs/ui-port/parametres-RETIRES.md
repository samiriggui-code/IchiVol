# Paramètres — éléments retirés (port maquette)

## Fichiers / modules supprimés

| Fichier | Raison |
|---------|--------|
| `pages/settings/*` (SettingsForm, panels, controller, dialogs, constants) | Layout nav latérale hors maquette `parametres()` |

## UI retirée vs ancienne page

- Navigation latérale multi-sections custom
- Dialogs confirm clé LLM / tests avancés
- Panels Environment / Risk / Market / Alerts / Connections séparés

## Champs « — »

| Emplacement | Champ | Note |
|-------------|-------|------|
| LLM modèle | | settings absents → — |
| Connexion moteur | | getSettings fail → Non connectée |
| Limites risque | | Persistées localStorage (maquette) ; pas d’écriture Risk Kernel |
