"""Universe data structures + merge helpers for a coverage book.

A "universe" is a list of ticker records, each classified into a `tab`
(pure | tangential | footnote) and a `sub_vertical`. This module holds the shape and
merges supplied data and research layers into one record per ticker.
"""

from __future__ import annotations

import copy

TABS = ("pure", "tangential", "footnote")


def make_record(
    ticker: str,
    name: str,
    sub_vertical: str,
    tab: str = "pure",
    tradeable: str = "",
    options_note: str = "",
    fund_currency: str = "USD",
    prior: dict | None = None,
) -> dict:
    """A single universe row before live data / dossiers are merged in."""
    if tab not in TABS:
        raise ValueError(f"tab must be one of {TABS}, got {tab!r}")
    return {
        "ticker": ticker,
        "name": name,
        "sub_vertical": sub_vertical,
        "tab": tab,
        "tradeable": tradeable,
        "options_note": options_note,
        "fund_currency": fund_currency,
        "prior": prior or {},
        "fund": {},
        "tech": None,
        "foreign": None,
        "dossier": None,
    }


def merge(
    universe: list[dict],
    fundamentals: dict | None = None,
    technicals: dict | None = None,
    foreign: dict | None = None,
    dossiers: dict | None = None,
) -> dict:
    """Merge the layers keyed by ticker. Returns {ticker: record}.

    Each layer is {ticker: data}; missing entries are left as the record's default.
    """
    seen: set = set()
    out: dict = {}
    for rec in universe:
        tk = rec["ticker"]
        # fail loud on a duplicate ticker (one name in two sub-verticals) — silent last-wins
        # would drop a record (matches technicals.load's duplicate-header guard).
        if tk in seen:
            raise ValueError(f"duplicate ticker in universe: {tk!r} (tickers must be unique)")
        seen.add(tk)
        r = copy.deepcopy(rec)
        if fundamentals and tk in fundamentals:
            r["fund"] = copy.deepcopy(fundamentals[tk])
            if r["fund"].get("currency"):
                r["fund_currency"] = r["fund"]["currency"]
        if technicals and tk in technicals:
            r["tech"] = copy.deepcopy(technicals[tk])
        if foreign and tk in foreign:
            r["foreign"] = copy.deepcopy(foreign[tk])
        if dossiers and tk in dossiers:
            r["dossier"] = copy.deepcopy(dossiers[tk])
        out[tk] = r
    return out


def by_subvertical(merged: dict) -> dict:
    """Group merged records by sub_vertical -> [tickers]."""
    groups: dict = {}
    for tk, r in merged.items():
        groups.setdefault(r["sub_vertical"], []).append(tk)
    return groups
