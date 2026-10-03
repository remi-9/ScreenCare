# ScreenCare

A calm focus and wellness companion that runs in your browser.
Adaptive Pomodoro-style focus blocks, with eye-rest, hydration, and movement
reminders merged into one well-timed break instead of five separate nags.

**Focus deeply → step away → move → hydrate → return refreshed.**

> **Status: mid-overhaul.** ScreenCare is moving from a Windows desktop app
> (PySide6) to a web app on Vercel, still written mainly in Python. See
> [docs/PLAN.md](docs/PLAN.md). The last desktop version will be tagged
> `desktop-final`.

## Docs

| File | Read it for |
|---|---|
| [docs/concept.md](docs/concept.md) | What ScreenCare is and how it should feel (the product source of truth) |
| [docs/PLAN.md](docs/PLAN.md) | The overhaul: what's kept, what's cut, the phases |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the web version works |
| [docs/UI.md](docs/UI.md) | Visual direction and accessibility checklist |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Setup, tests, deploy |
| [docs/archive/](docs/archive/) | The original desktop specs, for reference only |

## Stack

Python 3.12+ · FastAPI · Jinja2 · Tailwind CSS · Alpine.js · Vercel

## Privacy

No account, no tracking, nothing stored on a server. Your history stays in
your browser and leaves it only if you export it. ScreenCare is a wellness
aid, not a medical device.
