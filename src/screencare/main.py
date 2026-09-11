"""Application entry point for ScreenCare.

Both ``python -m screencare`` and the ``screencare`` console script resolve
to :func:`main`, which delegates to the bootstrap module. Keeping this file
tiny means there is exactly one place that decides how the process starts.
"""

from __future__ import annotations

import sys

from screencare.app.bootstrap import run


def main() -> int:
    """Start ScreenCare and return the process exit code."""
    return run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
