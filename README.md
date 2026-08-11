# equity-research-kit

> Extracted from the system I run daily; here's what it does for me.

`equity-research-kit` treats research workbooks as software: it ingests structured data, keeps price-target math currency-safe, corrects untrusted research fields, renders consistent `.xlsx` coverage books, and checks both visual contracts and real spreadsheet opening behavior.

The public repository contains the real deterministic engine and test suite, sanitized of private research content and delivery wiring. Its bundled workbook is deliberately fictional.

## Run the demo

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv run python examples/run_demo.py
```

The command is keyless and offline after its public dependencies are resolved. It regenerates `samples/synthetic_coverage_book.xlsx`, runs the visual contract, and runs the clean-open gate. On macOS with Microsoft Excel installed, clean-open drives Excel and closes only the named workbook. On other platforms it reports a successful platform skip. An automation-environment failure is reported as `UNAVAILABLE`, never as a clean-open pass.

## What is included

- `fundamentals`: paced, per-symbol yfinance ingestion that records failures instead of silently dropping symbols.
- `technicals`: defensive loading of ticker-keyed technical workbooks, including duplicate-schema guards.
- `universe`: merge helpers that preserve an explicit universe and its missing-data states.
- `corrections`: currency-safe upside math and enum sanitation for untrusted research fields.
- `coveragebook`: consistent, clean-open-oriented `.xlsx` rendering.
- `visual_lint` and `cleanopen`: post-render visual checks plus an Excel automation gate.

## Deliberate boundaries

This package does not discover a universe, make investment recommendations, validate qualitative claims, fetch private data, submit orders, or notify anyone. `yfinance` is retained for optional ingestion, but the demo never calls it. A passing clean-open gate means the workbook opened without a repair prompt; it does not establish that research claims are true or current.

## Verification

```bash
uv run pytest
uv run ruff format --check .
uv run ruff check .
```

## Honesty and prior art

This is workflow infrastructure, not a research method or an investment product. It builds on public Python libraries including `yfinance`, `openpyxl`, and `XlsxWriter`. The safeguards reflect practical spreadsheet and data-quality failure modes, but they are not a substitute for independent evidence review.

## Demo transcript

The following transcript is produced from this repository's bundled synthetic fixture on
macOS with Excel installed; on other platforms clean-open reports a successful platform
skip, and an automation failure reports UNAVAILABLE — never a pass:

```text
artifact: samples/synthetic_coverage_book.xlsx
visual_lint: PASS (0 issue(s))
clean_open: PASS (CLEAN OPEN OK | workbook=synthetic_coverage_book.xlsx | sheets=2)
```
