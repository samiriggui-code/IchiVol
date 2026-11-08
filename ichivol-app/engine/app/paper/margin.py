"""Pouvoir d'achat du compte paper sur marge (2026-11-08).

Un profil avec ``margin`` peut engager plus que sa caisse : le lot débite toujours son notionnel, la caisse peut donc
passer sous zéro (l'emprunt de marge) et toutes les formules existantes restent justes (équité = caisse + notionnels
réservés, clôture = rend le produit). Deux poches séparées : la crypto reste au comptant (1× par défaut, pas de
financement simulé), les CFD et futures vont jusqu'à ``other_max_exposure`` fois l'équité. Sans ``margin`` : la caisse.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.paper.strategy_profiles import _is_spot_crypto


def buying_power(
    profile: Mapping[str, Any] | None,
    symbol: str,
    *,
    cash: float,
    equity: float,
    open_lots: Iterable[Any],
) -> float:
    """Montant qu'un nouveau lot sur ``symbol`` peut encore engager (frais compris)."""
    margin = (profile or {}).get("margin")
    if not margin:
        return cash
    crypto = _is_spot_crypto(symbol)
    multiple = float(margin.get("crypto_max_exposure" if crypto else "other_max_exposure", 1.0))
    used = sum(
        float(getattr(lot, "notional", 0.0) or 0.0)
        for lot in open_lots
        if _is_spot_crypto(str(getattr(lot, "symbol", ""))) == crypto
    )
    return max(0.0, equity * multiple - used)
