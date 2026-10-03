# ScreenCare

A calm focus and wellness companion that runs in your browser.
Adaptive Pomodoro-style focus blocks, with eye-rest, hydration, and movement
reminders merged into one well-timed break instead of five separate nags.

**Focus deeply → step away → move → hydrate → return refreshed.**

> **Status: v1.0.** Runs locally and deploys to Vercel with no configuration.
> What's next is in [docs/PLAN.md](docs/PLAN.md). The original Windows desktop app and its specs
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
.venv\Scripts\Activate.ps1          # Windows (PowerShell). See the note below if it's blocked
source .venv/bin/activate           # macOS / Linux

# 4. Install ScreenCare plus the dev tools
pip install -e ".[dev]"

# 5. Start the server
uvicorn app:app --reload
```

Open **http://127.0.0.1:8000** and start a focus block. `--reload` restarts
the server when you edit Python files.

> **Windows: "running scripts is disabled on this system"?** PowerShell's
> default execution policy (*Restricted*) blocks every `.ps1` script,
> including the venv's `Activate.ps1`. Allow local scripts for your user, once
> (no admin needed):
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```
>
> `RemoteSigned` still requires downloaded scripts to be signed. If you'd
> rather not change it, skip activation and call the venv directly:
> `.venv\Scripts\python -m pip install -e ".[dev]"`, then
> `.venv\Scripts\python -m uvicorn app:app --reload`. Or use
> `.venv\Scripts\activate.bat` from `cmd`.

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

ScreenCare needs no Vercel configuration. Vercel finds the FastAPI `app` in
`app.py`, installs dependencies from `pyproject.toml`, and serves `public/`
from its CDN. Nothing is stored server-side, so there's no database or
environment variables to set up.

### From the dashboard (recommended)

1. **Push the code to GitHub** (GitLab and Bitbucket work too):
   ```bash
   git push -u origin main
   ```
2. Sign in at [vercel.com](https://vercel.com) and choose **Add New… → Project**.
3. **Import** the ScreenCare repository. Give Vercel access to it if it isn't listed.
4. On the configuration screen, keep the defaults:
   - **Framework Preset**: FastAPI (detected automatically)
   - **Root Directory**: `./`
   - **Build Command / Output Directory**: leave empty
   - **Environment Variables**: none
5. Click **Deploy**. After about a minute you get a URL like
   `screencare-<you>.vercel.app`.
6. Open it and check:
   - `/api/health` returns `{"status":"ok"}`
   - the page loads and a focus block starts
7. Optional: **Settings → Domains** to add your own domain.

After that, every push to another branch gets its own **preview URL**, and
every push or merge to `main` deploys **production**.

### From the command line

```bash
npm i -g vercel        # needs Node.js
vercel login
vercel                 # first run links the project and creates a preview
vercel --prod          # deploy to production
```

### Good to know

- **HTTPS is required** for notifications, idle detection, and installing as
  an app. Vercel URLs already use it.
- If you change templates or styles, rebuild `public/app.css` (see
  [Optional](#optional)) and commit it. Vercel doesn't run Tailwind.
- To roll back, use **Deployments → ⋯ → Promote to Production** on any
  earlier deployment.

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
