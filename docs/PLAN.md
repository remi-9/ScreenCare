# Overhaul plan: desktop app → web app on Vercel

Status: **v1.0 complete** (October 2026). Only deployment and launch items remain. The decisions below were settled: rules run
in stateless FastAPI on Vercel, the desktop app is tagged `desktop-final` and
removed, and the frontend is Jinja + Tailwind + Alpine.

## Why

ScreenCare's idea is small and gentle: *focus deeply → step away → move →
hydrate → return refreshed* ([concept.md](concept.md)). The desktop build
around it grew much larger than that idea:

| Area | Today | Problem |
|---|---|---|
| Code | ~7,300 lines across 13 packages | Five engines, a scheduler, a deadline-budget helper, a coordinator, and an app-session layer that wires them all together, for what is one timer with three reminders |
| Docs | ~110 KB of spec + phase logs | Agents and people were told to re-read all three spec docs before every milestone; that's most of the "analysis takes forever" cost |
| Comments | 190+ citations like "Technical.md §27" | Every docstring explains its own justification; reading the code means cross-referencing a 2,000-line spec |
| Defensive layers | Capability detection, adapter factories, checkpoint throttling, crash-recovery reconciliation, settings backends, migrations | Each one is reasonable on its own; together they're a lot of machinery for a single-user timer |
| Distribution | Windows-only Nuitka build, unsigned, never verified end to end | Hard to share, hard to try, and SmartScreen flags it |
| Dev setup | Pinned to Python 3.13; the local `.venv` points at a Python that's no longer installed | Nobody can run it without reinstalling an older Python |

The goal is a version anyone can open from a URL, that keeps the product's
character, and that a person or an AI agent can understand in one sitting.

## What stays (the product)

These are the rules that make ScreenCare *ScreenCare*. They carry over
unchanged in behavior:

- Three modes: **Classic** 25/5, **Deep Focus** 50/10, **Adaptive** (duration
  nudged by "too short / just right / too long" feedback, clamped to sane bounds).
- **Flow protection** at the end of a focus block: *Start break*, *Finish
  current thought* (once, 2 min), *Extend 5 min* (max 2). The UI gets warmer and
  firmer, never alarming, as the user keeps postponing.
- **Subtle eye-rest prompts** every ~20 min of active focus. In-page only,
  never a system notification.
- **Smart hydration**: hourly, but folded into a recovery break when that
  break is due within the merge window (default 10 min). Optional strict mode.
- **Idea Walk** ("I'm stuck"): 5-minute walk, then "Anything come to mind?"
  note capture.
- **Away time is not focus time.** Time spent idle, locked, asleep, or with the
  app closed doesn't count, and an away stretch of 3 min or more is credited as a
  natural break.
- **Quiet mode**: pause reminders for 30/60/120 min.
- **Dashboard**: sessions, focused time, average length, breaks taken/skipped,
  walks, hydration check-ins, week trend. No streaks or scores ("not a
  productivity competition").
- **Privacy**: no account, no tracking, no stored server data. History lives
  in the user's browser.

## What goes

| Removed | Replaced by |
|---|---|
| PySide6, QML, view models, tray icon, `bootstrap.py` | Server-rendered HTML (Jinja) + Tailwind + Alpine.js, see [UI.md](UI.md) |
| `Scheduler`, `DeadlineBudget`, `Clock`/`FakeClock`, monotonic time | Absolute UTC timestamps stored in the session state. Tests pass `now=` explicitly |
| `FocusEngine`, `BreakEngine`, `HydrationEngine`, `EyeRestEngine`, `WellnessCoordinator`, `AppSession` | One pure module, `screencare/rules.py`: `apply(state, action, now) -> (state, events)` |
| SQLite, migrations, 4 repositories, `QSettings` backends, crash-recovery snapshots | `localStorage` in the browser (+ JSON export/import). Crash recovery comes free: state is saved on every change, deadlines are absolute times |
| Windows `ctypes` idle/lock/sleep adapters, platform factory, capability detection | Browser Idle Detection API where available, plus a heartbeat-gap rule for sleep and closed tabs |
| `NotificationService` protocol + tray adapter | `events` returned by the API; the page shows them (Web Notifications when hidden, an in-page toast otherwise) |
| Nuitka / `pyside6-deploy` / icon pipeline | `git push` → Vercel |
| Phase-by-phase architecture log, spec section citations | Short [ARCHITECTURE.md](../ARCHITECTURE.md); plain comments only where the *why* isn't obvious |

The old specs and code remain available at git tag `desktop-final`.
They aren't required reading.

## Target shape

```text
Browser (the user's machine)                     Vercel (stateless Python)
┌──────────────────────────────────────┐        ┌────────────────────────────┐
│ Jinja-rendered page + Tailwind CSS   │  GET / │ FastAPI  screencare/web.py │
│ Alpine.js: countdown, toasts, forms  │◀──────▶│   POST /api/act            │
│ localStorage: state, settings,       │  JSON  │   POST /api/summary        │
│   history                            │        │ screencare/rules.py  (pure)│
│ IdleDetector / heartbeat → presence  │        │ screencare/summary.py      │
│ Notification API                     │        │ (stores nothing)           │
└──────────────────────────────────────┘        └────────────────────────────┘
```

Python makes every decision; the browser displays, counts down, and
remembers. The page only calls the API on a user action or when a deadline it
already knows about passes, so that's a handful of requests per focus block and
never one per second. Details are in [ARCHITECTURE.md](../ARCHITECTURE.md).

## Phases

Each phase ends deployable, with `pytest` and `ruff check` green.

### Phase 0: freeze the desktop app (½ day)

- [x] Commit the staged packaging work (`pysidedeploy.spec`, `packaging/`,
      `windows.py` tweak) as the last desktop commit.
- [x] Tag it `desktop-final` so the full PySide6 app stays one checkout away.
- [x] Move the spec docs to `docs/`, write this plan, and rewrite the README,
      ARCHITECTURE, DEVELOPMENT, and CLAUDE docs. *(this change)*

### Phase 1: pure rules core (1–2 days)

- [x] Delete `app/`, `ui/`, `platform/`, `activity/`, `notifications/`,
      `persistence/`, `scheduler/`, `packaging/`, `pysidedeploy.spec`, `tests/ui/`.
- [x] Flatten `src/screencare/` → `screencare/` (simpler imports on Vercel).
- [x] Write `screencare/rules.py`: `Settings`, `Session` (Pydantic models) and
      `apply(session, action, now, settings) -> Result(session, events)`.
      Port the logic from `focus_engine.py`, `hydration_engine.py`,
      `eye_rest_engine.py`, `wellness_coordinator.py`, `adaptive_focus.py`,
      and `break_engine.py`. Expect ~300 lines total.
- [x] Move `analytics/summary.py` → `screencare/summary.py` as-is (already pure).
- [x] Port the acceptance scenarios as tests with explicit `now`: sleep
      mid-session isn't counted, natural break credited, hydration merges into
      a nearby break, extension limit, reload/closed-tab gap, quiet mode.
      Keep tests focused on behavior and drop the per-method tests of deleted
      internals. Target: ~50 tests, well under a second.
- [x] `pyproject.toml`: `requires-python = ">=3.12"`, deps `fastapi`, `jinja2`;
      dev deps `pytest`, `httpx2`, `ruff`, `pytailwindcss`. Drop PySide6.

### Phase 2: API + first deploy (1 day)

- [x] `screencare/web.py`: FastAPI app with `GET /` (render page), `POST
      /api/act`, `POST /api/summary`, `GET /api/health`.
- [x] `app.py` at the repo root exporting `app` (Vercel's zero-config FastAPI
      entrypoint), static files in `public/`.
- [x] API tests via FastAPI's `TestClient`.
- [ ] Connect the repo to Vercel. Every push gets a preview URL and `main`
      deploys to production. That preview *is* the integration test.

### Phase 3: the UI (2–3 days)

- [x] Build the design in [UI.md](UI.md): Focus, In-session, Recovery due,
      Break, Idea Walk, Dashboard, Settings.
- [x] Tailwind v4 via `pytailwindcss`. Commit the built `public/app.css` so
      Vercel needs no Node build step.
- [x] Alpine.js (pinned, from jsdelivr) for the countdown ring, toasts,
      and forms. Target: one `public/app.js`, ~300 lines.

### Phase 4: browser integrations (1–2 days)

- [x] `localStorage` persistence of state, settings, and history (versioned
      key, so a future format change can migrate or reset cleanly). JSON
      export/import in Settings.
- [x] Presence: `IdleDetector` (Chromium, asks permission, 60 s minimum
      threshold, also reports screen lock). Everywhere else: a 15 s heartbeat,
      where a wall-clock gap of more than 2 min means away for that gap. That
      one rule also covers laptop sleep, a closed tab, and a browser crash.
      Manual "Step away" button as the universal fallback.
- [x] Notifications: request permission on first focus start, not on page
      load. System notification only when the page is hidden; in-page toast
      otherwise. Eye-rest is never a system notification.
- [x] PWA: manifest + minimal service worker, so ScreenCare can be installed
      into its own window. That's the closest web equivalent of "lives in the
      tray".

### Phase 5: dashboard, accessibility, polish (1–2 days)

- [x] Dashboard via `/api/summary` (today + 7-day trend).
- [x] Accessibility pass against the checklist in [UI.md](UI.md). axe-core
      (WCAG 2.2 AA + best practices) reports zero violations on every screen, in
      both themes, at 390 px and 1280 px.
- [ ] Manual screen-reader spot check (NVDA or VoiceOver). Automated tools
      can't judge announcement quality.
- [x] Onboarding: one screen explaining modes and asking for notification /
      idle permissions with a plain-language reason.

### Phase 6: launch

- [ ] Production domain on Vercel, README screenshots, `desktop-final`
      mentioned for anyone who wants the native app.

**Size target after Phase 5:** ~800 lines of Python (incl. tests), ~300 lines
of JS, ~6 templates. Today: ~7,300 lines of Python + QML.

## Known trade-offs of going web

Stated up front so they aren't surprises later:

- **Background tabs are throttled.** Chrome may delay timers in a hidden tab to
  about once a minute, so a reminder can be up to ~1 min late. Deadlines are
  absolute timestamps, so nothing drifts or gets lost. Installing the PWA helps.
- **System-wide idle detection is Chromium-only** (Chrome, Edge, Opera,
  desktop). Firefox/Safari fall back to the heartbeat + manual "Step away".
- **The page has to be open** (tab or installed window) for reminders. No push
  server, by design: that would need accounts and stored data.
- **Fullscreen/presentation and OS Do-Not-Disturb detection** aren't
  available to web pages. Quiet mode stays the manual equivalent.
- **"Launch at login"** becomes the OS's own "open installed app at login"
  option for PWAs, not something ScreenCare controls.
- **Stateless API**: the server trusts the session JSON the browser sends.
  That's fine, since it's only ever the user's own data and nothing is stored.
  Pydantic still validates and clamps every field.

## Decisions (settled)

The recommended option was chosen in each case.

1. **Where the rules run.**
   *Stateless FastAPI on Vercel (recommended)*: fast first load, real Python
   on the server, trivially testable. The cost is that actions need a network
   connection.
   *Alternative: Pyodide/PyScript*: the same Python running inside the
   browser, fully offline and with no server at all. But it means a ~10 MB
   first download and a slower start, which goes against "calm and light".
2. **The desktop app.** *Tag `desktop-final` and delete (recommended)*, or
   keep both. Keeping both means two UIs and two persistence layers sharing
   one rules module. That's possible, but it's exactly the sprawl this plan
   removes.
3. **Frontend weight.** *Jinja + Tailwind + Alpine (recommended)*: Python
   stays the main language, no Node toolchain. *Alternative: Next.js +
   shadcn/ui*: the most polished component ecosystem and Vercel's native
   path, but it turns the frontend into a TypeScript project roughly the size
   of the Python one. Python-native UI frameworks (Reflex, NiceGUI) were ruled
   out because they depend on long-lived websocket servers, which don't fit
   Vercel's request/response functions.
4. **Component kit.** *Hand-rolled Tailwind with a small token set
   (recommended)* gives the most distinctive look and zero plugin plumbing.
   DaisyUI or Basecoat are fine if speed matters more than character.

## Definition of done (every change)

1. `pytest` passes.
2. `ruff check --fix .` and `ruff format .` (apply; don't just check).
3. The Vercel preview for the branch loads and a focus session can be started.

That's the whole checklist. No manual packaging smoke tests, no
re-reading the specs.
