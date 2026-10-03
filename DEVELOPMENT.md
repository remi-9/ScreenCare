# Development

## Setup

Any Python 3.12 or newer.

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows
source .venv/bin/activate           # macOS/Linux
pip install -e ".[dev]"
```

If Windows says scripts are disabled, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once (see the README).

## Run locally

```bash
uvicorn app:app --reload            # http://127.0.0.1:8000
```

`vercel dev` also works if you have the Vercel CLI and want production-like
routing for `public/`.

## Styles

```bash
tailwindcss -i screencare/styles/app.css -o public/app.css --minify   # add --watch while editing
```

Commit `public/app.css`: Vercel serves it as-is and runs no CSS build.

## Checks

```bash
pytest                              # < 1 s, no browser needed
ruff check --fix . && ruff format .
```

That's the whole definition of done, plus "the Vercel preview loads and a
focus session starts". Rules tests pass `now=` explicitly, so never sleep in a
test.

## Deploy

Push a branch to get a preview URL from Vercel; merge to `main` to deploy
production. There's no build configuration: Vercel detects the FastAPI `app`
in `app.py` and serves `public/` from its CDN.
