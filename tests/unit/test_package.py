"""Sanity tests for the repository/package scaffold itself.

These do not import PySide6 or touch Qt, so they run in *any* Python 3.13
environment (including one without PySide6 installed) as a fast baseline
check that the package is importable and correctly laid out.
"""

from __future__ import annotations

import screencare


def test_package_is_importable() -> None:
    assert screencare.__version__


def test_version_looks_like_a_version() -> None:
    assert isinstance(screencare.__version__, str)
    assert screencare.__version__.count(".") >= 1
