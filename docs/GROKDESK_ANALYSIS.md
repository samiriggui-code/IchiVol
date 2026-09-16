# GROKDESK — Analyse technique

Repo analysé : `https://github.com/GrokDesk/grokdesk` (clone shallow dans `_research/grokdesk/`, commit au moment du clone : voir `_research/grokdesk/.git`).

**Constat général avant tout le reste** : GrokDesk n'est PAS l'application riche (dashboard + backend + DB + multi-agents LLM + Polymarket) que la présentation publique du projet laisse penser. C'est un **simulateur Python autonome de ~1300 lignes**, sans dépendance externe, qui tourne en CLI et imprime un scoreboard. Le "dashboard" est un fichier HTML statique non connecté au moteur. Il n'y a ni base de données, ni API, ni broker réel, ni notion de probabilité de marché. Le PnL affiché dans le README/les réseaux sociaux provient de données **synthétiques générées aléatoirement** avec une variable cachée `quality` qui pilote le taux de succès — ce n'est ni un backtest sur données réelles, ni une performance qui se transpose telle quelle.

Ce constat n'invalide pas la mission : GrokDesk reste intéressant comme **patron d'architecture** (orchestration multi-agents, boucle hire/fire, auto-calibration bornée d'une matrice de scoring, hiérarchie de véto Risk > tout). Mais il faut recalibrer les attentes : peu de code est directement réutilisable, beaucoup de patterns le sont.

---

## 1. Architecture générale

```
runtime.py (build + boucle de simulation asyncio)
   │
   ├── Bus (pub/sub async, topics: signal / candidate / entry / close)
   ├── LLM (wrapper Grok/OpenAI-compatible, fallback offline déterministe)
   ├── ScoringMatrix (poids + seuils mutables, réécrits par AUDIT)
   ├── Ledger (wallet + vault + historique trades, en mémoire)
   ├── PaperBroker (exécution simulée contre une bonding curve)
   ├── PumpFun (générateur de mints synthétiques aléatoires)
   └── 6 Desks (Radar, Research, Execution, Risk, Audit, Treasury)
         chacun avec ses "agents" (dataclasses légères, pas des LLM individuels)
   └── GrokCore ("head of desk", agent 19, revue horaire hire/fire)
```

Le pipeline event-driven : `Radar.observe → bus:signal → Research.on_signal → bus:candidate → Execution.on_candidate → bus:entry → (résolution simulée) → bus:close → Audit.on_close`.

Tout tourne dans un seul process, en mémoire, piloté par une boucle `asyncio` synchrone (pas de vrais I/O réseau sauf l'appel LLM optionnel).

## 2. Frontend

Il n'y a pas de frontend applicatif. `assets/terminal.html` (355 lignes) est une page HTML/CSS/JS **statique et autonome** : esthétique "terminal de trading" très soignée (grille, ticker, cartes d'agents, courbes), mais entièrement animée avec des données factices câblées en dur dans le JS. Vérifié : **aucun** `fetch`/`WebSocket`/`XMLHttpRequest` dans le fichier — zéro connexion au moteur Python. C'est un asset marketing, pas un dashboard fonctionnel.

## 3. Backend

Aucun serveur HTTP, aucune API REST/GraphQL, aucun websocket. Le "backend" est un script CLI (`python -m grokdesk`) qui construit les objets en mémoire (`runtime.build()`) et exécute une simulation minute par minute (`tick`) jusqu'à épuisement du nombre d'heures demandé, puis affiche un résumé texte.

## 4. Agents

19 "agents" au total, mais **ce ne sont pas des agents LLM individuels**. Chaque agent est une `dataclass` (`desks/base.py::Agent`) avec :
- `name`, `desk`, `budget` (float, 0.2–2.0), `score` (float 0–1, borné), `alive`, `prompt_rev` (compteur), `stats: dict` (flags ad hoc comme `loose`, `stale`).
- Une seule méthode : `credit(good: bool, w: float)` qui pousse le score de `±w`.

Seul **un** point du système appelle réellement un LLM : `Research.on_signal` → `llm.score_narrative()`. Sans clé API (`XAI_API_KEY`/`OPENAI_API_KEY`), le score est un hash déterministe du symbole (`sha256(symbol|blurb) % 1000 / 1000`) — donc même en mode "réel", il n'y a qu'un seul point de contact LLM sur toute la desk, pas 19 personas qui raisonnent.

Les 6 desks :
| Desk | Rôle réel dans le code |
|---|---|
| RADAR | Round-robin sur 3 agents, émet un `Signal` sauf si l'agent est trop lent (poll_s) et que la pièce a déjà "gradué" (signal obsolète → pénalité) |
| RESEARCH | Un agent (round-robin) calcule 4 sous-scores (narrative/deployer/clusters/liquidity), agrège en pondéré, compare à un seuil |
| EXECUTION | Sélectionne un trader parmi 7 (round-robin sur positions ouvertes), demande une taille à RISK, achète via PaperBroker |
| RISK | Un seul agent, applique des règles fixes (voir §8) |
| AUDIT | Grade les trades clos, ajuste `ScoringMatrix`, "réécrit" les agents virés |
| TREASURY | Gèle/dégèle RISK selon drawdown, sweep périodique vers un "cold vault" |

## 5. Moteur de décision

Pas de vote/consensus multi-agents au sens propre. RESEARCH tire **un seul agent** par signal (round-robin) qui calcule un score agrégé pondéré contre un seuil (`pass_threshold`). Il n'y a pas d'agrégation de plusieurs avis divergents, pas de pondération dynamique par régime de marché — seulement une matrice de poids globale, réajustée a posteriori par AUDIT.

`EXECUTION.on_candidate` : vérifie `Risk.allow()` (veto), choisit un trader disponible, demande une taille, achète. Aucune notion de "direction" (long/short) : dans l'univers pump.fun, on n'est jamais qu'acheteur.

## 6. Données marché

100% synthétique et propre au domaine pump.fun : `market/pumpfun.py::PumpFun.new_coin()` génère des mints aléatoires avec un `deployer`, un `funder` (dont certains marqués `-rug` pour simuler des rugpulls en cluster), un `trend` (0–1) et surtout une **variable cachée `quality`** (0–1, loi normale) qui détermine directement la probabilité de gain dans `runtime.py::on_entry` (`win = rng.random() < 0.12 if is_rug else 0.30 + 0.5*q`). Autrement dit : le "marché" est scripté pour produire un P&L crédible, pas une simulation de dynamique de marché réelle. `market/bonding_curve.py` implémente une vraie formule de bonding curve à produit constant (x*y=k), c'est le seul bout de "market microstructure" authentique du repo.

Aucune connexion à un flux de données réel (pas d'API pump.fun, pas de websocket on-chain).

## 7. Probabilités

Pas de moteur bayésien, pas de calibration formelle (Brier score, log-loss...), pas de notion de **probabilité de marché** à comparer à une probabilité modèle (contrairement à ce que ferait un adapter Polymarket). `score_narrative()` retourne un flottant 0–1 utilisé comme un sous-score parmi 4, pas comme une probabilité calibrée de succès du trade. Il n'y a rien ici qui réponde à la question "P(direction | observations)" posée dans la mission — c'est à construire de zéro côté projet principal.

## 8. Risk management

`desks/risk.py`, très simple et déclaratif (`config/desk.yaml`) :
- `max_position_fraction = 0.15` du wallet courant
- `max_open_positions = 3`
- `max_entries_per_hour = 6`
- Gel total piloté par TREASURY si `wallet < 0.6 * start` (dégel à `>= 0.9 * start`)

Pas de Kelly, pas de VaR, pas d'exposition par cluster/corrélation, pas d'EV attendue calculée avant l'entrée. Le point fort réel : **RISK a un droit de veto absolu** (`Execution.on_candidate` appelle `risk.allow()` avant tout achat, et personne ne peut le contourner) — c'est une bonne propriété architecturale, indépendante de la sophistication des règles.

## 9. Sizing

`Risk.size_for(agent)` : `size = clamp(0, wallet * 0.15, 0.25 * max(0.2, agent.budget))`. Le `budget` d'un agent (0.2 à 2.0) est le seul levier de modulation, et il évolue uniquement via `GrokCore._promote()` (le meilleur agent du roster gagne +0.2 par heure, plafonné à 2.0). Aucun lien avec la confiance du signal, la volatilité, ou un edge calculé — c'est un sizing "mérite de l'agent", pas un sizing "qualité du pari".

## 10. Paper trading

`market/broker.py::PaperBroker` : achète/vend contre la bonding curve simulée, débite/crédite le `Ledger`, prélève un gas fixe (0.003 SOL). C'est un vrai paper broker (mouvements d'argent simulés cohérents), mais le **résultat du trade lui-même n'est pas dérivé du broker** — il est pré-décidé dans `runtime.py::on_entry` par un tirage aléatoire (`win = rng.random() < ...`) indépendant du prix réel de sortie sur la courbe. Le broker exécute un résultat déjà écrit, il ne le découvre pas. À garder à l'esprit : ce n'est pas un moteur de paper trading généraliste, c'est un mécanisme comptable pour un résultat scripté.

## 11. Persistence

**Aucune.** Tout est en mémoire (`Ledger.trades: list`, `Audit.log: list`, `ScoringMatrix.history: list`). Rien n'est écrit sur disque pendant le run ; à la fin, un résumé est simplement imprimé sur stdout (`runtime.py::_summary`). Pas de SQLite, pas de fichiers JSON/CSV de sortie, pas de rejouabilité d'un run passé.

## 12. Logs

Pas de logging structuré (pas de `logging` module, pas de niveaux, pas de fichier log). Uniquement des `print()` de HUD horaire (`_hud()`) et le résumé final. `Audit.log` et `ScoringMatrix.history` sont les deux seules structures qui accumulent un historique, mais uniquement en RAM pour la durée du run.

## 13. Dashboard

Voir §2 : `assets/terminal.html` est un mockup visuel statique, non branché. Il n'y a pas de dashboard fonctionnel à étudier pour son "vrai" comportement — seulement pour son esthétique et sa disposition d'information (cartes d'agents, ticker, ribbon de métriques), qui peut inspirer une maquette UI mais ne contient aucune logique réutilisable.

## 14. Dépendances externes

`requirements.txt` fait 3 lignes (à vérifier mais le repo revendique "No dependencies. Python 3.10+" dans le README) — uniquement stdlib : `asyncio`, `dataclasses`, `hashlib`, `random`, `string`, `urllib.request`. L'unique dépendance externe optionnelle est réseau : un appel HTTP vers `https://api.x.ai/v1` ou un endpoint OpenAI-compatible, activé seulement si une clé d'API est présente. Aucun framework web, aucun ORM, aucune lib de calcul scientifique.

## 15. Composants réellement réutilisables

Ce qui mérite d'être porté (comme **pattern**, rarement comme **code tel quel**, voir `GROKDESK_REUSABLE_COMPONENTS.md` pour le détail) :

1. **Bus pub/sub minimal** (`bus.py`) — découplage propre par topics, portable presque tel quel en TypeScript.
2. **Hiérarchie de véto** — Risk peut bloquer n'importe quelle exécution, Treasury peut geler Risk. Bonne propriété à reproduire dans le pipeline `Consensus → Edge → Risk → Execution`.
3. **Matrice de scoring auto-calibrée avec bornes (`clamp`)** (`scoring.py::ScoringMatrix.tighten`) — pattern intéressant pour l'ajustement de poids de stratégie, **mais** son application est automatique et non supervisée, ce qui contredit la règle explicite de la mission (jamais de modification automatique des règles en prod) — à adapter, pas à copier.
4. **Séparation stricte Observation → Decks spécialisés → Décision → Risque → Exécution**, même si dans GrokDesk chaque étage est très simple.
5. **Ledger wallet/vault avec sweep périodique** — idée simple et saine pour la gestion de trésorerie du paper trading.

Ce qui ne sert à rien à récupérer : `market/pumpfun.py`, `market/bonding_curve.py` (100% spécifique Solana/pump.fun), `llm.py` (trivial), `assets/terminal.html` (déconnecté), toute la logique de "firing"/"rewrite" d'agent (cosmétique, ne fait aucun vrai réentraînement).
