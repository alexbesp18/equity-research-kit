"""Paced, labeled deep-fundamentals pull via yfinance.

Generalized from a long-running private research workflow.
- Sequential with backoff: parallel yfinance calls can rate-limit hard.
- Research sweep semantics: a single ticker that fails is logged + recorded with a
  FAIL status and the loop CONTINUES (so one bad symbol never kills a 30-name run).
  Per-FIELD failures (e.g. statements) are caught and noted, not fatal. This is an
  intentional, documented exception to fail-loud for a multi-symbol research sweep; the
  caller inspects `status` / the returned `fails` list rather than getting an exit code.

Returns {ticker: record}. Each record carries labeled metrics + a `status` field.
"""

from __future__ import annotations

import math
import sys
import time

import yfinance as yf


def _num(x):
    try:
        if x is None:
            return None
        if hasattr(x, "item"):  # numpy scalar (np.bool_/np.int64/np.float64) -> python scalar
            x = x.item()
        if isinstance(x, bool):
            return None  # reject bool: float(True)==1.0 would silently fabricate a value
        f = float(x)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _retry(fn, tries: int = 3, base: float = 1.2):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - research sweep: backoff+retry, then give up on this field
            last = e
            time.sleep(base * (i + 1))
    raise last


def revenue_cagr(series) -> float | None:
    """CAGR % between the newest and oldest non-NaN annual revenue (yfinance is most-recent-first).

    The exponent uses the actual calendar span between the surviving endpoints (from the date
    index) when available, so an interior/newest NaN year doesn't silently shrink the window and
    overstate the rate; falls back to the surviving-period count otherwise.
    """
    try:
        s = series.dropna()
        if len(s) < 2:
            return None
        # cast to python float so a huge ratio raises OverflowError (caught -> None) instead
        # of a numpy RuntimeWarning + inf; non-finite endpoints fall through to _num -> None.
        newest, oldest = float(s.iloc[0]), float(s.iloc[-1])
        if oldest <= 0 or newest <= 0:
            return None
        try:
            years = abs((s.index[0] - s.index[-1]).days) / 365.25
        except Exception:  # noqa: BLE001 - index isn't datetime
            # without a date span we can't tell the true span once NaNs were dropped, so
            # don't risk OVERSTATING the rate from a shrunk count — only trust count if nothing
            # was dropped.
            if len(s) < len(series):
                return None
            years = len(s) - 1
        # reject implausibly short spans: a <~1y gap (fiscal-year-end change, or a TTM/stub
        # column mixed with annuals) makes 1/years explode into an absurd-but-FINITE rate that
        # escapes the nan/inf blank and renders on the decision surface.
        if years < 0.75:
            return None
        # _num the result so an overflow/NaN becomes None like every sibling metric
        return _num((((newest / oldest) ** (1 / years)) - 1) * 100)
    except Exception:  # noqa: BLE001
        return None


def _roic_proxy(rec: dict, tax_rate: float = 0.21) -> float | None:
    """EBIT*(1-tax_rate) / (total_debt + book_equity - cash). Rough proxy.

    tax_rate defaults to the US 0.21; pass a jurisdiction rate for foreign-heavy themes.
    """
    ebit = rec.get("ebit_latest")
    td = rec.get("total_debt")
    tc = rec.get("total_cash")
    mktcap = rec.get("mktcap")
    pb = rec.get("pb")
    # reject pb<=0 / mktcap<=0: a negative priceToBook (negative book equity) would yield a
    # plausible-looking but meaningless ROIC.
    if (
        ebit is None  # a genuine EBIT==0 is valid (ROIC ~0), not "missing"
        or td is None
        or tc is None
        or not mktcap
        or not pb
        or pb <= 0
        or mktcap <= 0
    ):
        return None
    book_equity = mktcap / pb
    invested = td + book_equity - tc
    if invested <= 0:
        return None
    return _num(ebit * (1 - tax_rate) / invested * 100)


_INFO_FIELDS = {
    "name": ("longName", "shortName"),
    "currency": ("currency",),
    "mktcap": ("marketCap",),
    "ev": ("enterpriseValue",),
    "trailing_pe": ("trailingPE",),
    "forward_pe": ("forwardPE",),
    "peg": ("pegRatio", "trailingPegRatio"),
    "pb": ("priceToBook",),
    "ev_ebitda": ("enterpriseToEbitda",),
    "ev_rev": ("enterpriseToRevenue",),
    "beta": ("beta",),
    "hi52": ("fiftyTwoWeekHigh",),
    "lo52": ("fiftyTwoWeekLow",),
    "d50": ("fiftyDayAverage",),
    "d200": ("twoHundredDayAverage",),
    "rev_growth_yoy": ("revenueGrowth",),
    "earnings_growth_yoy": ("earningsGrowth",),
    "gross_margin": ("grossMargins",),
    "op_margin": ("operatingMargins",),
    "ebitda_margin": ("ebitdaMargins",),
    "profit_margin": ("profitMargins",),
    "fcf": ("freeCashflow",),
    "ocf": ("operatingCashflow",),
    "total_cash": ("totalCash",),
    "total_debt": ("totalDebt",),
    "total_revenue": ("totalRevenue",),
    "ebitda": ("ebitda",),
    "roe": ("returnOnEquity",),
    "roa": ("returnOnAssets",),
    "current_ratio": ("currentRatio",),
    "div_yield": ("dividendYield",),
    "rec_key": ("recommendationKey",),
    "rec_mean": ("recommendationMean",),
    "n_analysts": ("numberOfAnalystOpinions",),
    "pt_mean": ("targetMeanPrice",),
    "pt_median": ("targetMedianPrice",),
    "pt_high": ("targetHighPrice",),
    "pt_low": ("targetLowPrice",),
}
# fields that are raw passthrough (strings/ints), not coerced to float
_RAW = {"name", "currency", "rec_key", "n_analysts"}


def _price(g) -> float | None:
    # coerce FIRST (so a NaN/inf source -> None and we fall through to the next feed),
    # then accept the coerced value if present (a legit 0.0 still counts, NaN does not).
    for k in ("currentPrice", "regularMarketPrice", "previousClose"):
        v = _num(g(k))
        if v is not None:
            return v
    return None


def pull_one(ticker: str, ticker_obj=None) -> dict:
    """Pull one ticker. Never raises; returns a record with `status` (ok|no_info|FAIL:...)."""
    rec: dict = {"ticker": ticker, "status": "ok"}
    try:
        t = ticker_obj or yf.Ticker(ticker)
        info = _retry(lambda: t.info) or {}
        g = info.get
        if _price(g) is None:
            rec["status"] = "no_info"
        for key, srcs in _INFO_FIELDS.items():
            val = next((g(s) for s in srcs if g(s) is not None), None)
            rec[key] = val if key in _RAW else _num(val)
        rec["price"] = _price(g)
        rec["prev_close"] = _num(g("previousClose"))
        if rec.get("total_debt") is not None and rec.get("total_cash") is not None:
            rec["net_debt"] = rec["total_debt"] - rec["total_cash"]
        # statements (per-field guarded)
        try:
            fin = _retry(lambda: t.financials)
            if fin is not None and not fin.empty:
                if "Total Revenue" in fin.index:
                    # Legacy key name kept for downstream consumers; the actual CAGR span is
                    # whatever date/count span survives yfinance NaNs, not necessarily 3 years.
                    rec["rev_cagr_3y"] = revenue_cagr(fin.loc["Total Revenue"])
                # NB: do NOT dropna before positional indexing — yfinance columns are
                # most-recent-first, and a NaN newest column would shift iloc[0] to the
                # PRIOR year and mislabel it "latest". Take iloc[0]/iloc[1] of the aligned
                # ratio (NaN -> None via _num) so the labels track the real fiscal columns.
                ncols = fin.shape[1]
                if "Gross Profit" in fin.index and "Total Revenue" in fin.index and ncols >= 2:
                    gm = fin.loc["Gross Profit"] / fin.loc["Total Revenue"]
                    rec["gm_latest"], rec["gm_prior"] = (
                        _num(gm.iloc[0] * 100),
                        _num(gm.iloc[1] * 100),
                    )
                if "Operating Income" in fin.index and "Total Revenue" in fin.index and ncols >= 2:
                    om = fin.loc["Operating Income"] / fin.loc["Total Revenue"]
                    rec["om_latest"], rec["om_prior"] = (
                        _num(om.iloc[0] * 100),
                        _num(om.iloc[1] * 100),
                    )
                if "Operating Income" in fin.index and ncols >= 1:
                    rec["ebit_latest"] = _num(fin.loc["Operating Income"].iloc[0])
        except Exception as e:  # noqa: BLE001
            rec["fin_note"] = f"statements:{type(e).__name__}"
        rec["roic_proxy"] = _roic_proxy(rec)
        # earnings date
        try:
            cal = _retry(lambda: t.calendar)
            ed = None
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
            elif isinstance(cal, list | tuple):
                ed = cal
            elif cal is not None and hasattr(cal, "loc"):
                try:
                    ed = cal.loc["Earnings Date"].tolist()
                except Exception:  # noqa: BLE001
                    ed = None
            rec["earnings_date"] = str(ed) if ed else None
        except Exception:  # noqa: BLE001
            rec["earnings_date"] = None
    except Exception as e:  # noqa: BLE001 - record the failure, keep going
        rec["status"] = f"FAIL:{type(e).__name__}:{e}"
        sys.stderr.write(f"[fundamentals] FAIL {ticker}: {e}\n")
    return rec


def pull_many(tickers, sleep: float = 1.0, log=None) -> dict:
    """Pull a list of tickers sequentially with pacing. Returns {ticker: record}.

    `log`: optional callable(str) for progress. Never raises; inspect each record's status.
    """
    out: dict = {}
    for tk in tickers:
        rec = pull_one(tk)
        out[tk] = rec
        if log:
            log(f"{tk}: {rec['status']} px={rec.get('price')} revG={rec.get('rev_growth_yoy')}")
        time.sleep(sleep)
    return out


def summary(records: dict) -> dict:
    ok = [t for t, r in records.items() if r.get("status") == "ok"]
    fails = [t for t, r in records.items() if str(r.get("status", "")).startswith("FAIL")]
    ok_records = [r for r in records.values() if r.get("status") == "ok"]
    field_counts: dict[str, int] = {}
    for rec in ok_records:
        for key, value in rec.items():
            if key == "status":
                continue
            if value is not None and value != "":
                field_counts[key] = field_counts.get(key, 0) + 1
    return {"ok": len(ok), "total": len(records), "fails": fails, "field_counts": field_counts}
