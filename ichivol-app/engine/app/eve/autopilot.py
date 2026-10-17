"""Ève autopilot — the engine proposes, Ève (with JEV) decides, the Risk Kernel has the last word.

Active only when ``EVE_PAPER_AUTONOMY`` is on. The background screener cycle then runs every portfolio's own
method (BASELINE, SESSIONS, Futures & Crypto…) as usual, but the engine's signal no longer opens or closes a lot:
each would-be open/close becomes a *proposal* (``paper.engine.sync_auto_watchlist(proposals=...)``).

For each symbol with at least one proposal, Ève runs once per closed bar (Analyst → Challenger → Guardian →
Shadow with JEV), a Dossier is written, then every proposal on that symbol is accepted or refused:

* proposal OPEN LONG/SHORT → opened only if Ève's action is that same direction;
* proposal CLOSE → closed only if Ève says CLOSE or the opposite direction; otherwise the lot is kept.

Accepted proposals go through ``paper_submit`` (Risk Kernel, entry gate, degradation: JEV down = nothing opens).
A refused OPEN becomes a shadow trade (``block_source="eve"``, ShadowBroker, no cash) so "was Ève right to refuse?"
gets measured the same way as the indicator filters.
What the engine alone would have done stays in the Dossier (``decision_time.engine_proposals``) so "engine alone"
and "Ève + JEV" can be compared on the same books. Stops and targets still close lots on their own. Paper only.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.eve.actions import normalize_action

logger = logging.getLogger(__name__)

_OPPOSITE = {"LONG": "SHORT", "SHORT": "LONG"}


def eve_accepts(proposal: dict[str, Any], eve_action: str | None, position_direction: str | None = None) -> bool:
    """Does Ève's action accept this engine proposal? Undecided (HOLD / ABSTAIN) never acts."""
    action = normalize_action(eve_action) or "ABSTAIN"
    if proposal.get("action") == "OPEN":
        return action == proposal.get("direction")
    if proposal.get("action") == "CLOSE":
        if action == "CLOSE":
            return True
        return position_direction is not None and action == _OPPOSITE.get(position_direction)
    return False


def open_refusal_shadow(
    session: Session, proposal: dict[str, Any], eve_action: str, dossier_id: str | None
) -> str | None:
    """Counterfactual of a refused OPEN: same SL/TP geometry as the book, never touches cash."""
    from app.paper.portfolio import get_portfolio_by_code
    from app.shadow.broker import open_shadow

    raw = {"LONG": "BUY", "SHORT": "SELL"}.get(str(proposal.get("direction")))
    price = proposal.get("price")
    portfolio = get_portfolio_by_code(session, str(proposal["portfolio_code"]))
    if raw is None or portfolio is None or not isinstance(price, (int, float)):
        return None
    shadow = open_shadow(
        session,
        portfolio=portfolio,
        symbol=str(proposal["symbol"]),
        timeframe=str(proposal["timeframe"]),
        raw_decision=raw,
        price=float(price),
        stop_distance=proposal.get("stop_distance"),
        block_source="eve",
        block_reason=eve_action,
        meta={"eve_dossier_id": dossier_id, "engine_decision": proposal.get("engine_decision")},
    )
    return shadow.id if shadow is not None else None


def _group(proposals: list[dict[str, Any]]) -> "OrderedDict[tuple[str, str], list[dict[str, Any]]]":
    groups: OrderedDict[tuple[str, str], list[dict[str, Any]]] = OrderedDict()
    for p in proposals:
        groups.setdefault((str(p["symbol"]), str(p["timeframe"])), []).append(p)
    return groups


class EveAutopilot:
    """Processes the engine's proposals in its own thread so a slow JEV never delays the screener."""

    def __init__(
        self,
        *,
        max_symbols_per_cycle: int = 8,
        evaluate: Callable[..., dict[str, Any]] | None = None,
        submit: Callable[..., dict[str, Any]] | None = None,
        shadow: Callable[..., str | None] | None = None,
    ) -> None:
        self.max_symbols_per_cycle = max_symbols_per_cycle
        self._evaluate = evaluate
        self._submit = submit
        self._shadow = shadow
        self._pending: list[dict[str, Any]] | None = None
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # (symbol, timeframe, signal_bar_close) already judged → Ève runs once per closed bar, not every refresh.
        self._judged: OrderedDict[tuple[str, str, Any], dict[str, Any]] = OrderedDict()
        self.last_cycle: dict[str, Any] | None = None

    # -- lifecycle -------------------------------------------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="eve-autopilot")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def submit_proposals(self, proposals: list[dict[str, Any]]) -> None:
        """Called by the screener cycle. A newer batch replaces one not yet processed (never a backlog)."""
        if not proposals:
            return
        with self._lock:
            self._pending = list(proposals)
        self._wake.set()

    def _loop(self) -> None:
        from app.db.session import SessionLocal

        while not self._stop.is_set():
            self._wake.wait()
            self._wake.clear()
            with self._lock:
                batch, self._pending = self._pending, None
            if not batch or self._stop.is_set():
                continue
            session = SessionLocal()
            try:
                self.last_cycle = self.run_cycle(session, batch)
            except Exception:  # noqa: BLE001 -- a failed cycle must not kill the loop
                logger.warning("eve autopilot cycle failed", exc_info=True)
                session.rollback()
            finally:
                session.close()

    # -- one cycle -------------------------------------------------------------------------------------------
    def run_cycle(self, session: Session, proposals: list[dict[str, Any]]) -> dict[str, Any]:
        from app.eve import paper_submit
        from app.eve.dossier import get_dossier
        from app.eve.orchestrator import evaluate_opportunity
        from app.db.models import PaperPosition

        evaluate = self._evaluate or evaluate_opportunity
        submit = self._submit or paper_submit.submit_to_portfolio
        shadow = self._shadow or open_refusal_shadow

        report: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "autonomy_enabled": paper_submit.autonomy_enabled(),
            "symbols": [],
            "skipped_already_judged": 0,
            "skipped_over_budget": 0,
        }
        if not report["autonomy_enabled"]:
            report["note"] = "autonomie coupée : Ève ne décide rien"
            return report

        evaluated = 0
        for (symbol, timeframe), group in _group(proposals).items():
            bar = group[0].get("signal_bar_close")
            key = (symbol, timeframe, bar)
            if bar is not None and key in self._judged:
                report["skipped_already_judged"] += 1
                continue
            if evaluated >= self.max_symbols_per_cycle:
                report["skipped_over_budget"] += 1
                continue
            evaluated += 1

            evaluation = evaluate(symbol, timeframe, session=session, persist=True, paper_dry_run=False)
            eve_action = normalize_action(evaluation.get("eve_action")) or "ABSTAIN"
            dossier_id = evaluation.get("dossier_id")
            outcomes: list[dict[str, Any]] = []
            for proposal in group:
                position_direction = None
                if proposal.get("action") == "CLOSE" and proposal.get("position_id"):
                    pos = session.get(PaperPosition, proposal["position_id"])
                    position_direction = getattr(pos, "direction", None)
                accepted = eve_accepts(proposal, eve_action, position_direction)
                outcome: dict[str, Any] = {
                    "portfolio_code": proposal["portfolio_code"],
                    "engine_action": proposal["action"],
                    "engine_direction": proposal.get("direction"),
                    "engine_decision": proposal.get("engine_decision"),
                    "eve_action": eve_action,
                    "eve_accepts": accepted,
                }
                if accepted and dossier_id:
                    res = submit(
                        session,
                        dossier_id,
                        portfolio_code=proposal["portfolio_code"],
                        price=proposal.get("price"),
                        stop_distance=proposal.get("stop_distance"),
                        execute=True,
                        action_override="CLOSE" if proposal["action"] == "CLOSE" else None,
                    )
                    outcome["status"] = res.get("status")
                    outcome["executed"] = bool(res.get("executed"))
                    outcome["risk_authorization"] = res.get("risk_authorization")
                else:
                    outcome["status"] = "refused_by_eve" if dossier_id else "no_dossier"
                    outcome["executed"] = False
                    if dossier_id and proposal.get("action") == "OPEN":
                        try:
                            outcome["shadow_id"] = shadow(session, proposal, eve_action, dossier_id)
                        except Exception:  # a counterfactual must never break Ève's cycle
                            logger.exception("eve refusal shadow failed for %s", proposal.get("portfolio_code"))
                outcomes.append(outcome)

            if dossier_id:
                dossier = get_dossier(session, dossier_id)
                if dossier is not None:
                    dt = dict(dossier.decision_time_json or {})
                    dt["engine_proposals"] = outcomes
                    dossier.decision_time_json = dt
            session.commit()

            judged = {"eve_action": eve_action, "dossier_id": dossier_id, "outcomes": outcomes}
            if bar is not None:
                self._judged[key] = judged
                while len(self._judged) > 500:
                    self._judged.popitem(last=False)
            report["symbols"].append({"symbol": symbol, "timeframe": timeframe, **judged})

        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        return report


eve_autopilot = EveAutopilot()
