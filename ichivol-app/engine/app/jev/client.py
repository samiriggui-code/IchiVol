"""JEV client — one typed call to ``POST <base>/v1/systemone``.

Same wire format for the three ways to reach JEV:

- TypeSafe (official): ``JEV_URL=https://api.typesafe.ai``, ``JEV_MODEL=jev-latest``
- OpenRouter: ``JEV_URL=https://openrouter.ai/api``, ``JEV_MODEL=~typesafe/jev-latest``
- jevos-v4 (local CPU server, github.com/feder-cr/jev): ``http://jevos-v4:8017``

``JEV_FALLBACK_URL`` (default jevos-v4) is tried when the primary fails. Answers are validated against the
System One contract (noul in [0,1]; choice + probabilities + confidence; score + probabilities + confidence);
anything else is an error, never a default value.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

SYSTEM_ONE_PATH = "/v1/systemone"
DEFAULT_URL = "https://api.typesafe.ai"
DEFAULT_FALLBACK_URL = "http://jevos-v4:8017"
DEFAULT_MODEL = "jev-latest"


@dataclass(frozen=True)
class JevEndpoint:
    name: str  # "primary" | "fallback"
    url: str
    api_key: str
    model: str
    timeout_s: float

    @property
    def label(self) -> str:
        if "typesafe.ai" in self.url:
            return "typesafe"
        if "openrouter.ai" in self.url:
            return "openrouter"
        if "jevos" in self.url or ":8017" in self.url:
            return "jevos"
        return "custom"


@dataclass
class JevCall:
    ok: bool
    answers: dict[str, dict[str, Any]] = field(default_factory=dict)
    model: str | None = None
    provider: str | None = None
    usage: dict[str, Any] | None = None
    latency_ms: float | None = None
    error: str | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "answers": self.answers,
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "errors": self.errors,
        }


def endpoints_from_env() -> list[JevEndpoint]:
    timeout = float(os.getenv("JEV_TIMEOUT_S", "8") or 8)
    out: list[JevEndpoint] = []
    primary = (os.getenv("JEV_URL") or DEFAULT_URL).strip().rstrip("/")
    key = (os.getenv("JEV_API_KEY") or "").strip()
    # A hosted provider without a key would only produce 401s; jevos accepts calls without one.
    if primary and (key or "typesafe.ai" not in primary and "openrouter.ai" not in primary):
        out.append(JevEndpoint("primary", primary, key, (os.getenv("JEV_MODEL") or DEFAULT_MODEL).strip(), timeout))
    fallback = (os.getenv("JEV_FALLBACK_URL", DEFAULT_FALLBACK_URL) or "").strip().rstrip("/")
    if fallback and fallback != primary:
        out.append(
            JevEndpoint(
                "fallback",
                fallback,
                (os.getenv("JEV_FALLBACK_API_KEY") or "").strip(),
                (os.getenv("JEV_FALLBACK_MODEL") or DEFAULT_MODEL).strip(),
                # jevos-v4 runs on the VPS CPU: slower than the hosted model.
                float(os.getenv("JEV_FALLBACK_TIMEOUT_S", "60") or 60),
            )
        )
    return out


def endpoints_for(source: str) -> list[JevEndpoint]:
    """Endpoints for one Ève account: ``jev`` = hosted primary then jevos fallback; ``jevos`` = local only."""
    eps = endpoints_from_env()
    if source == "jevos":
        local = [ep for ep in eps if ep.label == "jevos"]
        return [JevEndpoint("primary", ep.url, ep.api_key, ep.model, ep.timeout_s) for ep in local[:1]]
    return eps


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def validate_answer(name: str, question: dict[str, Any], answer: Any) -> str | None:
    """Return an error code when ``answer`` breaks the System One contract for ``question``."""
    qtype = question.get("type")
    if not isinstance(answer, dict) or answer.get("type") != qtype:
        return f"{name}:type"
    if qtype == "noul":
        v = answer.get("noul")
        return None if _num(v) and 0.0 <= v <= 1.0 else f"{name}:noul"
    probs = answer.get("probabilities")
    if not isinstance(probs, dict) or not probs or not all(_num(p) for p in probs.values()):
        return f"{name}:probabilities"
    if not _num(answer.get("confidence")):
        return f"{name}:confidence"
    if qtype == "choice":
        labels = set((question.get("criteria") or {}).keys())
        if answer.get("choice") not in labels:
            return f"{name}:choice"
        return None
    if qtype == "score":
        n = len(question.get("criteria") or [])
        s = answer.get("score")
        return None if _num(s) and -1e-6 <= s <= n - 1 + 1e-6 else f"{name}:score"
    return f"{name}:unknown_type"


def _post(ep: JevEndpoint, state: Any, questions: dict[str, Any], client: httpx.Client | None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if ep.api_key:
        headers["Authorization"] = "Bearer " + ep.api_key
    body = {"model": ep.model, "state": state, "questions": questions}
    if client is not None:
        resp = client.post(ep.url + SYSTEM_ONE_PATH, json=body, headers=headers, timeout=ep.timeout_s)
    else:
        with httpx.Client(timeout=ep.timeout_s) as c:
            resp = c.post(ep.url + SYSTEM_ONE_PATH, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("response_not_object")
    return data


def system_one(
    state: Any,
    questions: dict[str, dict[str, Any]],
    *,
    endpoints: list[JevEndpoint] | None = None,
    client: httpx.Client | None = None,
) -> JevCall:
    """Ask every question about ``state`` in one call; primary then fallback. Never raises."""
    eps = endpoints if endpoints is not None else endpoints_from_env()
    if not eps:
        return JevCall(ok=False, error="jev_not_configured")
    errors: list[str] = []
    for ep in eps:
        started = time.monotonic()
        try:
            data = _post(ep, state, questions, client)
        except httpx.HTTPStatusError as exc:
            errors.append(f"{ep.label}:http_{exc.response.status_code}")
            continue
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"{ep.label}:{type(exc).__name__}")
            continue
        latency = round((time.monotonic() - started) * 1000, 1)
        raw = data.get("answers") if isinstance(data.get("answers"), dict) else {}
        answers: dict[str, dict[str, Any]] = {}
        bad: list[str] = []
        for name, q in questions.items():
            err = validate_answer(name, q, raw.get(name))
            if err:
                bad.append(err)
            else:
                answers[name] = raw[name]
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return JevCall(
            ok=not bad,
            answers=answers,
            model=str(data.get("model")) if data.get("model") is not None else None,
            provider=ep.label,
            usage=usage,
            latency_ms=latency,
            error="invalid_answers" if bad else None,
            errors=errors + bad,
        )
    return JevCall(ok=False, error="jev_unavailable", errors=errors)


def evaluate(state: Any, questions: dict) -> dict:
    """Legacy shape kept for app.jev.shadow callers: ``{ok, result|error}``."""
    call = system_one(state, questions)
    if call.answers:
        return {"ok": call.ok, "result": {"answers": call.answers, "model": call.model, "usage": call.usage},
                "provider": call.provider, "errors": call.errors}
    return {"ok": False, "error": call.error, "errors": call.errors}
