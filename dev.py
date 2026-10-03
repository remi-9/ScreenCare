"""Local development server: the app plus `public/`, served from one process.

On Vercel, `public/` is served by the CDN and must not be mounted in the app,
so this lives outside the deployed entrypoint (`app.py`).

    uvicorn dev:app --reload
"""

from pathlib import Path

from fastapi.staticfiles import StaticFiles

from screencare.web import app

app.mount("/", StaticFiles(directory=Path(__file__).parent / "public"), name="public")
