# ScreenCare

A calm focus and wellness companion that runs in your browser.

**Focus deeply → step away → move → hydrate → return refreshed.**

## What it does

- **Focus blocks** in three rhythms: Classic (25/5), Deep focus (50/8), or
  Adaptive, which tunes itself from a quick "how was that?" after each block.
- **One break, not five nags.** Eye-rest, water, and movement reminders are
  folded into a single, well-timed recovery break.
- **Flow protection.** When a block ends, finish your thought or take 5 more
  minutes, with gentle limits so it doesn't become hours.
- **Idea Walk.** Stuck? Take a 5-minute walk, then jot down what came to mind.
- **Notices when you step away.** Away time never counts as focus, and a few
  minutes away counts as a break.
- **A breathing ring** that paces your breaks, plus your own colors and a
  light/dark theme.
- **A simple dashboard** of today and the past week. No streaks, no scores.

## Run it locally

You need **Python 3.12+** and git.

```bash
git clone https://github.com/remi-9/ScreenCare.git
cd ScreenCare
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows (PowerShell)
source .venv/bin/activate           # macOS / Linux
pip install -e ".[dev]"
uvicorn app:app --reload
```

Open **http://127.0.0.1:8000**.

> **Windows: "running scripts is disabled on this system"?** Run this once,
> then activate again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Deploy to Vercel

No configuration needed.

1. Push the repo to GitHub.
2. On [vercel.com](https://vercel.com): **Add New… → Project**, then import the repo.
3. Keep the defaults and click **Deploy**.

Every push to `main` deploys to production. Other branches get preview URLs.

## Tips

- **Allow notifications** when asked, to get break reminders while the tab is
  in the background.
- **Turn on away detection** in Settings (Chrome and Edge) to notice when you
  leave your computer.
- **Install it as an app** from your browser's menu to give it its own window.

## Privacy

No account, no tracking, nothing stored on a server. Your history stays in
your browser and leaves it only if you export it. ScreenCare is a wellness
aid, not a medical device.

---

Built with Python (FastAPI), Tailwind CSS, and Alpine.js. Contributing? See
[DEVELOPMENT.md](DEVELOPMENT.md).
