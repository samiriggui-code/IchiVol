# Ichimoku Volume Pulse (`IchiVol`)

Indicateur Pine Script v5 à **jumeler** avec l’Ichimoku Cloud de TradingView.  
Il lit le **volume automatiquement**, le colore selon le biais du nuage, et ne valide les signaux TK / breakouts cloud que si le **volume relatif (RVOL)** confirme.

## Installation (TradingView)

1. Ouvre [TradingView](https://www.tradingview.com/) → graphique de ton actif.
2. Ajoute d’abord **Ichimoku Cloud** (indicateur natif) pour le nuage / Tenkan / Kijun / Chikou.
3. `Pine Editor` (bas de l’écran) → colle le contenu de `IchimokuVolumePulse.pine` → **Add to chart**.
4. Tu obtiens un **panneau volume** sous le prix, synchronisé avec les mêmes paramètres Ichimoku (9 / 26 / 52 / 26).

Optionnel : dans les réglages `IchiVol`, active **Colorer les bougies du prix** pour peindre les bougies selon le biais + signaux confirmés.

## Lecture rapide

| Élément | Signification |
|--------|----------------|
| Colonnes **vertes/teal** | Prix au-dessus du cloud + volume ≥ moyenne |
| Colonnes **rouges** | Prix sous le cloud + volume ≥ moyenne |
| Colonnes **ambre** | Prix **dans** le cloud (zone neutre) |
| Colonnes **grises** | Volume sous la moyenne (conviction faible) |
| Triangle **VOL↑ / VOL↓** | Signal Ichimoku **confirmé** par RVOL ≥ seuil (défaut 1.5×) |
| Fond teinté | Barre où le RVOL dépasse le seuil (confirmation en cours) |
| Tableau coin haut-droit | Biais cloud, twist, RVOL, état volume, Tenkan/Kijun live |
| `⚠️ Pas de volume` | Actif sans série volume (certains indices / CFD) → signaux volume désactivés |

## Signaux alertables

- Croisement Tenkan/Kijun haussier **au-dessus** du cloud + volume confirmé  
- Croisement Tenkan/Kijun baissier **sous** le cloud + volume confirmé  
- Breakout / breakdown du cloud + volume confirmé  
- Spike volume (RVOL ≥ 2× par défaut)

Créer une alerte TradingView → condition = `Ichimoku Volume Pulse` → choisir l’événement.

## Paramètres utiles

- **Seuil confirmation RVOL** (`1.5`) : baisse à `1.2` sur marchés calmes, monte à `2.0` sur crypto volatile.  
- Aligne **Tenkan / Kijun / Senkou B / Displacement** sur ton Ichimoku overlay si tu utilises des réglages non standards.

## Fichier

- `IchimokuVolumePulse.pine` — source unique à coller dans le Pine Editor.
