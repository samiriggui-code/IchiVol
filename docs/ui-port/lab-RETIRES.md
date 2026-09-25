# Strategy Lab — éléments retirés (port maquette)

## Fichiers / modules supprimés

| Fichier | Raison |
|---------|--------|
| `pages/lab/HistorySheet.tsx` | Historique sheet hors maquette `lab()` |
| `pages/lab/LabKpis.tsx` | KPIs custom hors metrics maquette |
| `pages/lab/LabMainContent.tsx` | Contenu research T5–T7 hors DOM maquette |
| `pages/lab/labShared.tsx` | Tabs / helpers ancienne UI |
| `pages/lab/useLabController.ts` | Contrôleur research hors maquette |

## UI retirée vs ancienne page

- Sélecteur classe d’actif / onglets Research
- Historique sheet / ablations recalcul
- Contenu T5–T7 / Researcher
- Courbes de perf inventées (SVG structurel « — » uniquement)

## Champs « — »

| Emplacement | Champ | Note |
|-------------|-------|------|
| Metrics Univers / Fenêtre | valeurs | coverage / runs absents → — |
| Tableau PÉRIMÈTRE | | coverage absent → — |
| Tableau STATUT | | pas de runs → À ÉVALUER / — |
| Trajectoires | courbe | pas de série equity lab exposée → « — » |
| Configurer / Examiner | | non branchés moteur (disabled / no-op) |
