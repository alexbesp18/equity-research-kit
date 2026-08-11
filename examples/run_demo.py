#!/usr/bin/env python3
"""Build and verify the bundled synthetic workbook without network access."""

from __future__ import annotations

from build_coverage_example import DEFAULT_OUT, build_example

from er_kit.visual_lint import SheetVisualContract, lint_workbook


def main() -> int:
    out, clean_ok, clean_message = build_example(DEFAULT_OUT)
    lint = lint_workbook(out, contracts=[SheetVisualContract("Decision", expected_freeze="C5")])
    clean_unavailable = clean_message.startswith("environment/automation failure:")
    clean_verdict = "PASS" if clean_ok else "UNAVAILABLE" if clean_unavailable else "FAIL"
    print(f"artifact: {out.relative_to(out.parents[1])}")
    print(f"visual_lint: {'PASS' if lint.ok else 'FAIL'} ({len(lint.issues)} issue(s))")
    print(f"clean_open: {clean_verdict} ({clean_message})")
    if not lint.ok:
        for issue in lint.issues:
            print(f"  {issue.code} {issue.sheet}!{issue.cell}: {issue.message}")
    return 0 if lint.ok and (clean_ok or clean_unavailable) else 1


if __name__ == "__main__":
    raise SystemExit(main())
