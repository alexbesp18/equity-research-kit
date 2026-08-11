#!/usr/bin/env python3
"""No-network end-to-end synthetic coverage-book fixture builder."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from er_kit.cleanopen import clean_open  # noqa: E402
from er_kit.corrections import resolve_verdict  # noqa: E402
from er_kit.coveragebook import CoverageBook, compute_upside  # noqa: E402
from er_kit.universe import make_record, merge  # noqa: E402

# The tracked fixture is intentionally fictional and can be regenerated deterministically.
DEFAULT_OUT = ROOT / "samples" / "synthetic_coverage_book.xlsx"


def _records() -> list[dict]:
    universe = [
        make_record("ALFA", "Alpha Example Corp.", "Synthetic components", tab="pure"),
        make_record(
            "BETA",
            "Beta Example Ltd.",
            "Synthetic infrastructure",
            tab="tangential",
            fund_currency="JPY",
        ),
    ]
    fundamentals = {
        "ALFA": {
            "price": 100.00,
            "pt_mean": 112.00,
            "mktcap": 12.5e9,
            "currency": "USD",
        },
        "BETA": {
            "price": 2500.0,
            "pt_mean": 2650.0,
            "mktcap": 800e9,
            "currency": "JPY",
        },
    }
    dossiers = {
        "ALFA": {
            "refreshed_verdict": "buy_laggard",
            "laggard": "laggard",
            "note": "Fictional example used only to exercise the renderer and QA checks.",
        },
        "BETA": {
            "corrected_verdict": "hold",
            "laggard": "fair",
            "note": "Fictional non-USD row proves neutral money formats avoid false dollar marks.",
        },
    }
    merged = merge(universe, fundamentals=fundamentals, dossiers=dossiers)
    rows = []
    for rec in merged.values():
        fund = rec["fund"]
        dossier = rec["dossier"] or {}
        rows.append(
            {
                "_currency": rec["fund_currency"],
                "ticker": rec["ticker"],
                "name": rec["name"],
                "verdict": resolve_verdict(
                    dossier.get("refreshed_verdict"),
                    dossier.get("corrected_verdict"),
                    "watch",
                ),
                "laggard": dossier.get("laggard"),
                "price": fund.get("price"),
                "mktcap": fund.get("mktcap"),
                "upside": compute_upside(rec),
                "note": dossier.get("note"),
            }
        )
    return rows


def build_example(out_path: str | Path = DEFAULT_OUT) -> tuple[Path, bool, str]:
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = _records()
    cb = CoverageBook(str(out))
    decision = cb.add_sheet("Decision", "0B3D2E")
    columns = [
        {"key": "ticker", "header": "Ticker", "width": 10, "type": "boldc"},
        {"key": "name", "header": "Name", "width": 20, "type": "text"},
        {"key": "verdict", "header": "Verdict", "width": 14, "type": "verdict"},
        {"key": "laggard", "header": "Laggard", "width": 12, "type": "laggard"},
        {"key": "price", "header": "Price", "width": 12, "type": "money"},
        {"key": "mktcap", "header": "Mkt cap", "width": 12, "type": "mcap"},
        {"key": "upside", "header": "Upside", "width": 10, "type": "upside"},
        {"key": "note", "header": "Note", "width": 48, "type": "text", "max": 160},
    ]
    start = cb.header_block(
        decision,
        3,
        "Synthetic Coverage Example",
        "Self-contained demo: make_record -> merge -> CoverageBook -> clean_open",
        banner="Fictional USD and JPY records; no network calls are made.",
    )
    cb.table(decision, columns, rows, start_row=start, freeze=(start + 1, 2))

    legend = cb.add_sheet("Legend", "57606A")
    start = cb.header_block(legend, 1, "Legend")
    cb.kv_rows(
        legend,
        [
            ("verdict", "Enum/synonym-safe verdict output after resolve_verdict."),
            ("laggard", "Laggard bucket rendered with the shared coverage-book palette."),
            ("upside", "Same-currency target upside from compute_upside."),
            ("money/mcap", "USD renders with $, non-USD renders as neutral numeric format."),
        ],
        start_row=start,
    )
    cb.close()
    ok, msg = clean_open(str(out))
    return out, ok, msg


def main() -> int:
    out, ok, msg = build_example()
    print(f"wrote {out}")
    print(f"clean_open: {msg}")
    if ok or msg.startswith("environment/automation failure:"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
