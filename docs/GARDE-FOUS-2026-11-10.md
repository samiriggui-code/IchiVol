# Garde-fous après le bilan du 10/11 (2026-11-10)

Paper uniquement. Branche `garde-fous-exposition-stops`.

## Constat (base de production, 27/10 → 10/11)
46 trades clôturés, −1 408 €, équité 48 320 € sur 50 000.
- 12 gagnants sur 46 (26 %) ; un stop coûte −82 € en moyenne, un objectif rapporte +118 € : il faudrait 41 %.
- JEV annonce 0,49 à 0,56 de chance de gain. Depuis le 08/11 cette probabilité dose la mise : WTI −560 € et
  EURUSD −278 €, soit 60 % de la perte en deux trades.
- Hors crypto, le stop n'était contrôlé que par le scan (300 s) et exécuté au prix du moment : EURUSD stop 1,12063,
  sortie 1,11812 (−2,8 R). Perte moyenne au stop : 1,3 R.
- Le 10/11, EURUSD, GBPUSD et or vendus en une heure : un seul pari dollar, 243 000 € d'exposition (5× l'équité).
- Ré-entrée ou retournement quelques heures après un stop (WTI, EURUSD).
- Financement de nuit débité dès l'ouverture : deux nuits pour 17 h de détention, une pour un trade de 1 h 40.

## Ce qui change
| Quoi | Avant | Après | Où |
|---|---|---|---|
| Risque par trade d'Ève | 0,25 % à 1 % selon l'écart JEV | 0,25 % fixe, moins les facteurs | `MAIN_PROFILE.engagement` |
| Lot CFD maximal | 3× l'équité | 1× | `engagement.other_max_notional_pct` |
| Total CFD et futures | 5× l'équité | 2× | `margin.other_max_exposure` |
| Paris corrélés | aucun contrôle | 1 lot par sens dans `dollar` (EURUSD, GBPUSD, XAUUSD, XAGUSD) et `indices_us` (SPX, NDX, YM), 3 en crypto ; refus `correlated_exposure_cap` | `correlation_groups`, `paper/risk_kernel.py` |
| Après un stop | ré-entrée immédiate possible | 8 h sans nouvelle entrée sur le symbole, dans les deux sens ; refus `reentry_cooldown` | `reentry_cooldown_hours`, `paper/gates.py` |
| Stop hors crypto | scan 300 s, prix du moment | minutes 1m biquote toutes les 60 s : stop touché = exécuté au stop, saut = à l'ouverture | `paper/protection.py` (`PROVIDER_FEEDS`) |
| Financement de nuit | débité le jour de l'ouverture | à partir du lendemain | `paper/financing.py` |

| Contre l'horizon supérieur | signal suivi | aucune ouverture si le pipeline porte `mtf_opposed` (4h contre le 1h), moteur comme Ève | `block_mtf_opposed`, `engine.trend_refusal` |
| Achats crypto | suivis | suspendus en automatique jusqu'au verdict du test sur repli ; refus `long_suspended` | `long_suspended_symbols`, `engine.long_suspension_refusal` |

Les ordres manuels passent toujours (comme pour les autres plafonds). Un lot de sens opposé dans un groupe
(couverture) est permis. Les lots ouverts ne sont pas touchés ; tant que l'exposition CFD dépasse 2×, aucun nouveau
lot CFD ne s'ouvre.

## Le fond : le signal perd avant frais
552 signaux BUY/SELL 1h avec résultat sur 20 bougies (`signal_evidence`, 21/09 → 10/11), stop 1,5 ATR, objectif 2 R,
stop compté en premier quand les deux sont touchés :

| Famille | n | objectif | stop | R moyen (± IC 95 %) |
|---|---|---|---|---|
| Tous | 552 | 20 % | 66 % | −0,20 ± 0,10 |
| BUY | 203 | 13 % | 78 % | −0,46 ± 0,15 |
| BUY crypto | 131 | 11 % | 80 % | −0,55 ± 0,17 |
| SELL | 349 | 23 % | 60 % | −0,05 ± 0,13 |
| `mtf_opposed` | 78 | 8 % | 82 % | −0,60 ± 0,20 |
| RVOL > 2,5 | 107 | 15 % | 76 % | −0,42 ± 0,21 |
| SELL sans `mtf_opposed` | 311 | 26 % | 57 % | +0,05 ± 0,15 |

Frais non comptés (environ 0,10 à 0,15 R). Aucune famille n'est nettement positive.

**Tendance journalière : ne trie rien.** Les achats crypto perdent autant quand l'Ichimoku 1d du symbole est haussier
(81 signaux, −0,54 R) ; le 1d du BTC n'a jamais été baissier sur la période. Aucun filtre 1d n'est donc ajouté.
Suite : [`REPLI-KIJUN-PREENREGISTREMENT-2026-11-10.md`](REPLI-KIJUN-PREENREGISTREMENT-2026-11-10.md).

## Non traité
- **Calibration de JEV** : toujours à faire ; rouvrir la fourchette de risque seulement après.
- **Ève suit le moteur** (7 signaux sur 9 suivis, le Challenger s'abstient) : aucun filtre ajouté ici.
- **Protection des gains** : 12 stops sur 31 avaient d'abord fait +1 R. Le stop suiveur existe
  (`protection_trail`, désormais utilisable hors crypto) mais reste éteint : sans le chemin de prix minute par minute
  des 11 gagnants, impossible de dire s'il aurait aidé. À tester en fantôme.
- Barres biquote au bid : le stop d'un short se déclenche un spread trop tard (0,8 bps sur EURUSD).
