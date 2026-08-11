"""Clean-open xlsx coverage-book builder (xlsxwriter).

The KIT owns the *rendering conventions* (format palette, clean-open safety, a flexible
table renderer with conditional fills for verdict / laggard / upside); the SKILL owns the
*content wiring* (which tabs, which columns, which records).

Clean-open pattern (memory: pattern_excel_clean_xlsx): xlsxwriter not openpyxl,
`nan_inf_to_errors`, NO single-cell merges, no conditional-format dxf. Verify with
er_kit.cleanopen.clean_open after building.
"""

from __future__ import annotations

import datetime as _dt
import math
import numbers
from dataclasses import dataclass

import xlsxwriter

from .corrections import sanitize_laggard, sanitize_verdict, upside_pct
from .visual_style import COLORS, LAGGARD_BG, VERDICT_BG, coverage_format_specs, fmt_spec

_NUMERIC_TYPES = {"num", "num1", "pct", "money", "mcap", "upside"}


@dataclass
class _PendingHeader:
    ws: object
    ncols: int
    rows: list[tuple[str, str, int | None]]


class CoverageBook:
    """A workbook with shared clean-open formats + a flexible table renderer."""

    def __init__(self, out_path: str):
        self.path = out_path
        self.wb = xlsxwriter.Workbook(out_path, {"nan_inf_to_errors": True})
        self._used_sheets: set[str] = set()
        self._pending_headers: dict[int, _PendingHeader] = {}
        # THREE trailing commas in mcap/mcapj = divide raw currency units by 1e9 for a "B"
        # label. Two commas silently rendered a $27B cap as "$27,227B".
        self.f = {key: self._fmt(spec) for key, spec in coverage_format_specs().items()}

    def _fmt(self, d):
        return self.wb.add_format(d)

    def _flush_header(self, ws, ncols: int | None = None) -> None:
        pending = self._pending_headers.pop(id(ws), None)
        if not pending:
            return
        width = max(ncols if ncols is not None else pending.ncols, 1)
        end = width - 1
        for r, value, fmt_key, height in pending.rows:
            if end == 0:
                ws.write(r, 0, value, self.f[fmt_key])
            else:
                ws.merge_range(r, 0, r, end, value, self.f[fmt_key])
            if height is not None:
                ws.set_row(r, height)

    @staticmethod
    def _date_text(value) -> str | None:
        if isinstance(value, _dt.date):  # covers datetime.datetime too (subclass)
            return value.strftime("%Y-%m-%d")
        # numpy.datetime64 is intentionally handled without importing numpy here; pandas/yfinance
        # bring numpy transitively, but the renderer should not require it at import time.
        if type(value).__module__.startswith("numpy") and type(value).__name__ == "datetime64":
            text = str(value)
            if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
                return text[:10]
        return None

    @staticmethod
    def _currency(rec: dict) -> str | None:
        fund = rec.get("fund")
        nested_present = isinstance(fund, dict) and "currency" in fund
        has_currency_field = "_currency" in rec or "fund_currency" in rec or nested_present
        if not has_currency_field:
            return None
        cur = rec.get("_currency") or rec.get("fund_currency")
        if not cur and nested_present:
            cur = fund.get("currency")
        return cur or "USD"

    def verdict_fmt(self, v):
        return self._fmt(
            fmt_spec(
                bg_color=VERDICT_BG.get(v, COLORS["muted"]),
                font_color=COLORS["white"],
                bold=True,
                align="center",
            )
        )

    def laggard_fmt(self, lag):
        return self._fmt(fmt_spec(bg_color=LAGGARD_BG.get(lag, COLORS["white"]), align="center"))

    def upside_fmt(self, u):
        # tolerate None / non-numeric / NaN without aborting the whole render. numbers.Real
        # (not int|float) so a numpy.int64 upside still gets the colored band.
        if not isinstance(u, numbers.Real) or isinstance(u, bool) or u != u:
            return self.f["num1"]
        bg = (
            COLORS["positive_fill"]
            if u >= 12
            else (COLORS["neutral_fill"] if u >= 0 else COLORS["negative_fill"])
        )
        return self._fmt(fmt_spec(num_format='0.0"%"', align="right", bg_color=bg))

    def add_sheet(self, name: str, tab_color: str | None = None):
        # Excel forbids these chars in sheet names; LLM-generated sub-vertical names may carry
        # them (the SKILL builds tab names), so sanitize defensively before xlsxwriter sees them.
        safe = str(name)
        for ch in r"[]:*?/\\":
            safe = safe.replace(ch, "-")
        safe = "".join(c for c in safe if ord(c) >= 32)  # drop control chars
        safe = safe.strip().strip("'").strip()[:31]  # Excel forbids leading/trailing apostrophe
        if not safe:
            safe = "Sheet"  # never pass an empty name (xlsxwriter would silently rename to Sheet1)
        # de-dup after truncation (long-named themes can collide on the first 31 chars,
        # which would otherwise crash the whole build with DuplicateWorksheetName)
        base, i = safe, 2
        while safe.lower() in self._used_sheets:
            suf = f"~{i}"
            safe = base[: 31 - len(suf)] + suf
            i += 1
        self._used_sheets.add(safe.lower())
        ws = self.wb.add_worksheet(safe)
        ws.hide_gridlines(2)
        if tab_color:
            ws.set_tab_color(tab_color)
        return ws

    def header_block(
        self, ws, ncols: int, title: str, subtitle: str = "", note: str = "", banner: str = ""
    ) -> int:
        """Stage title/subtitle/note/banner rows. Returns next free row.

        The staged header is flushed by the following table/kv renderer using that renderer's
        actual column count, so a stale caller-provided ncols cannot narrow the title band.
        close() flushes staged headers that were not followed by a renderer.
        """
        r = 0
        rows = [(r, title, "title", None)]
        r += 1
        if subtitle:
            rows.append((r, subtitle, "sub", None))
            r += 1
        if note:
            rows.append((r, note, "note", None))
            r += 1
        if banner:
            rows.append((r, banner, "banner", 56))
            r += 1
        self._pending_headers[id(ws)] = _PendingHeader(ws=ws, ncols=ncols, rows=rows)
        return r

    def _cell_value_fmt(self, spec: dict, rec: dict):
        """Resolve (value, format) for one cell from a column spec + a record."""
        key, typ = spec["key"], spec.get("type", "text")
        val = rec.get(key)
        # a date/datetime in a text cell would store as a raw Excel serial (46190.66) — render
        # it as an ISO string so the decision surface shows a real date, not a float.
        date_text = self._date_text(val)
        if date_text is not None:
            val = date_text
        # EXHAUSTIVE fallback (not a whitelist): anything that isn't None/str/real-number —
        # dict/list/bytes/numpy.ndarray/numpy.datetime64/complex/range/custom — is coerced to
        # text, so a leaked value degrades gracefully instead of a TypeError that kills the
        # whole build at write()/close() and silently defeats the clean-open gate.
        elif val is not None and not isinstance(val, (str, numbers.Real)):
            val = str(val)
        # a non-finite real renders as a literal #NUM!/=1/0 via nan_inf_to_errors -> blank it
        # for ANY cell type (e.g. n_analysts is often NaN and rendered as center/text).
        if isinstance(val, numbers.Real) and not isinstance(val, bool) and not math.isfinite(val):
            val = None
        # a numeric-typed cell must hold a real number or be blank — a bool / numpy.bool_ / a
        # leftover string would otherwise render as 1 / True / raw text in a $/% column.
        if typ in _NUMERIC_TYPES and not (
            isinstance(val, numbers.Real) and not isinstance(val, bool)
        ):
            val = None
        # currency: renderer key (_currency) -> producer key (fund_currency, set by
        # universe.merge) -> nested fund.currency. If no currency field exists at all, use a
        # neutral no-symbol format rather than inventing a false USD marker.
        cur = self._currency(rec)
        usd = cur == "USD"
        if typ == "verdict":
            v = sanitize_verdict(val)  # single source of truth; strips stray whitespace
            return v, self.verdict_fmt(v)
        if typ == "laggard":
            lag = sanitize_laggard(val)  # strip+clamp, mirroring verdict (one source of truth)
            return lag, self.laggard_fmt(lag)
        if typ == "upside":
            u = val if isinstance(val, numbers.Real) and not isinstance(val, bool) else None
            return u, self.upside_fmt(u)
        if typ == "money":
            return val, (self.f["money"] if usd else self.f["num"])
        if typ == "mcap":
            return val, (self.f["mcap"] if usd else self.f["mcapj"])
        if typ in ("num", "num1", "pct"):
            return val, self.f[typ]
        if typ == "boldc":
            return val, self.f["boldc"]
        if typ == "center":
            return val, self.f["cellc"]
        # text (truncate long)
        if isinstance(val, str) and spec.get("max"):
            val = val[: spec["max"]]
        return ("" if val is None else val), self.f["cell"]

    def table(
        self,
        ws,
        col_specs: list[dict],
        records: list[dict],
        start_row: int = 0,
        freeze: tuple[int, int] | None = None,
        autofilter: bool = True,
    ):
        """Render a table. col_specs: [{key, header, width, type, max?}]. records: list of dicts.

        Recognized types: text|center|boldc|num|num1|pct|money|mcap|verdict|laggard|upside.
        Put the record's price currency in rec['_currency'] so money/mcap pick $ vs plain.
        """
        if not col_specs:
            return start_row  # nothing to render; avoid col -1 set_column/autofilter warnings
        self._flush_header(ws, len(col_specs))
        for i, c in enumerate(col_specs):
            ws.set_column(i, i, c.get("width", 12))
        ws.write_row(start_row, 0, [c["header"] for c in col_specs], self.f["hdr"])
        rr = start_row + 1
        for rec in records:
            row = (
                rec if isinstance(rec, dict) else {}
            )  # a non-dict record -> blank row, never a crash
            for ci, spec in enumerate(col_specs):
                val, fmt = self._cell_value_fmt(spec, row)
                ws.write(rr, ci, val if val is not None else "", fmt)
            rr += 1
        if freeze:
            ws.freeze_panes(*freeze)
        if autofilter and rr > start_row + 1:
            ws.autofilter(start_row, 0, rr - 1, len(col_specs) - 1)
        return rr

    def kv_rows(self, ws, pairs, start_row: int = 0, key_w: int = 22, val_w: int = 110):
        """Write [(key, value)] rows for legend/notes-style tabs."""
        self._flush_header(ws, 2)
        ws.set_column(0, 0, key_w)
        ws.set_column(1, 1, val_w)
        r = start_row
        for k, v in pairs:
            ws.write(r, 0, k, self.f["cellc"])
            ws.write(r, 1, str(v), self.f["cell"])
            r += 1
        return r

    def close(self):
        for pending in list(self._pending_headers.values()):
            self._flush_header(pending.ws)
        self.wb.close()
        return self.path


def compute_upside(rec: dict) -> float | None:
    """Currency-safe upside for a merged record: uses same-line fundamentals PT vs price."""
    fund = rec.get("fund")
    fund = fund if isinstance(fund, dict) else {}
    return upside_pct(fund.get("price"), fund.get("pt_mean"))
