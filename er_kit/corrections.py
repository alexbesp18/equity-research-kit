"""Currency-safe + adversarial-correction helpers for coverage books.

Encodes hard-won data-quality rules:
- A primary-line price target paired with an ADR price can create a false upside figure,
  so upside math must use a target quoted in the SAME listing/currency as the price.
- Some adversarial-verifier agents wrote prose into a `corrected_verdict` enum field
  -> only honor a corrected verdict if it is a clean enum.
- Critics catch fabricated/inverted analyst blocks -> provide a way to suppress them.
"""

from __future__ import annotations

import math

VALID_VERDICTS = (
    "top_pick",
    "buy_laggard",
    "quality_wait",
    "watch",
    "context",
    "pass",
)

VERDICT_ORDER = {v: i for i, v in enumerate(VALID_VERDICTS)}
VERDICT_SYNONYMS = {
    "hold": "watch",
    "avoid": "pass",
    "sell": "pass",
    "buy": "buy_laggard",
}

LAGGARD_BUCKETS = ("laggard", "fair", "leader_ran", "value_trap")


def sanitize_verdict(value: str | None, fallback: str = "watch") -> str:
    """Return value only if it is a clean verdict enum, else fallback.

    Guards against verifier agents that wrote a sentence into the verdict field.
    """
    if isinstance(value, str) and value.strip() in VALID_VERDICTS:
        return value.strip()
    return fallback


def sanitize_laggard(value: str | None) -> str:
    """Return value only if it is a clean laggard bucket (whitespace-stripped), else ''.

    Mirrors sanitize_verdict so the renderer treats the laggard enum (same loose LLM source)
    with the same strip+clamp discipline; a padded ' laggard ' must not silently blank.
    """
    return value.strip() if isinstance(value, str) and value.strip() in LAGGARD_BUCKETS else ""


def resolve_verdict(refreshed: str | None, corrected: str | None, prior: str | None) -> str:
    """Pick the verdict to show: corrected enum/synonym wins, else refreshed, else prior."""
    if isinstance(corrected, str):
        cleaned = corrected.strip()
        if cleaned in VALID_VERDICTS:
            return cleaned
        synonym = VERDICT_SYNONYMS.get(cleaned.lower())
        if synonym:
            return synonym
    if isinstance(refreshed, str) and refreshed.strip() in VALID_VERDICTS:
        return refreshed.strip()
    return sanitize_verdict(prior, "watch")


def upside_pct(price, pt) -> float | None:
    """(pt/price - 1) * 100, rounded. None unless both are positive numbers.

    CALLER CONTRACT: price and pt MUST be in the same listing/currency. Use
    `same_line_pt` to source a price target from the same data feed as the price.
    """
    # normalize numpy scalars (np.bool_/np.int64/np.float64) to python types so the bool guard fires
    price = price.item() if hasattr(price, "item") else price
    pt = pt.item() if hasattr(pt, "item") else pt
    if isinstance(price, bool) or isinstance(pt, bool):
        return None  # a bool would coerce True->1.0 and fabricate an upside
    try:
        price = float(price)
        pt = float(pt)
    except (TypeError, ValueError):
        return None
    # reject NaN/inf (yfinance targetMeanPrice is often NaN for thin coverage) so the value
    # path returns None, not a NaN that renders as a literal #NUM! on the decision surface.
    if not (math.isfinite(price) and math.isfinite(pt)):
        return None
    if price <= 0 or pt <= 0:
        return None
    result = (pt / price - 1) * 100
    return round(result, 1) if math.isfinite(result) else None  # denormal price can overflow


def same_line_pt(fund: dict, dossier_analyst: dict | None = None):
    """Return ONLY the same-feed fundamentals PT (`fund['pt_mean']`), which matches the
    price's currency, or None.

    We deliberately do NOT fall back to a dossier/agent PT: that PT may be the foreign
    primary-line target (EUR/JPY) while the price is the USD ADR — the exact currency
    mismatch that caused the +373% upside bug this kit exists to prevent. The param is kept
    for signature compatibility but ignored unless a future caller proves a matching currency.
    """
    return (fund or {}).get("pt_mean")


def suppress_analyst_block(dossier: dict) -> dict:
    """Blank a dossier's recent_actions in place (for fabricated/inverted blocks a critic flagged).

    Tolerant of a non-dict dossier / non-dict analyst (agent output is a distrusted source).
    """
    if isinstance(dossier, dict) and isinstance(dossier.get("analyst"), dict):
        dossier["analyst"]["recent_actions"] = []
    return dossier


def apply_corrections(dossiers, suppress: list[str] | None = None):
    """Apply critic corrections. Accepts EITHER a {ticker: dossier} map OR the workflow's
    native LIST of dossiers (each with a 'ticker'); mutates in place and returns it.

    `suppress`: tickers whose analyst recent_actions are known-bad and should be blanked.
    Handling both shapes avoids the silent no-op when the raw workflow list (not a keyed map)
    is passed — which would let a fabricated/inverted analyst block ship unsuppressed.
    """
    sup = set(suppress or [])
    if not sup:
        return dossiers
    if isinstance(dossiers, dict):
        for tk in sup:
            if tk in dossiers:
                suppress_analyst_block(dossiers[tk])
    elif isinstance(dossiers, list):
        for d in dossiers:
            if isinstance(d, dict) and d.get("ticker") in sup:
                suppress_analyst_block(d)
    return dossiers
