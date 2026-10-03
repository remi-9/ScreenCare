"""Vercel entrypoint (zero-config FastAPI detection looks for `app` here)."""

from screencare.web import app

__all__ = ["app"]
