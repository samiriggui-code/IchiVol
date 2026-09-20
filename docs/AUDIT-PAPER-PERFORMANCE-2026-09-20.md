# Audit de la performance paper — 2026-09-20 (lecture seule)

Source : base `ichivol_engine` du VPS (SELECT uniquement), dernier snapshot 2026-09-20 16:40 UTC. Aucun code ni paramètre modifié. La base locale de dev ne contient aucune position dimensionnée (equity figée à 5 000 €) : elle n'est pas la source des chiffres.

## 1. Les « +53 € » ne sont pas reproductibles

- Baseline `ICHIVOL_BASELINE_V1` au dernier snapshot : equity 5 200,31 € (+200,31 €), dont **réalisé +8,31 €** et **latent +193,86 €**. Recalcul aux cours Binance actuels : ≈ 5 173 €.
- Fourchette horaire de l'equity depuis le 18/09 : 4 953,80 € – 5 200,31 €. Le passage de 4 998 € (15h UTC) à 5 200 € (16h UTC) vient de deux positions NEAR ouvertes à 16:14 et 16:20 UTC (pump de +7,7 %).
- La somme du réalisé des 12 portefeuilles est −8,75 €. Aucun agrégat trouvé ne donne +53 €. **Il faut me dire où ce chiffre est affiché** (digest, page Paper, portefeuille précis).
- Conclusion : le seul résultat solide est **+8,31 € net réalisé sur 20 transactions**, soit +0,17 % du capital.

## 2. Baseline — transactions clôturées dimensionnées (18/09 19:28 → 20/09 15:52 UTC, ~44 h)

| Mesure | Valeur |
|---|---|
| Transactions (gagnantes / perdantes) | 20 (7 / 13) |
| Résultat brut / frais / net | +33,33 € / 25,01 € / **+8,31 €** |
| Gain moyen / perte moyenne | +12,59 € / −6,14 € |
| Espérance nette par transaction | +0,42 € |
| Durée moyenne | **0,33 h (20 min)** sur des bougies 1h |
| Motif de sortie | **20/20 `pipeline_downgraded`** ; 0 stop, 0 objectif |
| Drawdown max (positions ouvertes incluses) | −2,92 % |
| Dépendance à un cas | PEPE +41,84 € > net total ; sans elle, −33,5 € |

- Frais = 75 % du brut. Frais modélisés : commission 5 bps par côté, spread 2 bps + slippage 3 bps par côté (`paper/risk.py`), soit ≈ 20 bps aller-retour. Aucun financement ni funding.
- Réconciliation : cash 1 291,30 + notionnels ouverts 3 715,2 = 5 006,5 ≈ 5 000 + 8,31 − frais d'entrée des ouvertes. Le cash est cohérent avec le réalisé. Le grand livre (`brokerage/ledger`) est encore non commité et n'existe pas sur le VPS : pas de réconciliation par mouvements possible.
- 115 autres transactions « legacy » (avant le 18/09 19:23) n'ont ni quantité ni euros. À tenir à part, et à ne pas mélanger.
- Positions ouvertes : 2 legacy (LTC, AVAX) sans quantité, **exclues de l'equity** ; APT ; 2 × NEAR.

## 3. Défauts et biais constatés

1. **Bougie non clôturée.** `scan_symbol` calcule Ichimoku/RVOL sur `candles[-1]`, la barre 1h en formation, rafraîchie toutes les 5 min (`screener/cache.py`, `screener/service.py`). Les signaux clignotent dans l'heure, d'où 20 min de durée moyenne. La règle « bougies clôturées » n'est pas respectée : c'est la cause probable de la sur-rotation et des frais.
2. **APT jamais clôturée.** Position `user_confirmed` : plus haut 0,7790 > objectif 0,7789 **et** plus bas 0,6970 < stop 0,7031, pourtant toujours OPEN. `sync_position` ne teste stop/objectif que dans la boucle auto-watchlist. Gain potentiel ~+85 € réalisable, ou perte au stop, non constaté.
3. **Deux NEAR ouvertes dans le même portefeuille** (une auto, une user_confirmed), contre la règle « unique open (portfolio, symbol, timeframe) ».
4. **Stop/objectif évalués sur le prix de fin de cycle**, pas sur high/low : gaps et mèches invisibles.
5. **Portefeuilles doublons** : `ICHIVOL_MS_V1` = `STRUCTURE_CONSENSUS`, `ICHIVOL_CTX_RSI` = `ICHIVOL_CTX_FULL` (résultats identiques au centime).
6. **Aucun compteur de rejets** persisté par étape du pipeline : l'entonnoir du point 2 de la mission ne peut pas être reconstitué. Il faut l'instrumenter.
7. Univers : crypto Binance uniquement pour le paper (1h). Forex, métaux, indices et actions exclus de `sync_auto_watchlist`.
8. Les 11 autres portefeuilles (structure, contexte) tournent déjà en parallèle sur les mêmes cycles, avec des périodes de départ différentes (18/09 19:43, 19:51, 22:03, 09:50 le 19/09) : ils ne sont pas comparables tels quels.

## 4. Limites de risque en place (`paper/strategy_profiles.py`)

Risque 1 % par trade, notionnel max 25 % de l'equity, 5 positions max, objectif 2R, stop ATR obligatoire. **Absents** : plafond de risque cumulé, limite par famille/corrélation, perte journalière max, arrêt/reprise, délai entre entrées. Levier : aucun.

## 5. Conclusion

Résultat insuffisant pour décider. 20 transactions sur 44 h, une seule (PEPE) explique plus que le net, l'exécution sur bougie non clôturée gonfle la rotation et les frais. Ne pas annualiser.
