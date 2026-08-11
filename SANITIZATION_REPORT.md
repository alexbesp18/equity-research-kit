# Sanitization report

Source areas are described by category on purpose — naming the private layout would itself
leak operational structure.

Scope: a public extraction of reusable research-workbook tooling. The source tree was read-only.

| Category | Source file(s) | Action |
| --- | --- | --- |
| Private QA harnesses with absolute personal paths and private-ground-truth references | two private QA harness scripts | Excluded entirely. |
| Private workflow template with absolute local input placeholder and workflow-specific owner constraints | a private workflow template | Excluded entirely; it is not needed to run the public package, tests, or demo. |
| Source-specific research names and values in the end-to-end example | `examples/build_coverage_example.py` | Replaced with two explicitly fictional records, labels, fundamentals, targets, and notes. |
| Source-specific research names in renderer and technical-ingestion tests | `tests/test_coveragebook.py`, `tests/test_technicals.py`, `tests/test_visual_lint.py` | Replaced with fictional identifiers while preserving the tested behaviors. |
| Source-specific research names in correction tests | `tests/test_corrections.py` | Replaced with fictional identifiers and a fictional research-firm label while preserving correction coverage. |
| Source-history/domain references in package documentation | `er_kit/__init__.py`, `er_kit/fundamentals.py`, `er_kit/technicals.py`, `er_kit/universe.py`, `er_kit/corrections.py`, `er_kit/cleanopen.py`, `er_kit/coveragebook.py`, `pyproject.toml` | Rewritten as neutral descriptions of the retained behavior. |
| Generated research books and other source outputs | source tree | Not copied. One regenerated synthetic workbook is the only workbook included. |
| Credentials, notification routing, scheduled-job labels, host identifiers, employer/client content, owner positions, holdings, or account amounts | source files retained for extraction | None found. |

## Judgment calls

- The workflow template was structurally reusable, but it depended on private context. Excluded rather than risk retaining any of it.
- Test tickers and company labels can be read as research provenance even when used only as fixtures. They were replaced with plainly fictional values.
