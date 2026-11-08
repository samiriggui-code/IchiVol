# Ève décide, le moteur calcule (2026-11-08)

Décision du propriétaire après l'audit du 08/11 : « le moteur ne doit pas être devant mais derrière JEV et Ève, pour
fournir les outils à Ève ». Paper uniquement.

## Constat
217 abstentions sur 217 dossiers depuis le 17/10 ; les 40 trades automatiques du compte unique étaient des trades
refusés par Ève (`engine_over_eve`). La porte d'entrée exigeait 0,55 de confiance sur `execution_quality`, qui n'a
jamais dépassé 0,17 : on demandait à JEV de juger un stop et un spread qu'il ne recevait pas.

## Rôles
| Qui | Fait quoi | Où |
|---|---|---|
| Moteur | classe les opportunités, calcule stop, objectif, coûts, seuil de rentabilité `p_min`, volume, tendance, exposition | `paper/engine.py` (`eve_candidate`, `candidate_score`), `eve/engagement.py` (`build_trade_plan`) |
| JEV | NOUL = probabilité d'atteindre l'objectif avant le stop (`long_target`, `short_target`) ; CHOICE = direction ; SCORE et avis = réduction de taille | `eve/modes.py` |
| Ève | s'engage si `p > p_min`, risque selon l'écart | `eve/engagement.py` (`decide_engagement`), `eve/orchestrator.py` |
| Risk Kernel | dernier mot : kill switch, plafonds, risque ouvert | `paper/risk_kernel.py` |

`p_min = (1 + coût_R) / (objectif_R + 1)`. JEV ne reçoit jamais ce seuil.

## Dosage (profil `engagement`)
Risque de 0,25 % (écart nul) à 1 % (écart ≥ 0,20), multiplié par fragilité, porte d'entrée, audit, confiance JEV, volume
et tendance des horizons supérieurs, plancher 0,10 %. Lot max : crypto 1× l'équité, autres 3×.

## Marge (profil `margin`, `paper/margin.py`)
La caisse peut passer sous zéro (emprunt) : crypto au comptant 1× au total, CFD et futures 5× l'équité. Une caisse
négative à l'écran est donc normale. Les plafonds de risque ouvert (4 %) et de perte journalière (3 %) restent.

## Ce qui bloque encore
Kill switch, verrou de perte journalière, données périmées, JEV en panne ou en retard, pas de stop, coûts > 0,5 R,
`p <= p_min`, alerte critique du Guardian, confiance élevée sur un `block` ou un conflit signal/régime, audit
choisissant le sens opposé.

## Budget et comparaison
8 symboles au plus par bougie fermée, les signaux du moteur d'abord. Sans signal du moteur, le filtre de régime est une
information pour Ève. Quand Ève s'abstient sur un vrai signal du moteur, celui-ci est rejoué en trade fantôme
(`shadow_positions`, coûts réels par symbole) : c'est le livre « moteur seul ». `engine_over_eve` ne subsiste que pour
l'historique.

## Limite connue
Le pourcentage de JEV n'est pas calibré. Rejeu sur 40 décisions passées (médiane 0,47, 33 au-dessus du seuil) : 0,49 en
moyenne sur les perdants, 0,45 sur les gagnants. Ne pas élargir la fourchette de risque ni le levier avant d'avoir
vérifié ces pourcentages sur quelques centaines de décisions (`decision_time.jev_probabilities`).
