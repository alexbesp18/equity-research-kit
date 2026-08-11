import xlsxwriter

from er_kit import technicals as T


def _make_tech_xlsx(path):
    wb = xlsxwriter.Workbook(str(path))
    ws = wb.add_worksheet("tech_analysis_clean")
    headers = ["Ticker", "Price", "LT_Trend", "LT_52W_Position", "MT_RSI_14", "Market_Regime"]
    ws.write_row(0, 0, headers)
    ws.write_row(1, 0, ["ALFA", 157.34, "UPTREND", "94%", 60.1, "bull_strong"])
    ws.write_row(2, 0, ["BETA", 281.75, "SIDEWAYS", "85%", 47.5, "bull_strong"])
    ws.write_row(3, 0, ["GAMM", 31.01, "STRONG_DOWNTREND", "55%", 40.9, "bull_strong"])
    wb.close()


def test_load_filters_and_keeps(tmp_path):
    p = tmp_path / "tech.xlsx"
    _make_tech_xlsx(p)
    out = T.load(str(p), tickers=["ALFA", "GAMM"], keep=["Ticker", "LT_Trend", "MT_RSI_14"])
    assert set(out.keys()) == {"ALFA", "GAMM"}
    assert out["ALFA"]["LT_Trend"] == "UPTREND"
    assert out["GAMM"]["MT_RSI_14"] == 40.9
    assert "BETA" not in out


def test_load_stores_stripped_ticker_value(tmp_path):
    p = tmp_path / "tech.xlsx"
    wb = xlsxwriter.Workbook(str(p))
    ws = wb.add_worksheet("tech_analysis_clean")
    ws.write_row(0, 0, ["Ticker", "Price"])
    ws.write_row(1, 0, [" ALFA ", 157.34])
    wb.close()

    out = T.load(str(p), keep=["Ticker", "Price"])
    assert set(out.keys()) == {"ALFA"}
    assert out["ALFA"]["Ticker"] == "ALFA"


def test_load_all_when_no_filter(tmp_path):
    p = tmp_path / "tech.xlsx"
    _make_tech_xlsx(p)
    out = T.load(str(p), keep=["Ticker", "Price"])
    assert set(out.keys()) == {"ALFA", "BETA", "GAMM"}


def test_duplicate_ticker_row_fails_loud(tmp_path):
    import pytest
    import xlsxwriter

    p = tmp_path / "dup.xlsx"
    wb = xlsxwriter.Workbook(str(p))
    ws = wb.add_worksheet("tech_analysis_clean")
    ws.write_row(0, 0, ["Ticker", "Price"])
    ws.write_row(1, 0, ["AAA", 1.0])
    ws.write_row(2, 0, ["AAA", 2.0])  # duplicate ticker row
    wb.close()
    with pytest.raises(ValueError, match="duplicate ticker row"):
        T.load(str(p), keep=["Ticker", "Price"])


def test_coverage_split(tmp_path):
    p = tmp_path / "tech.xlsx"
    _make_tech_xlsx(p)
    cov = T.coverage(str(p), ["ALFA", "BETA", "QNTY", "ZZZZ"])
    assert cov["covered"] == ["ALFA", "BETA"]
    assert cov["missing"] == ["QNTY", "ZZZZ"]
