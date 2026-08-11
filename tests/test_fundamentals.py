import pandas as pd
import pytest

from er_kit import fundamentals as Fund


def test_revenue_cagr_math():
    # yfinance columns are most-recent-first: newest=133.1, oldest=100 over 3 yrs
    s = pd.Series([133.1, 121.0, 110.0, 100.0])
    assert round(Fund.revenue_cagr(s), 1) == 10.0
    assert Fund.revenue_cagr(pd.Series([100.0])) is None  # need >=2
    assert Fund.revenue_cagr(pd.Series([100.0, -5.0])) is None  # non-positive guard


def test_revenue_cagr_uses_date_span_not_count():
    idx = pd.to_datetime(["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31"])
    s = pd.Series([133.1, 121.0, 110.0, 100.0], index=idx)  # most-recent-first
    assert round(Fund.revenue_cagr(s)) == 10  # 100->133.1 over 3 calendar yrs
    # newest year NaN: window end-anchors on 2024 -> 100->121 over 2 yrs ~10%, NOT overstated
    s2 = pd.Series([float("nan"), 121.0, 110.0, 100.0], index=idx)
    assert round(Fund.revenue_cagr(s2)) == 10


def test_num_rejects_bool():
    import numpy as np

    assert Fund._num(True) is None
    assert Fund._num(False) is None
    assert Fund._num(np.bool_(True)) is None  # numpy bool too (via .item() normalization)
    assert Fund._num(np.int64(5)) == 5.0  # legit numpy number still works


def test_roic_proxy_zero_ebit_is_valid():
    # a genuine EBIT==0 should compute (ROIC ~0), not be treated as missing
    v = Fund._roic_proxy(
        {"ebit_latest": 0.0, "total_debt": 100, "total_cash": 10, "mktcap": 100, "pb": 2}
    )
    assert v == 0.0


def test_roic_proxy_rejects_negative_book_equity():
    # pb<0 (negative book equity) must not yield a plausible-looking ROIC
    assert (
        Fund._roic_proxy(
            {"ebit_latest": 100, "total_debt": 100, "total_cash": 10, "mktcap": 100, "pb": -2}
        )
        is None
    )
    # sane case still computes
    assert (
        Fund._roic_proxy(
            {"ebit_latest": 100, "total_debt": 100, "total_cash": 10, "mktcap": 100, "pb": 2}
        )
        is not None
    )


def test_revenue_cagr_nondatetime_index_with_nan_returns_none():
    # non-datetime index + a dropped NaN year -> span unknowable -> None (no overstated rate)
    s = pd.Series([121.0, float("nan"), 100.0], index=[2022, 2021, 2020])
    assert Fund.revenue_cagr(s) is None
    # non-datetime, no NaN -> count fallback is fine
    s2 = pd.Series([121.0, 110.0, 100.0], index=[2022, 2021, 2020])
    assert Fund.revenue_cagr(s2) is not None


def test_revenue_cagr_subyear_span_returns_none():
    # endpoints <1y apart (fiscal-year-end change / TTM stub) must NOT annualize into an absurd rate
    idx = pd.to_datetime(["2024-01-02", "2024-01-01"])
    assert Fund.revenue_cagr(pd.Series([105.0, 100.0], index=idx)) is None
    idx2 = pd.to_datetime(["2024-12-31", "2024-09-30"])  # adjacent quarters
    assert Fund.revenue_cagr(pd.Series([110.0, 100.0], index=idx2)) is None


def test_revenue_cagr_inf_becomes_none():
    # an overflow/non-finite result must be _num'd to None, not stored raw
    assert Fund.revenue_cagr(pd.Series([float("inf"), 100.0])) is None
    assert Fund.revenue_cagr(pd.Series([1e308, 1.0])) is None


def test_num_coercion():
    assert Fund._num("3.5") == 3.5
    assert Fund._num(None) is None
    assert Fund._num(float("nan")) is None
    assert Fund._num("abc") is None


class _FakeTicker:
    def __init__(self, info, fin=None, cal=None, raise_info=False):
        self._info, self._fin, self._cal, self._raise = info, fin, cal, raise_info

    @property
    def info(self):
        if self._raise:
            raise RuntimeError("rate limited")
        return self._info

    @property
    def financials(self):
        return self._fin

    @property
    def calendar(self):
        return self._cal


def test_pull_one_happy_path():
    info = {
        "longName": "Test Co",
        "currency": "USD",
        "currentPrice": 100.0,
        "marketCap": 1e9,
        "trailingPE": 20.0,
        "priceToBook": 4.0,
        "operatingMargins": 0.18,
        "targetMeanPrice": 120.0,
        "numberOfAnalystOpinions": 9,
        "totalDebt": 200.0,
        "totalCash": 50.0,
    }
    fin = pd.DataFrame(
        {"y3": [80.0, 30.0, 20.0], "y2": [90.0, 33.0, 22.0], "y1": [100.0, 40.0, 25.0]},
        index=["Total Revenue", "Gross Profit", "Operating Income"],
    )
    # make most-recent-first (yfinance order)
    fin = fin[["y1", "y2", "y3"]]
    rec = Fund.pull_one(
        "TEST", ticker_obj=_FakeTicker(info, fin, {"Earnings Date": ["2026-07-30"]})
    )
    assert rec["status"] == "ok"
    assert rec["price"] == 100.0
    assert rec["pt_mean"] == 120.0
    assert rec["net_debt"] == 150.0
    assert rec["n_analysts"] == 9
    assert rec["rev_cagr_3y"] is not None  # 100 vs 80 over 2 yrs
    assert rec["gm_latest"] == 40.0  # 40/100
    assert rec["roic_proxy"] is not None
    assert rec["earnings_date"] is not None


def test_pull_one_accepts_calendar_list():
    info = {"longName": "ListCal Co", "currency": "USD", "currentPrice": 100.0}
    rec = Fund.pull_one("LCAL", ticker_obj=_FakeTicker(info, cal=["2026-08-01"]))
    assert rec["status"] == "ok"
    assert rec["earnings_date"] == "['2026-08-01']"


def test_pull_one_nan_newest_year_not_mislabeled():
    # regression: if the NEWEST annual Gross Profit / Operating Income is NaN (common right
    # after fiscal year-end), the *_latest labels must be None, NOT the prior year's value.
    info = {
        "longName": "Gappy Co",
        "currency": "USD",
        "currentPrice": 50.0,
        "marketCap": 1e9,
        "priceToBook": 4.0,
        "totalDebt": 100.0,
        "totalCash": 20.0,
    }
    # columns most-recent-first (y1 newest); newest GP/OI are NaN
    fin = pd.DataFrame(
        {
            "y1": [100.0, float("nan"), float("nan")],
            "y2": [90.0, 33.0, 18.0],
            "y3": [80.0, 30.0, 16.0],
        },
        index=["Total Revenue", "Gross Profit", "Operating Income"],
    )
    rec = Fund.pull_one("GAP", ticker_obj=_FakeTicker(info, fin))
    assert rec["gm_latest"] is None  # not mislabeled as the y2 36.7%
    assert rec["gm_prior"] is not None
    assert rec["ebit_latest"] is None  # newest OI is NaN
    assert rec["roic_proxy"] is None  # no EBIT -> no proxy (not computed off a stale year)


def test_price_falls_through_nan_source_keeps_zero():
    # regression: a NaN currentPrice must fall through to the next feed, not return None;
    # a legit 0.0 must still count.
    assert Fund._price({"currentPrice": float("nan"), "regularMarketPrice": 179.0}.get) == 179.0
    assert Fund._price({"currentPrice": 0.0}.get) == 0.0
    assert Fund._price({}.get) is None


def test_pull_one_nan_price_recovers_from_next_feed():
    info = {
        "longName": "Halty Co",
        "currency": "USD",
        "currentPrice": float("nan"),
        "regularMarketPrice": 179.0,
        "previousClose": 178.0,
    }
    rec = Fund.pull_one("HALT", ticker_obj=_FakeTicker(info))
    assert rec["status"] == "ok"
    assert rec["price"] == 179.0  # not mislabeled no_info


def test_pull_one_failure_is_recorded_not_raised():
    # the fail-loud-but-continue contract: a hard failure is recorded, never raised
    rec = Fund.pull_one("BAD", ticker_obj=_FakeTicker({}, raise_info=True))
    assert rec["status"].startswith("FAIL")
    assert rec["ticker"] == "BAD"


def test_pull_one_no_info():
    rec = Fund.pull_one("EMPTY", ticker_obj=_FakeTicker({"longName": "X"}))
    assert rec["status"] == "no_info"  # no price field


def test_summary_counts():
    recs = {
        "A": {"status": "ok", "price": 10.0, "pt_mean": 12.0},
        "B": {"status": "ok", "price": None, "n_analysts": 0},
        "C": {"status": "FAIL:RuntimeError:x"},
        "D": {"status": "no_info"},
    }
    s = Fund.summary(recs)
    assert s == {
        "ok": 2,
        "total": 4,
        "fails": ["C"],
        "field_counts": {"price": 1, "pt_mean": 1, "n_analysts": 1},
    }


def test_summary_field_counts_surface_global_schema_break():
    s = Fund.summary(
        {
            "A": {"status": "ok", "price": 10.0, "mktcap": None},
            "B": {"status": "ok", "price": 20.0, "mktcap": None},
        }
    )
    assert s["field_counts"]["price"] == 2
    assert "mktcap" not in s["field_counts"]


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
