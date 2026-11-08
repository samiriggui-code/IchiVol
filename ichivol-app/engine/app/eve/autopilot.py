"""Ève autopilot — the engine calculates, JEV measures, Ève decides, the Risk Kernel has the last word (2026-11-08).

Active only when ``EVE_PAPER_AUTONOMY`` is on. The engine's signal opens or closes nothing: each cycle it hands over
its opportunities (``paper.engine.sync_auto_watchlist(proposals=...)``): its own BUY/SELL, and every other row with a
known direction, ranked by ``score``. At most ``max_symbols_per_cycle`` symbols are judged per closed bar, best first.

For each symbol Ève runs once per closed bar (Analyst → Challenger → Guardian, with JEV, on the engine's plan), a
Dossier is written, then:

* Ève says LONG or SHORT → unless the independent audit picks the opposite side (``modes.audit_verdict``; the blocked
  OPEN becomes a shadow trade, ``block_source="audit"``), she trades, in her direction, for the amount of her
  ``engagement``;
* Ève abstains → no trade. If the engine had its own signal, it is played as a shadow trade (no cash): that is the
  "engine alone" book to compare her with.
* A CLOSE needs her agreement (CLOSE or the opposite direction), then the audit's.

Every trade goes through ``paper_submit`` and the Risk Kernel, and needs a healthy JEV and the entry gate. Stops and
targets still close lots on their own. Paper only.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.eve.actions import normalize_action
from app.eve.modes import audit_verdict

logger = logging.getLogger(__name__)

_OPPOSITE = {"LONG": "SHORT", "SHORT": "LONG"}


def eve_accepts(proposal: dict[str, Any], eve_action: str | None, position_direction: str | None = None) -> bool:
    """Does Ève act on this opportunity? OPEN: she picks the side. Undecided (HOLD / ABSTAIN) never acts."""
    action = normalize_action(eve_action) or "ABSTAIN"
    if proposal.get("action") == "OPEN":
        return action in ("LONG", "SHORT")
    if proposal.get("action") == "CLOSE":
        if action == "CLOSE":
            return True
        return position_direction is not None and action == _OPPOSITE.get(position_direction)
    return False


def open_refusal_shadow(
    session: Session,
    proposal: dict[str, Any],
    eve_action: str,
    dossier_id: str | None,
    block_source: str = "eve",
) -> str | None:
    """Counterfactual of a blocked OPEN: same SL/TP geometry as the book, never touches cash."""
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
        block_source=block_source,
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
        # Best opportunities first; a close on a held lot is never crowded out by a new idea.
        ranked = sorted(proposals, key=lambda p: float("inf") if p.get("action") == "CLOSE" else p.get("score") or 0.0, reverse=True)
        for (symbol, timeframe), group in _group(ranked).items():
            bar = group[0].get("signal_bar_close")
            key = (symbol, timeframe, bar)
            if bar is not None and key in self._judged:
                report["skipped_already_judged"] += 1
                continue
            # The budget is per closed bar: later cycles of the same bar must not walk down the ranking.
            judged_on_bar = sum(1 for k in self._judged if k[2] == bar) if bar is not None else 0
            if max(evaluated, judged_on_bar) >= self.max_symbols_per_cycle:
                report["skipped_over_budget"] += 1
                continue
            evaluated += 1

            evaluation = evaluate(
                symbol, timeframe, session=session, persist=True, paper_dry_run=False, candidate=group[0]
            )
            eve_action = normalize_action(evaluation.get("eve_action")) or "ABSTAIN"
            dossier_id = evaluation.get("dossier_id")
            shadow_mode = (evaluation.get("modes") or {}).get("shadow") or {}
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
                    "engine_signal": bool(proposal.get("engine_signal", True)),
                    "score": proposal.get("score"),
                }
                if not dossier_id:
                    outcome["status"] = "no_dossier"
                    outcome["executed"] = False
                    outcomes.append(outcome)
                    continue
                is_close = proposal["action"] == "CLOSE"
                if accepted:
                    audit = audit_verdict(
                        shadow_mode,
                        "CLOSE" if is_close else eve_action,
                        position_direction=position_direction,
                    )
                    outcome["audit"] = audit
                    if audit["verdict"] == "block":
                        outcome["decided_by"] = "audit"
                        outcome["status"] = "blocked_by_audit"
                        outcome["executed"] = False
                        if not is_close:
                            try:
                                outcome["shadow_id"] = shadow(
                                    session, proposal, f"audit:{audit['reason']}", dossier_id, "audit"
                                )
                            except Exception:  # a counterfactual must never break Ève's cycle
                                logger.exception("audit block shadow failed for %s", proposal.get("portfolio_code"))
                        outcomes.append(outcome)
                        continue
                    outcome["decided_by"] = "eve"
                    override = "CLOSE" if is_close else eve_action
                else:
                    outcome["status"] = "kept_by_eve" if is_close else "refused_by_eve"
                    outcome["executed"] = False
                    if not is_close and proposal.get("engine_signal", True):
                        try:
                            outcome["shadow_id"] = shadow(session, proposal, eve_action, dossier_id)
                        except Exception:  # a counterfactual must never break Ève's cycle
                            logger.exception("refusal shadow failed for %s", proposal.get("portfolio_code"))
                    outcomes.append(outcome)
                    continue
                res = submit(
                    session,
                    dossier_id,
                    portfolio_code=proposal["portfolio_code"],
                    price=proposal.get("price"),
                    stop_distance=proposal.get("stop_distance"),
                    execute=True,
                    action_override=override,
                    decided_by=outcome["decided_by"],
                )
                outcome["status"] = res.get("status")
                outcome["executed"] = bool(res.get("executed"))
                outcome["risk_authorization"] = res.get("risk_authorization")
                outcome["position_id"] = res.get("position_id")
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
