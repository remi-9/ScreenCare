# Architecture

> The PySide6 desktop app this replaced is at git tag `desktop-final`. Its
> architecture is archived in
> [docs/archive/desktop-architecture.md](docs/archive/desktop-architecture.md).

## The one idea

**Python decides. The browser displays, counts down, and remembers.**

The server is a stateless FastAPI app on Vercel. The browser sends the current
session state plus an action, and Python returns the new state plus any
events. Nothing is stored server-side.

```text
browser ──(state, action)──▶ POST /api/act ──▶ rules.apply() ──▶ (state, events) ──▶ browser
```

## Layout

```text
app.py                  Vercel entrypoint: `from screencare.web import app`
screencare/
  rules.py              the whole product logic: Settings, Session, apply()
  summary.py            dashboard aggregation over history records
  web.py                FastAPI routes + Jinja rendering
  templates/            index.html (the whole page), icons.html (SVG macro)
  styles/app.css        Tailwind source (tokens in @theme)
public/                 served by Vercel's CDN as-is
  app.css               built from styles/app.css (committed)
  app.js                Alpine components: timer, presence, storage, notifications
  manifest.webmanifest, sw.js, icons/
tests/
  test_rules.py         behavior scenarios with explicit `now`
  test_summary.py
  test_api.py           FastAPI TestClient
```

## Session state

One flat Pydantic model, serialized to JSON and kept in `localStorage`. Every
deadline is an **absolute UTC timestamp**, which is why there's no scheduler,
no ticking counter, and no crash-recovery code: reloading the page just
re-reads the state.

```text
phase              idle | focusing | paused | recovery_due | breaking | idea_walk
mode, task         classic | deep | adaptive, optional label
started_at         when the focus block began
planned_s, recovery_s
focus, rest,       four Timers: {due_at} while running, {left_s} while frozen.
hydration, eye     `rest` is the break or idea-walk countdown.
active_s, active_since   credited focus time (+ the live stretch, if accruing)
extensions_used, finish_thought_used, extension_s
hydration_pending, eye_pending   reminders waiting to be folded into the break
away_since         set while presence is away
quiet_until
adaptive_focus_s   current adaptive duration
```

"Frozen" vs "running" is the only timing concept: a running timer has a
`due_at`; a frozen one has `left_s`. Freezing converts one to
the other, and thawing converts back. That replaces `Scheduler`, `DeadlineBudget`,
and `Clock` from the desktop version.

## Actions

`POST /api/act` with `{session, settings, action, payload}`:

| Action | Payload | Notes |
|---|---|---|
| `start` | `mode`, `task?` | |
| `pause` / `resume` | | |
| `sync` | | Sent on load and when the browser sees a known deadline pass. Every action fires due timers first, using the server's clock |
| `extend` / `finish_thought` / `start_break` | | Only from `recovery_due`; limits enforced here |
| `end_break` / `skip_break` | `feedback?` | Feedback updates `adaptive_focus_s` |
| `idea_walk` / `return` | `note?`, `resume` | |
| `away` / `back` | `since` | From IdleDetector or the heartbeat gap rule |
| `drink`, `dismiss`, `quiet` | `minutes?` | |
| `stop` | | |

Response: `{session, events, server_now}`. The page uses `server_now` to
correct for clock skew when it renders countdowns.

Events are plain dicts keyed by `event`:

- `{event: "notify", title, body, type}`: system notification if the page is
  hidden, otherwise a toast
- `{event: "banner", text, type}`: subtle in-page prompt (eye rest is always
  this; the page sends `dismiss` after 20 s)
- `{event: "record", type, ...}`: appended to history in `localStorage`
  (`focus`, `break` with `kind` recovery/away/idea_walk/skipped, `drink`, `note`)

Invalid transitions return `409` with a human-readable message. The UI only
offers valid actions, so this means stale state, and the page refetches.

## Rules worth knowing

All live in `rules.py`; values come from `Settings` with clamped defaults.

- **Away isn't focus.** `away` freezes focus, hydration, and eye-rest timers.
  `back` thaws them, and if the gap is ≥ 180 s it emits a `record` for a
  natural break (`source: idle_detected`, never "walk completed").
- **Gap = away.** The page heartbeats every 15 s. A wall-clock gap of more
  than 2 min (sleep, closed tab, crash) is reported as `away` from the last
  heartbeat. One rule covers what used to be sleep/wake handling, lock
  handling, and crash recovery.
- **Hydration merge.** When hydration comes due and a recovery break is due
  within `merge_window` (10 min), it's folded into that break's message
  instead of firing on its own. Strict mode disables merging.
- **Stale reminders don't burst.** On return from a long gap, overdue
  reminders fire at most once and then re-arm from now.
- **Flow protection limits**: 2 extensions of 5 min, 1 finish-thought of 2 min
  per focus block.
- **Quiet mode** suppresses `notify`/`banner` events only. Timers keep running.

## Privacy

- No accounts, cookies, analytics, or server-side storage.
- The API sees session state only for the duration of a request and doesn't
  log request bodies.
- History never leaves the browser except as a user-initiated JSON export.
- Presence comes only from the Idle Detection API's coarse `active/idle` +
  `locked/unlocked` signals and from timer gaps. No input contents, ever.

## Not a medical device

ScreenCare offers wellness suggestions. It never claims to diagnose, prevent,
or treat anything. Copy should reflect that.
