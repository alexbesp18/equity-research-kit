"""Shared visual tokens for equity research workbooks.

Coverage books should look intentional without each caller inventing fonts, fills, and
number formats. Keep this module boring: stable tokens in, XlsxWriter format dicts out.
"""

from __future__ import annotations

FONT_FAMILY = "Aptos"
FONT_SIZE = 10

COLORS = {
    "ink": "17202A",
    "muted": "57606A",
    "border": "D0D7DE",
    "header": "0B3D2E",
    "header_alt": "123C69",
    "banner_fill": "FFF8E1",
    "alert": "B42318",
    "positive_fill": "DAF4E0",
    "neutral_fill": "FFF1C2",
    "negative_fill": "FBD5D0",
    "white": "FFFFFF",
}

BASE_FORMAT = {
    "font_name": FONT_FAMILY,
    "font_size": FONT_SIZE,
    "font_color": COLORS["ink"],
    "valign": "top",
    "border": 1,
    "border_color": COLORS["border"],
}

VERDICT_BG = {
    "top_pick": "1B7F37",
    "buy_laggard": "1F6FEB",
    "quality_wait": "9A6700",
    "watch": "6E7781",
    "context": "57606A",
    "pass": "B42318",
}

LAGGARD_BG = {
    "laggard": COLORS["positive_fill"],
    "fair": COLORS["neutral_fill"],
    "leader_ran": COLORS["negative_fill"],
    "value_trap": "F4C7C3",
}


def fmt_spec(**overrides: object) -> dict[str, object]:
    """Return a fresh XlsxWriter format spec from the shared base."""
    spec: dict[str, object] = dict(BASE_FORMAT)
    spec.update(overrides)
    return spec


def coverage_format_specs() -> dict[str, dict[str, object]]:
    """Semantic format specs used by CoverageBook.

    The historic short keys remain because downstream skills call them directly. The
    longer aliases let new generators choose by intent without making up a new style.
    """
    specs = {
        "title": fmt_spec(
            font_size=17,
            bold=True,
            font_color=COLORS["header"],
            border=0,
        ),
        "sub": fmt_spec(
            font_size=9,
            italic=True,
            font_color=COLORS["muted"],
            border=0,
        ),
        "note": fmt_spec(
            font_size=9,
            italic=True,
            font_color=COLORS["alert"],
            border=0,
        ),
        "banner": fmt_spec(
            text_wrap=True,
            bg_color=COLORS["banner_fill"],
            font_color=COLORS["header"],
        ),
        "hdr": fmt_spec(
            bold=True,
            bg_color=COLORS["header"],
            font_color=COLORS["white"],
            text_wrap=True,
            align="center",
            valign="vcenter",
        ),
        "cell": fmt_spec(text_wrap=True),
        "cellc": fmt_spec(align="center"),
        "boldc": fmt_spec(bold=True, align="center"),
        "num": fmt_spec(num_format="#,##0.00", align="right"),
        "num1": fmt_spec(num_format="#,##0.0", align="right"),
        "money": fmt_spec(num_format="$#,##0.00", align="right"),
        "mcap": fmt_spec(num_format='$#,##0.0,,,"B"', align="right"),
        "mcapj": fmt_spec(num_format='#,##0.0,,,"B"', align="right"),
        "pct": fmt_spec(num_format='0.0"%"', align="right"),
        "formula_output": fmt_spec(
            num_format="#,##0.00",
            align="right",
            bg_color="EAF2FF",
            font_color=COLORS["header_alt"],
        ),
    }
    specs["section_header"] = specs["hdr"]
    specs["table_header"] = specs["hdr"]
    specs["body_text"] = specs["cell"]
    specs["body_center"] = specs["cellc"]
    specs["body_number"] = specs["num"]
    specs["body_percent"] = specs["pct"]
    specs["money_usd"] = specs["money"]
    specs["market_cap_usd"] = specs["mcap"]
    specs["market_cap_neutral"] = specs["mcapj"]
    return specs
