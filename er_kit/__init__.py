"""equity-research-kit — reusable plumbing for deep equity coverage books.

Layers:
- fundamentals: paced yfinance deep pull (sequential, fail-loud-but-continue)
- technicals:   load a technicals export workbook into per-ticker dicts
- universe:     ticker-record shape + merge of the data/research layers
- corrections:  currency-safe upside + verdict sanitize + suppress fabricated blocks
- coveragebook: clean-open xlsx builder (format palette + flexible table renderer)
- cleanopen:    macOS gate proving the .xlsx opens without Excel's repair prompt
- visual_style: shared workbook font, fill, number-format, and semantic style tokens
- visual_lint:  post-render workbook visual contract checks

The deterministic plumbing lives here. Research judgment, source selection, and investment
decisions remain outside the package.
"""

from . import (
    cleanopen,
    corrections,
    coveragebook,
    fundamentals,
    technicals,
    universe,
    visual_lint,
    visual_style,
)

__all__ = [
    "cleanopen",
    "corrections",
    "coveragebook",
    "fundamentals",
    "technicals",
    "universe",
    "visual_lint",
    "visual_style",
]
__version__ = "0.1.0"
