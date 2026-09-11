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

Everything else — `activity/`, `notifications/`, `platform/`,
`analytics/`, `ui/viewmodels/` — still exists only as an empty package
with a docstring noting which phase implements it.

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
4. **Desktop UI** — real dashboard/focus/break/settings QML views, tray
   integration, `NotificationService`, view models wired to the Phase 2
   engines, and the wiring this phase deferred: opening the real database
   at startup, checkpointing the session snapshot, resolving the real
   settings backend.
5. **First platform integration (Windows)** — idle detection
   (`GetLastInputInfo`), lock/unlock (`WTSRegisterSessionNotification`),
   sleep/wake (`WM_POWERBROADCAST`), all behind the `activity`/`platform`
   interfaces.
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

The scheduler/engine layer (Phase 2, above) implements the deadline
mechanics; what's not yet implemented is wiring `Scheduler.tick()` to an
actual Qt event loop. Per the technical spec, that will be one central
scheduler ticked from the Qt main thread — no per-feature `QTimer`s — with
coarse tick intervals when the app is backgrounded (Phase 4). Worker
threads (`QThreadPool`/`QThread`) are reserved for genuinely blocking work
(large exports/analytics, Phase 3+), each with its own SQLite connection.

## Notifications (not yet implemented)

Notifications are an output channel, never a source of truth: the engines
and coordinator decide state and persist it; `NotificationService` merely
attempts to display it, and the app must remain correct even if the OS
suppresses the notification.
