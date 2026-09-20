# Revue lecture seule — moniteur de protection (D3) et code D5 face à `SPEC-FWD-E-LONG`

**Auteur :** ichivol-36 · **Date :** 2026-09-20 · **Lu :** `release/d5-2026-09-20` (`a987b8d`, qui contient D3 `0b0cd69`, D3b `c67995b`, D2 `e933c1d`) via `git show`, sans rien extraire ni modifier. Fichiers : `app/paper/protection.py`, `broker.py`, `engine.py`, `strategy_profiles.py`, `main.py`, `config.py`, `brokerage/persistence.py`, `brokerage/execution.py`.
**Vérifications exécutées :** cinq scénarios synthétiques sur `find_first_breach` (version d5 extraite dans un dossier temporaire, hors du dépôt) : résultats en §3. Je n'ai **pas** lancé les tests des branches.

## Verdict

- **Règles de sortie et de stop du moniteur : saines** (pas de look-ahead avant l'entrée, gap au prix d'ouverture ou du tick, stop d'abord en cas d'ambiguïté).
- **Deux défauts à corriger avant l'activation** : double fermeture possible entre le moniteur et la boucle automatique (H1), et un moniteur qui s'arrête entièrement si un seul symbole échoue (H2).
- **Conformité D5 / spec : bonne**, avec un écart (M2, timeframe).

## 1. À corriger avant l'activation

| # | Constat | Pourquoi c'est réel | Correctif proposé |
|---|---|---|---|
| **H1** | **Double fermeture (double crédit de trésorerie)**. `close_capital_position` contrôle `position.status != "OPEN"` **avant** de prendre le verrou du portefeuille, et `_lock_portfolio` ne rafraîchit que le portefeuille, pas la position. | Le moniteur charge toutes les positions ouvertes, puis fait des appels réseau (klines, aggTrades) par position, pendant plusieurs secondes. La boucle automatique détecte **le même franchissement de stop** (`check_stop_or_tp` sur le prix du cycle) et ferme la position dans une autre transaction. Le moniteur détient un objet position périmé (`OPEN`), attend le verrou, relit le portefeuille (avec le crédit de l'autre), puis ajoute le sien. Le scénario se produit **exactement au moment du franchissement** : c'est le cas le plus probable. Ensuite `close:{id}` déjà posté → `DuplicateConflict` capturé en `LEDGER_ERROR`, mais la trésorerie, l'ordre et `realized_pnl` sont déjà doublés (`reconcile` le signalera, il ne corrige rien). | Après `_lock_portfolio`, `session.refresh(position)` (ou verrou de ligne sur la position) puis re-test du statut ; dans le moniteur, recharger chaque position juste avant de la fermer et **valider par position**. Test : deux sessions ferment la même position en parallèle → un seul crédit, un seul ordre. |
| **H2** | **Point de défaillance unique.** `run_protection_cycle` n'a aucun `try/except` par position et ne valide qu'à la fin. | `raise_for_status()` lève sur une erreur 400/429/réseau : le cycle échoue, la boucle fait `rollback()` (les fermetures déjà faites dans ce cycle sont annulées) et recommence 60 s plus tard. Un seul symbole en erreur permanente (paire retirée ou gelée, symbole invalide) **prive toutes les positions de protection**, indéfiniment. | `try/except` autour de chaque position (statut `error`, journal), validation par position, alerte après N échecs consécutifs. Test : `klines_fn` qui lève pour un symbole, les autres restent traités. |

## 2. À planifier

| # | Constat | Correctif proposé |
|---|---|---|
| **M1** | **Activé par défaut** : `enable_protection_monitor: bool = True` (`config.py`). Le plan prévoyait « essai à blanc puis réel » ; le commit `0b0cd69` le livrait désactivé, `c67995b` l'active. Un déploiement de D3b démarre donc l'application des stops sans étape `--dry-run` préalable. | Valeur par défaut `False`, activation par variable d'environnement après lecture du rapport `--dry-run`. |
| **M2** | **Sortie E indépendante du timeframe du lot.** La règle `exit_mode == "direction" and existing.source == source` ignore `existing.timeframe`. `sync_position` est appelé pour chaque ligne (symbole, timeframe) ; `_get_open_by_symbol` renvoie le lot du symbole tous timeframes confondus. Si la surveillance couvre plusieurs timeframes par symbole (à confirmer dans la configuration), la direction Ichimoku du timeframe Y peut fermer un lot ouvert sur le timeframe X. Même défaut préexistant pour les sorties par décision. | Ajouter `and existing.timeframe == timeframe`, et le préciser dans la spec (la direction est celle du timeframe du lot). Test : deux lignes pour un même symbole, la direction de l'autre timeframe ne ferme rien. |
| **M3** | **Absence de données = absence de franchissement.** (a) Réponse `klines` vide : le repère avance à `end_closed` (vérifié : +30 min sans aucune barre lue). Un incident du fournisseur, ou un symbole gelé (TONUSDT) passe pour « ok ». (b) Minute d'entrée sans ticks : ignorée (vérifié : creux à 90 sous un stop à 95 non vu). (c) `aggTrades` : plafond 20 × 1 000 trades, pagination par `endTime + 1 ms` (des trades de la même milliseconde peuvent être sautés). | Distinguer « minute sans trade » de « pas de données » (statut `no_data`, ne pas dépasser la dernière barre vue plus une marge) ; paginer avec `fromId`. |
| **M4** | **Sémantique du lot « legacy »** : le code **ne ferme jamais un lot legacy sur reconstruction de l'historique** (`history_breach` est seulement rapporté, watermark « maintenant ») — mais il **ferme les lots legacy sur un franchissement postérieur au watermark** (l'événement `PROTECTION_CHECKED` porte `legacy: True` et le lot repasse dans le scan normal). Un lot déjà au-delà de son stop à l'activation est fermé dans la minute suivante (première barre ouverte au-delà du niveau → `stop_gap`). La boucle (`check_stop_or_tp`, préexistant) le fermerait de toute façon au cycle suivant. | Si l'exigence est « jamais » : `if legacy: rapporter seulement`. Sinon, l'écrire explicitement dans le plan de release (sinon un lot manuel ancien sera fermé à l'activation). |
| **M5** | **Deux fermeurs, deux conventions de prix.** La boucle ferme au **prix du cycle** (potentiellement bien au-delà du stop) ; le moniteur ferme au **niveau du stop** (ou à l'ouverture / au tick en cas de gap), à une heure antidatée (`at`). Le moniteur gagne presque toujours (60 s). De plus, `exit_reason` gagne `stop_gap`. | Documenter ; dans l'analyse du forward test, regrouper `stop_hit` et `stop_gap` comme « stop », et noter la part de fermetures faites par la boucle. |

## 3. Vérifié correct (scénarios synthétiques, version d5)

| Scénario | Résultat |
|---|---|
| Barre suivante ouverte à 93 sous un stop à 95 | `stop_gap` au prix **93** (ouverture), pas au niveau |
| Stop et objectif dans la même minute, sans ticks | `stop_hit` au niveau, note « stop assumed first » |
| Idem avec ticks, objectif atteint d'abord | `take_profit_hit`, granularité `tick` |
| Entrée au milieu d'une minute | Seuls les ticks **postérieurs à l'heure d'entrée** comptent : un plus bas de la minute d'entrée antérieur au fill n'est **jamais** utilisé (pas de look-ahead avant l'entrée) |
| Fenêtre bornée aux minutes closes | La minute en formation est laissée au cycle suivant |

Limites mineures : (i) `entry_time` est l'heure d'écriture, postérieure à l'échantillon de prix du screener : les ticks entre les deux sont exclus, léger optimisme (utiliser l'heure de l'échantillon) ; (ii) le couplage `"both inside bar" in r.note` avec le texte de `execution.py` est fragile (indicateur structuré + test) ; (iii) heure de franchissement à la minute (`at` = ouverture de la barre 1 m) et livre sans colonne de séquence ; (iv) un événement `PROTECTION_CHECKED` par position toutes les 15 min (≈ 96/jour) à purger.

## 4. Conformité D5 à `SPEC-FWD-E-LONG-2026-09-20`

| Point de la spec | Code d5 | Statut |
|---|---|---|
| Sortie E = direction ≠ LONG (NEUTRAL ou SHORT), pas de sortie sur simple WATCH | `_pdir == existing.direction → return None`, sinon `direction_flipped` | Conforme |
| Lots d'une autre source jamais fermés par le signal (D1b) | condition `existing.source == source` ; sinon retour `None` ; stop/objectif restent surveillés | Conforme |
| Stop / objectif avant la règle de direction | `check_stop_or_tp` s'exécute en premier | Conforme (au prix du cycle ; voir M5) |
| Pas de short, sans consommer la série de signal | `short_not_allowed` avant les gates, compteur si `log_rejections` | Conforme |
| Données périmées : aucune décision de sortie | ligne ignorée (`signal_timing.stale`) ; le moniteur garde les protections | Conforme |
| Clés de profil, valeurs par défaut = comportement actuel | `allow_short` / `exit_mode` avec défauts ; `FWD_*` figés ; commission 7,5 bps ; barème par symbole identique à ma table (arrondi 0,1) | Conforme |
| Timeframe du lot | non contrôlé | **Écart (M2)** |
| Une seule fermeture, une seule jambe de livre | garde de statut + verrou portefeuille, mais avec objet périmé | **Écart (H1)** |
| Bougies clôturées uniquement (T7) | dépend de `signal_timing` / `_closed_only`, non relu ici | Non vérifié |

## 5. Ce que je n'ai pas fait
Aucun test de branche exécuté ; aucune vérification sur la base du VPS ; la configuration réelle de la surveillance (nombre de timeframes par symbole) n'est pas vérifiée — M2 est conditionnel.
