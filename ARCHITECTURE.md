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

## What exists today (Phase 1 — repository foundation)

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

Everything else — `domain/`, `engines/`, `scheduler/`, `activity/`,
`notifications/`, `persistence/`, `platform/`, `analytics/`,
`ui/viewmodels/` — exists only as an empty package with a docstring noting
which phase implements it. That's intentional: the target layout from
`ScreenCare — Technical.md` §5 is laid down up front so later phases have an
obvious home, but no logic is invented ahead of the phase that needs it.

## Planned phases

Following `ScreenCare — Implementation Standards.md` §49 (repository
foundation before pure domain logic, before persistence, before the real
desktop shell):

1. **Repository foundation** — done (this document, `pyproject.toml`,
   lint/test setup, bootstrap + placeholder window).
2. **Pure core domain** — `Clock`/`FakeClock`, the central scheduler,
   `FocusEngine`, `BreakEngine`, `HydrationEngine`, `EyeRestEngine`,
   `WellnessCoordinator`. No Qt, no OS APIs — fully unit-testable with an
   injectable clock.
3. **Persistence** — `QSettings`, SQLite (WAL mode) + migrations,
   repositories, crash-recovery snapshot/reconciliation.
4. **Desktop UI** — real dashboard/focus/break/settings QML views, tray
   integration, `NotificationService`, view models wired to the Phase 2
   engines.
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

## Threading and scheduling (not yet implemented)

Per the technical spec: one central scheduler on the Qt main thread, no
per-feature `QTimer`s, deadlines computed from `time.monotonic_ns()` for
runtime correctness and UTC timestamps for persisted history. Worker
threads (`QThreadPool`/`QThread`) are reserved for genuinely blocking work
(large exports/analytics), each with its own SQLite connection.

## Notifications (not yet implemented)

Notifications are an output channel, never a source of truth: the engines
and coordinator decide state and persist it; `NotificationService` merely
attempts to display it, and the app must remain correct even if the OS
suppresses the notification.
