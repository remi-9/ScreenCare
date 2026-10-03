# ScreenCare

A calm focus and wellness companion that runs in your browser.
Adaptive Pomodoro-style focus blocks, with eye-rest, hydration, and movement
reminders merged into one well-timed break instead of five separate nags.

**Focus deeply → step away → move → hydrate → return refreshed.**

> **Status:** the web version runs locally and is ready to deploy on Vercel
> (`uvicorn app:app --reload` to try it). Remaining work is in
> [docs/PLAN.md](docs/PLAN.md). The original Windows desktop app and its specs
> are at git tag `desktop-final`.

## Run it locally

You need **Python 3.12 or newer** ([python.org](https://www.python.org/downloads/)) and git.

```bash
# 1. Get the code
git clone <your-repo-url> ScreenCare
cd ScreenCare

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
.venv\Scripts\Activate.ps1          # Windows (PowerShell)
source .venv/bin/activate           # macOS / Linux

# 4. Install ScreenCare plus the dev tools
pip install -e ".[dev]"

# 5. Start the server
uvicorn app:app --reload
```

Open **http://127.0.0.1:8000** and start a focus block. `--reload` restarts
the server when you edit Python files.

If PowerShell refuses to run `Activate.ps1`, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use
`.venv\Scripts\activate.bat` from `cmd`.

### Optional

```bash
pytest                                     # run the tests (< 1 s)
ruff check --fix . && ruff format .        # lint and format
tailwindcss -i screencare/styles/app.css -o public/app.css --minify   # rebuild CSS after editing templates or styles
```

The first `tailwindcss` run downloads the Tailwind binary. Commit the rebuilt
`public/app.css`.

### Browser features

- **Notifications**: allow them when asked (on your first focus block) to get
  break reminders while the tab is in the background.
- **Automatic away detection**: Settings → *Detect automatically* (Chrome and
  Edge). Other browsers still notice sleep and closed tabs, and you can use
  *Step away* during a focus block.
- **Install as an app**: use your browser's *Install ScreenCare* option to give
  it its own window.

## Deploy to Vercel

1. Push the repo to GitHub.
2. In Vercel: **Add New → Project**, import the repo, and keep the defaults
   (no build command, no output directory). Vercel detects the FastAPI `app` in
   `app.py`, installs dependencies from `pyproject.toml`, and serves `public/`
   from its CDN.
3. Every push gets a preview URL. Merging to `main` deploys production.

Or, with the CLI: `npm i -g vercel`, then run `vercel` (preview) or
`vercel --prod` from the repo root.

## Docs

| File | Read it for |
|---|---|
| [docs/concept.md](docs/concept.md) | What ScreenCare is and how it should feel (the product source of truth) |
| [docs/PLAN.md](docs/PLAN.md) | The overhaul: what's kept, what's cut, the phases |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the web version works |
| [docs/UI.md](docs/UI.md) | Visual direction and accessibility checklist |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Setup, tests, deploy |

## Stack

Python 3.12+ · FastAPI · Jinja2 · Tailwind CSS · Alpine.js · Vercel

## Privacy

No account, no tracking, nothing stored on a server. Your history stays in
your browser and leaves it only if you export it. ScreenCare is a wellness
aid, not a medical device.
