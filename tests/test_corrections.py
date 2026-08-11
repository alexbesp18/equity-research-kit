from er_kit import corrections as C


def test_sanitize_verdict_rejects_prose():
    assert C.sanitize_verdict("buy_laggard") == "buy_laggard"
    assert C.sanitize_verdict("quality_wait (unchanged, but upside understated)...") == "watch"
    assert C.sanitize_verdict(None) == "watch"
    assert C.sanitize_verdict("garbage", fallback="pass") == "pass"


def test_resolve_verdict_precedence():
    # clean corrected wins
    assert C.resolve_verdict("watch", "buy_laggard", "context") == "buy_laggard"
    # prose corrected ignored -> refreshed
    assert C.resolve_verdict("watch", "buy_laggard because ...", "context") == "watch"
    # no corrected -> refreshed
    assert C.resolve_verdict("top_pick", None, "context") == "top_pick"
    # nothing valid -> prior, sanitized
    assert C.resolve_verdict(None, None, "pass") == "pass"
    assert C.resolve_verdict(None, None, None) == "watch"


def test_resolve_verdict_accepts_corrected_near_synonyms():
    assert C.resolve_verdict("watch", "hold", "pass") == "watch"
    assert C.resolve_verdict("watch", "avoid", "top_pick") == "pass"
    assert C.resolve_verdict("watch", "sell", "top_pick") == "pass"
    assert C.resolve_verdict("watch", "buy", "pass") == "buy_laggard"
    assert C.resolve_verdict("top_pick", "buy because upside is high", "pass") == "top_pick"


def test_upside_pct():
    assert C.upside_pct(100, 117) == 17.0
    assert C.upside_pct(178.77, 160.6) == -10.2
    assert C.upside_pct(0, 50) is None
    assert C.upside_pct(None, 50) is None
    assert C.upside_pct(50, None) is None


def test_same_line_pt_never_uses_foreign_fallback():
    # currency-mismatch guard: ONLY the same-feed USD PT, never the foreign-line dossier PT
    fund = {"price": 30.55, "pt_mean": 34.04}  # USD listed line
    dossier = {"pt_mean": 144.44}  # another-currency primary-line target
    assert C.same_line_pt(fund, dossier) == 34.04
    # no same-feed PT -> None (NOT the foreign 2500 -> +2400% bug)
    assert C.same_line_pt({"price": 100}, {"pt_mean": 2500}) is None
    assert C.same_line_pt({}, None) is None


def test_upside_pct_rejects_bool():
    # a bool would coerce True->1.0 and fabricate an upside (python AND numpy bool)
    import numpy as np

    assert C.upside_pct(True, 2) is None
    assert C.upside_pct(100, True) is None
    assert C.upside_pct(np.bool_(True), 10.0) is None
    assert C.upside_pct(10.0, np.bool_(True)) is None


def test_upside_pct_result_overflow_is_none():
    # a denormal price can overflow the ratio to inf -> result must be None, not inf
    assert C.upside_pct(1e-300, 1e10) is None


def test_upside_pct_rejects_nonfinite():
    # NaN/inf must become None, not a value that renders as #NUM! on the decision surface
    assert C.upside_pct(100, float("nan")) is None
    assert C.upside_pct(100, float("inf")) is None
    assert C.upside_pct(float("nan"), 50) is None


def test_sanitize_laggard():
    assert C.sanitize_laggard(" laggard ") == "laggard"
    assert C.sanitize_laggard("leader_ran") == "leader_ran"
    assert C.sanitize_laggard("junk") == ""
    assert C.sanitize_laggard(None) == ""


def test_apply_corrections_handles_list_shape():
    # the workflow returns dossiers as a LIST, not a map — suppress must still fire (no silent no-op)
    lst = [
        {"ticker": "ALFA", "analyst": {"recent_actions": [{"firm": "X"}]}},
        {"ticker": "BETA", "analyst": {"recent_actions": [{"firm": "Example Research"}]}},
    ]
    C.apply_corrections(lst, suppress=["ALFA"])
    assert lst[0]["analyst"]["recent_actions"] == []  # ALFA suppressed in the list
    assert len(lst[1]["analyst"]["recent_actions"]) == 1  # BETA untouched


def test_suppress_tolerates_non_dict_dossier():
    # agent output is distrusted: a non-dict dossier / analyst must not crash
    assert C.suppress_analyst_block("junk") == "junk"
    assert C.suppress_analyst_block({"analyst": "not a dict"}) == {"analyst": "not a dict"}
    C.apply_corrections({"X": "junk"}, suppress=["X"])  # must not raise


def test_apply_corrections_suppresses_blocks():
    dossiers = {
        "ALFA": {"analyst": {"recent_actions": [{"firm": "fabricated", "pt": "$100"}]}},
        "BETA": {"analyst": {"recent_actions": [{"firm": "Example Research", "pt": "$52"}]}},
    }
    C.apply_corrections(dossiers, suppress=["ALFA"])
    assert dossiers["ALFA"]["analyst"]["recent_actions"] == []
    assert len(dossiers["BETA"]["analyst"]["recent_actions"]) == 1
