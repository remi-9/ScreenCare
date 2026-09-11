# Architecture

This is a short map of the system. The full design rationale lives in
`ScreenCare — Technical.md`; this file tracks what actually exists in the
repository right now versus what's planned, so it will grow as phases land.

## Target shape

```text
Qt Quick / QML UI
        │
        ▼
PySide6 Application Layer
        │
        ▼
WellnessCoordinator
        │
 ┌──────┼───────────┬─────────────┐
 ▼      ▼           ▼             ▼
Focus  Scheduler  Activity     Notification
Engine            Monitor       Service
 │                  │             │
 └──────────┬───────┴─────────────┘
            ▼
       Persistence
   QSettings + SQLite
            │
            ▼
    OS Integration Layer
 Windows / macOS / Linux
```

Two rules hold everywhere:

1. **QML is presentation only.** Business rules live in Python, in
   `screencare.engines` and `screencare.domain`, and are exposed to QML only
   through narrow view models (`screencare.ui.viewmodels`).
2. **Platform code stays behind interfaces.** `screencare.domain` and
   `screencare.engines` never import Qt-platform or OS-specific APIs
   directly; `screencare.activity` and `screencare.platform` are the only
   places allowed to do that.

## What exists today

### Phase 1 — repository foundation

```text
src/screencare/
├── __init__.py          package version
├── main.py               entry point (python -m screencare / `screencare` script)
├── __main__.py           enables `python -m screencare`
├── app/
│   └── bootstrap.py      builds QGuiApplication + QQmlApplicationEngine, loads Main.qml
└── ui/
    └── qml/Main.qml       placeholder window — no behavior yet
```

`app/bootstrap.py` is deliberately the only place that touches Qt at
startup. It has exactly one job: load the root QML and hand control to the
Qt event loop, returning a non-zero exit code if the QML fails to load
(so a CI/packaging smoke test can catch a broken UI without a display).

### Phase 2 — pure core domain

```text
src/screencare/
├── domain/
│   ├── enums.py     FocusMode, FocusState, PresenceState, BreakKind, ...
│   ├── errors.py     InvalidStateTransition
│   └── models.py     FocusPlan/Durations, FocusSessionSummary, BreakSession, HydrationEvent
├── scheduler/
│   ├── clock.py             Clock protocol, SystemClock, FakeClock
│   ├── scheduler.py          Scheduler — the one central deadline registry
│   └── deadline_budget.py    DeadlineBudget — shared freeze/thaw-on-presence-change helper
└── engines/
    ├── adaptive_focus.py       AdaptiveFocusEngine (deterministic, rules-based)
    ├── focus_engine.py         FocusEngine — the Technical.md §6 state machine
    ├── break_engine.py         BreakEngine — away-time break qualification
    ├── hydration_engine.py     HydrationEngine
    ├── eye_rest_engine.py      EyeRestEngine
    └── wellness_coordinator.py WellnessCoordinator — recovery/hydration merge decisions
```

No Qt, no OS APIs, no I/O — every one of these is driven entirely by an
injected `Clock` and is covered by `tests/unit/` using `FakeClock`
(70 tests, all deterministic — no test waits on a real timer).

Two design points worth calling out:

- **One shared scheduler, not five timers.** `FocusEngine`, `HydrationEngine`,
  and `EyeRestEngine` each schedule their own named deadlines on the same
  `Scheduler` instance via `DeadlineBudget`, rather than owning a timer each
  (`Technical.md` §11, `Implementation Standards.md` §8). `DeadlineBudget`
  is what lets all three implement "sleep/idle doesn't count against you"
  exactly once instead of three times.
- **Presence is a hook, not a sensor, in this phase.** `FocusEngine.on_presence_changed()`
  exists and is fully tested (including the §47 acceptance scenario — start
  a 25-minute session, sleep 30 minutes, wake up: the sleep isn't counted as
  focus time and the session doesn't spuriously complete), but nothing calls
  it yet with a real signal. That wiring is Phase 5's job
  (`GetLastInputInfo`, `WTSRegisterSessionNotification`,
  `WM_POWERBROADCAST` on Windows); Phase 2 only guarantees the engine reacts
  correctly once something does call it.

### Phase 3 — persistence

```text
src/screencare/persistence/
├── database.py          Database — sqlite3 connection, pragmas (WAL etc.), DatabaseError
├── migrations.py         schema_migrations table + versioned migration functions
├── repositories.py        FocusSessionRepository, BreakSessionRepository, HydrationEventRepository
├── session_recovery.py    SessionSnapshot(Repository), reconcile_startup_snapshot()
├── settings.py            AppSettings + SettingsBackend (InMemory / QSettings)
└── paths.py               default_database_path() (QStandardPaths)
```

Almost all of this is plain Python tested against a real (temporary) or
in-memory `sqlite3` connection — 33 new tests, no PySide6 required. Only
`paths.py` and `settings.QSettingsBackend` touch Qt (`QStandardPaths` /
`QSettings`), gated the same `pytest.importorskip("PySide6")` way as the
Phase 1 QML test; their tests build an isolated, temp-file-backed
`QSettings` rather than the app-wide one, so running the suite never
touches the developer's real, persistent ScreenCare settings.

Design points:

- **No ORM, explicit SQL, short transactions.** Each repository method is
  one `with connection:` block. Migrations are plain functions recorded
  in `schema_migrations`, run once, and are meant to be *added to*, never
  edited — `symptom_checkins` (Concept.md's optional check-in feature)
  is deliberately not created yet, since the spec says to keep it
  optional/disabled until the feature itself is built.
- **One exception type for a broken database.** `Database.open()` wraps
  both filesystem and sqlite3 errors as `DatabaseError`, so a caller (the
  app, eventually) can show a recoverable error instead of crash-looping
  (`Implementation Standards.md` §41).
- **Crash recovery is reconciliation from timestamps, not a guess.**
  `session_recovery.py` stores a single-row "what was in progress"
  snapshot and a pure `reconcile_startup_snapshot()` decides, from the
  gap since the last checkpoint: nothing to do, offer to resume (≤ ~2
  min), or close as interrupted — it never reports a session as
  *completed* just because time passed (`Technical.md` §23). This is
  about surviving a crash/restart specifically; the live in-process
  sleep/idle handling for a session that's still running is
  `FocusEngine.on_presence_changed()` (Phase 2).
- **Settings are validated in Python, not trusted from QML.**
  `AppSettings` clamps every duration to the bounds in
  `Implementation Standards.md` §30 and falls back to a safe default for
  a missing, wrong-typed, or corrupted stored value — tested entirely
  through `InMemorySettingsBackend`, with `QSettingsBackend` as a thin,
  separately-tested adapter.
- **Not yet wired up:** nothing calls `SessionSnapshotRepository.save()`
  from a running session, and nothing resolves `default_database_path()`
  into an actual `Database.open()` at startup. Both need Phase 4's real
  app/event loop to have a sensible "when" — Phase 3 only had to prove
  the storage and reconciliation logic are correct in isolation.

### Phase 4 — desktop UI

```text
src/screencare/
├── app/
│   ├── session.py         AppSession — the Qt-free application layer (see below)
│   └── bootstrap.py       QApplication + AppSession + view models + QML, wired together
├── notifications/
│   ├── base.py            Notification, NotificationService protocol, InMemoryNotificationService
│   └── tray_service.py     TrayNotificationService (QSystemTrayIcon adapter)
├── analytics/
│   └── summary.py          dashboard_summary() — pure aggregation over history rows
├── ui/
│   ├── viewmodels/
│   │   ├── focus_view_model.py       FocusViewModel
│   │   ├── break_view_model.py       BreakViewModel
│   │   ├── settings_view_model.py    SettingsViewModel
│   │   └── dashboard_view_model.py   DashboardViewModel
│   └── qml/
│       ├── Main.qml            real window shell: tab bar + break overlay
│       ├── FocusView.qml       timer, mode selection, idea walk
│       ├── BreakView.qml       recovery break / ready screen
│       ├── DashboardView.qml    today/week summary
│       └── SettingsView.qml     bindings over SettingsViewModel
└── persistence/
    ├── repositories.py     + list_since() on every history repo; + IdeaWalkNoteRepository
    ├── migrations.py        + migration 002 (idea_walk_notes table)
    └── settings.py          + AppSettings.window_geometry
```

**`AppSession` (`app/session.py`) is the center of this phase and is
deliberately Qt-free.** It wires the Phase 2 engines, `WellnessCoordinator`,
the Phase 3 repositories, and a `NotificationService` together into the
actual focus-session lifecycle (`start_focus`/`pause`/`resume`/`extend`/
`start_break`/`end_break`/`start_idea_walk`/`return_from_idea_walk`/`stop`,
plus `log_drink`, `dismiss_reminder`, `enter_quiet_mode`), and is driven by
an injected `Clock` exactly like the engines beneath it. That's what let
Phase 4's hardest logic — notification merging, crash-recovery
checkpointing, quiet mode — be fully covered by `tests/unit/test_app_session.py`
using a `FakeClock` and a real (in-memory) SQLite database, with no PySide6
installed. Only the thin Qt layer on top (`FocusViewModel`, `BreakViewModel`,
`bootstrap.py`) needs a human or a PySide6-equipped CI run to confirm.

Design points:

- **Checkpointing lives in `AppSession`, not the engines.** It saves a
  `SessionSnapshot` immediately on every lifecycle transition and at most
  once a minute otherwise (`Technical.md` §27: "Database session writes
  <= 1/minute except transitions"), reading `FocusEngine.plan` /
  `.started_at_utc` — two small new read-only properties added to
  `FocusEngine` this phase specifically so `AppSession` never has to reach
  into its private state.
- **Notification merging is exactly the worked example in `Technical.md`
  §7.** `WellnessCoordinator.decide_recovery`/`.should_fire_hydration_standalone`
  already existed (Phase 2); `AppSession` is what actually calls them at the
  right moments — when hydration comes due mid-session (merge into the
  upcoming break if close enough, otherwise fire standalone) and when
  recovery comes due (fold in a hydration reminder that fired shortly
  before, and any still-pending in-session eye-rest prompt).
- **Eye-rest notifications are always in-app only, never sent through
  `NotificationService`** (`Implementation Standards.md` §22: "should not
  aggressively interrupt"); hydration and recovery notifications go through
  it, so a `TrayNotificationService`-less environment (no system tray) or
  quiet mode can suppress them without touching internal state.
- **Quiet mode suppresses delivery, not state.** `enter_quiet_mode()`
  only gates the `NotificationService.send()` calls in `AppSession`; the
  engines underneath keep running exactly as before, so nothing is lost,
  and the recovery break screen still works normally regardless.
- **`QApplication`, not a bare `QGuiApplication`.** `QSystemTrayIcon`/
  `QMenu`/`QAction` are part of the widgets-based tray stack even though the
  UI itself is Qt Quick/QML; `QApplication` is a `QGuiApplication` subclass
  so `QQmlApplicationEngine` works identically under it.
- **The tray icon is generated in code** (`bootstrap._build_tray_pixmap`),
  not a shipped asset — one less file to keep in sync, and it's checked
  against `QSystemTrayIcon.isSystemTrayAvailable()` first, falling back to
  normal window behavior (`app.setQuitOnLastWindowClosed(True)`) if no tray
  exists, per `Technical.md` §41.
- **The UI tick is throttled when the window is hidden** (1 s while
  visible, 5 s while hidden — `Technical.md` §25/§27) by watching the root
  window's `visibleChanged` signal from Python; `AppSession.tick()` itself
  doesn't care how often it's called; `Scheduler`'s wall-clock correctness
  means a slower tick never causes a missed or late deadline, only a
  slightly less frequent check for one that's already due.
- **`DashboardViewModel` reads the repositories directly**, not through
  `AppSession` — the dashboard is a read-only report over history, not a
  control surface for the live session, and it only queries on open or by
  explicit refresh (`Technical.md` §42), never on the per-second UI timer.
- **A tiny new migration (002)** adds `idea_walk_notes` — Concept.md's
  "anything come to mind?" capture — kept in its own table since a note
  isn't tied to any one focus session.

**Deliberately not done in this phase:**

- **Launch-at-login is a stored preference only.** `SettingsViewModel.launchAtLogin`
  round-trips through `AppSettings`, but nothing registers or removes an
  actual OS autostart entry yet — that's a Windows platform adapter, Phase 5.
- **The break countdown shown in `BreakView.qml` is not currently
  enforced or persisted second-by-second** the way the focus countdown is;
  `BreakEngine` still just records start/end timestamps. Concept.md only
  ever describes the break duration as a suggestion, not something the
  engine must enforce, so this wasn't extended this phase.
- **No native Windows toast, no presence-aware notification suppression.**
  `TrayNotificationService` is exactly the `QSystemTrayIcon.showMessage`
  MVP path `Technical.md` §16 specifies; richer platform notifications and
  automatic LOCKED/SLEEPING/IDLE-based suppression are explicitly Phase 5+
  (`Technical.md` §45's "later" list).

### Phase 5 — first platform integration (Windows)

```text
src/screencare/activity/
├── base.py               ActivityProvider / PowerMonitor / AutostartService protocols, PlatformCapabilities
└── presence_monitor.py    PresenceMonitor — Qt-free idle/lock/sleep decision logic

src/screencare/platform/
├── windows.py             WindowsActivityProvider, WindowsSessionMonitor, WindowsAutostartService (ctypes/winreg)
└── factory.py             build_platform_adapters() — the one sys.platform branch
```

Design points:

- **Same Qt-free split as `AppSession` itself.** `PresenceMonitor` only
  depends on the `ActivityProvider` protocol, so the idle/lock/sleep
  decision table (`Technical.md` §13) is fully unit-tested with a fake
  provider — no real Windows or PySide6 needed for that logic. The
  concrete `WindowsActivityProvider`/`WindowsSessionMonitor` (ctypes
  `GetLastInputInfo`, `WTSRegisterSessionNotification` +
  `WM_WTSSESSION_CHANGE`, `WM_POWERBROADCAST`, all constants verified
  against current Microsoft Learn docs rather than guessed) can only run
  on real Windows, so they're the one part of this phase that needs the
  user's machine to actually exercise.
- **`AppSession` polls presence every `tick()`** (not just on platform
  events) — cheap, and it doubles as the `Technical.md` §41 "missed
  event" reconciliation: if a sleep/wake or lock/unlock notification is
  somehow missed, the next real tick re-queries actual idle/lock state
  anyway. Sleep/wake are *also* pushed immediately via
  `AppSession.on_platform_sleep()`/`on_platform_wake()` (called by
  `WindowsSessionMonitor`'s native event filter, on the Qt main thread —
  no extra thread needed) so a suspend is checkpointed before power-down
  and a resume re-queries idle state right away rather than waiting for
  the next tick.
- **Hydration and eye-rest freeze/resume on any ACTIVE ↔ non-ACTIVE
  presence transition**, mirroring what `start_idea_walk()` already did
  explicitly — except deliberately skipped during an actual idea walk
  (which owns that freeze/thaw itself) and eye-rest is skipped unless the
  session is actually `FOCUSING` (a deliberately `PAUSED` session must
  never be silently un-paused by a presence blip).
- **Away-from-computer break credit** (`Technical.md` §14): a presence
  return-to-ACTIVE that clears `BreakEngine.qualifies_as_break()`'s
  180-second floor is recorded as a `BreakSession(kind=AWAY,
  completion_source=IDLE_DETECTED)` — never "walk completed", just what
  was actually observed.
- **Capability detection degrades, never crashes**
  (`PlatformCapabilities`, Implementation Standards.md §14): any adapter
  that fails to construct, or a provider that starts raising at runtime,
  is dropped/disabled and logged rather than propagated — the focus timer
  keeps working with automatic-away detection simply turned off.
- **Launch-at-login is now real.** `WindowsAutostartService` adds/removes
  a per-user `Run` registry value (no admin rights, no service) and
  `bootstrap.py` syncs it once at startup and again on every settings
  change.

**Deliberately not done in this phase:**

- **macOS/Linux adapters** — `activity/base.py`'s protocols are already
  platform-agnostic; only `platform/windows.py` exists so far (Phase 7).
- **Fullscreen/presentation detection and native actionable
  notifications** — both explicitly `Technical.md` §45's "later" list.
- **No automated verification of `platform/windows.py` itself.** It
  imports `winreg`/`ctypes.windll`, which only exist on real Windows, so
  it cannot be imported or exercised in this Linux sandbox at all (unlike
  Phase 4's Qt-only code, which at least byte-compiles and can be
  reasoned about structurally). Verify it manually on the user's machine.

Everything else — `platform/` beyond `windows.py`/`factory.py` — still
exists only as an empty package with a docstring.

## Planned phases

Following `ScreenCare — Implementation Standards.md` §49 (repository
foundation before pure domain logic, before persistence, before the real
desktop shell):

1. **Repository foundation** — done (this document, `pyproject.toml`,
   lint/test setup, bootstrap + placeholder window).
2. **Pure core domain** — done (`Clock`/`FakeClock`, the central scheduler,
   `FocusEngine`, `BreakEngine`, `HydrationEngine`, `EyeRestEngine`,
   `WellnessCoordinator`; see above).
3. **Persistence** — done (`QSettings`, SQLite (WAL mode) + migrations,
   repositories, crash-recovery snapshot/reconciliation; see above).
4. **Desktop UI** — done (`AppSession`, real dashboard/focus/break/settings
   QML views, tray integration, `NotificationService`, quiet mode, view
   models wired to the Phase 2 engines, the database opened and the
   session snapshot checkpointed at real startup; see above).
5. **First platform integration (Windows)** — done (idle detection
   (`GetLastInputInfo`), lock/unlock (`WTSRegisterSessionNotification`),
   sleep/wake (`WM_POWERBROADCAST`), autostart, all behind the
   `activity`/`platform` interfaces; see above).
6. **Packaging** — `pyside6-deploy` / Nuitka standalone build, measured
   against the resource-efficiency targets in the technical spec.
7. **Other operating systems** — macOS/Linux adapters behind the same
   interfaces, once Windows is stable.
8. **Polish** — adaptive-focus tuning, accessibility, theming, dashboard,
   onboarding.

`ScreenCare — Technical.md` §46 orders things slightly differently (core
engine before the desktop shell, full stop). Where the two docs disagree on
sequencing rather than substance, this repo follows the more operationally
specific `Implementation Standards.md` phase list, since it explicitly
requires confirming the app boots and the test/lint setup works before any
further code is added — a good gate to have before building the domain
layer.

## Threading and scheduling

`Scheduler.tick()` is now driven by one `QTimer` on the Qt main thread
(`app/bootstrap.py`) — no per-feature `QTimer`s — at 1 s while the window is
visible and 5 s while hidden in the tray (`Technical.md` §25/§27). Worker
threads (`QThreadPool`/`QThread`) remain reserved for genuinely blocking
work (large exports/analytics) and aren't needed yet — Phase 4's dashboard
queries are cheap enough to run on the main thread, each with its own
SQLite connection via the repositories.

## Notifications

Notifications are an output channel, never a source of truth: the engines
and `AppSession` decide state and persist it first; `NotificationService`
(`notifications/base.py`'s protocol, `notifications/tray_service.py`'s
`QSystemTrayIcon` adapter) merely attempts to display it afterward, and the
app remains correct even if the OS suppresses the notification, no tray
exists at all, or the user has turned on quiet mode.
