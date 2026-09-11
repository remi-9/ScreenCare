# ScreenCare Technical Specification

> **Purpose:** Implementation blueprint for a Python-centered desktop wellness and focus application that remains reliable in the background, minimizes CPU/battery usage, preserves user privacy, and can grow into Windows, macOS, and Linux support without rewriting the core application.

## 1. Technical Direction

ScreenCare should be built as a **local-first native desktop application**.

The recommended architecture is:

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

The application should **not require a backend server** for its core functionality.

All focus sessions, break data, hydration events, settings, and wellness history should remain on the device by default.

---

## 2. Recommended Technology Stack

### Runtime

- **Python 3.13.x**
- **PySide6 6.11.x / Qt 6.11**
- **Qt Quick + QML** for the visual interface
- Python standard library wherever possible

### Persistence

- **SQLite** through Python's built-in `sqlite3`
- **QSettings** for lightweight application preferences
- **QStandardPaths** for OS-correct storage locations

### Packaging

- **`pyside6-deploy`**
- **Nuitka**
- Prefer a **standalone installed application** over a one-file executable for production

### Testing and quality

- `pytest`
- `pytest-qt`
- `ruff`
- optional static typing with `mypy` or `pyright`

### Platform-specific integration

- **Windows:** Win32 APIs through `ctypes`
- **macOS:** native AppKit/CoreGraphics integration behind a macOS adapter; PyObjC may be used when required
- **Linux:** Qt D-Bus / XDG Desktop Portals / systemd-logind integration where available

Do not allow operating-system-specific code to leak into the focus or wellness logic.

---

## 3. Why Python 3.13 Instead of Automatically Using the Newest Python

As of September 2026, current PySide6 releases support Python 3.10 through 3.14, and current Nuitka releases support Python 3.14.

For the first production release, use **Python 3.13** unless a required dependency specifically benefits from 3.14.

Reason:

- mature ecosystem support;
- avoids introducing a new interpreter version and new application code simultaneously;
- fully supported by current PySide6;
- straightforward Nuitka deployment;
- upgrading to Python 3.14 later should not require architectural changes.

Set the project constraint to:

```toml
requires-python = ">=3.13,<3.14"
```

Re-evaluate this constraint after the packaged application has been tested on all target operating systems.

---

## 4. Dependency Philosophy

ScreenCare is a background utility, so dependency count should remain deliberately small.

Prefer:

```text
Python standard library
        +
PySide6 / Qt
        +
small OS-specific adapter dependencies only when necessary
```

Avoid adding frameworks merely for convenience.

### Do not use for the MVP

- Electron
- React
- FastAPI
- Django
- PostgreSQL
- Redis
- Docker
- Celery
- APScheduler
- a separate Node.js runtime
- a cloud database
- a local HTTP server

None of these are required for ScreenCare's core use case.

---

## 5. Project Layout

Recommended repository structure:

```text
screencare/
├── pyproject.toml
├── README.md
├── LICENSES/
├── resources/
│   ├── icons/
│   ├── sounds/
│   └── fonts/
│
├── src/
│   └── screencare/
│       ├── __init__.py
│       ├── main.py
│       │
│       ├── app/
│       │   ├── bootstrap.py
│       │   ├── lifecycle.py
│       │   └── app_context.py
│       │
│       ├── domain/
│       │   ├── models.py
│       │   ├── enums.py
│       │   └── events.py
│       │
│       ├── engines/
│       │   ├── focus_engine.py
│       │   ├── break_engine.py
│       │   ├── hydration_engine.py
│       │   ├── eye_rest_engine.py
│       │   ├── adaptive_focus.py
│       │   └── wellness_coordinator.py
│       │
│       ├── scheduler/
│       │   ├── scheduler.py
│       │   └── clock.py
│       │
│       ├── activity/
│       │   ├── base.py
│       │   ├── windows.py
│       │   ├── macos.py
│       │   └── linux.py
│       │
│       ├── notifications/
│       │   ├── service.py
│       │   ├── policy.py
│       │   └── models.py
│       │
│       ├── persistence/
│       │   ├── database.py
│       │   ├── migrations.py
│       │   ├── repositories.py
│       │   └── settings.py
│       │
│       ├── platform/
│       │   ├── base.py
│       │   ├── windows.py
│       │   ├── macos.py
│       │   └── linux.py
│       │
│       ├── analytics/
│       │   └── statistics.py
│       │
│       └── ui/
│           ├── qml/
│           │   ├── Main.qml
│           │   ├── Dashboard.qml
│           │   ├── FocusTimer.qml
│           │   ├── BreakView.qml
│           │   ├── IdeaWalk.qml
│           │   ├── Settings.qml
│           │   └── components/
│           └── viewmodels/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── platform/
│   └── ui/
│
└── scripts/
    ├── build.py
    └── smoke_test.py
```

The core rule is:

> **Domain and engine code must not import Windows, macOS, or Linux APIs.**

Platform behavior is injected through interfaces.

---

## 6. Core Application Architecture

ScreenCare should use an **event-driven state machine**, not a collection of independent countdown timers.

### Focus state

```text
STOPPED
   │
   ▼
FOCUSING ─────────────► PAUSED
   │                      │
   │                      └────► FOCUSING
   ▼
RECOVERY_DUE
   │
   ▼
BREAKING
   │
   ▼
READY
```

Additional state:

```text
IDEA_WALK
```

### Presence state

Presence is separate from focus state:

```text
ACTIVE
IDLE
LOCKED
SLEEPING
```

This distinction prevents accidental logic such as:

> "The focus timer ended while the computer was asleep, therefore show three overdue reminders immediately."

Instead, the coordinator can reconcile the state when the user returns.

---

## 7. Central Wellness Coordinator

The most important application component should be:

```python
WellnessCoordinator
```

Its responsibility is to combine competing reminders into one appropriate intervention.

It receives inputs from:

```text
FocusEngine
HydrationEngine
EyeRestEngine
BreakEngine
ActivityMonitor
Scheduler
UserSettings
```

and decides:

```text
notify now
merge reminders
silently defer
mark completed
pause
resume
cancel
```

### Example

State:

```text
Focus session ends in:       6 minutes
Hydration due in:            2 minutes
Movement break due in:       5 minutes
Eye reset completed:        12 minutes ago
```

Do **not** generate three notifications.

Generate one recovery event six minutes later:

```text
Recovery Break

• Step away from the screen
• Walk or move around
• Refill or drink water
• Rest your eyes
```

This reduces notification fatigue and makes the application feel intentional.

---

## 8. Reminder Priority Model

Use four internal priorities.

```text
P0 — informational
P1 — gentle
P2 — normal
P3 — recovery due
```

Suggested mapping:

| Reminder | Priority |
|---|---:|
| eye-rest micro prompt | P0 |
| hydration | P1 |
| posture/movement suggestion | P1 |
| Pomodoro completion | P2 |
| long uninterrupted session | P3 |

The application should never aggressively override the operating system's own Focus / Do Not Disturb rules.

---

## 9. Hydration Scheduling

Default hydration interval:

```text
60 minutes
```

Hydration is based primarily on **wall-clock elapsed time while the user is in the workday**, not the number of keystrokes made.

### Merge behavior

Default:

```text
hydration interval:   60 min
merge window:         10 min
maximum defer:        10 min
```

If a focus recovery break is already scheduled inside the merge window, attach hydration to that recovery break instead of generating another notification.

Example:

```text
55 min — focus session will end in 5 min
60 min — hydration becomes due
60 min — recovery begins
```

Result:

```text
One recovery notification containing hydration.
```

Include a user setting:

```text
Strict hourly hydration reminders: ON/OFF
```

When enabled, hydration reminders are not merged past their due time.

---

## 10. Focus Modes

Implement three focus strategies using the same engine.

### Classic

```text
25 min focus
5 min recovery
```

### Deep Focus

Default:

```text
50 min focus
7–10 min recovery
```

### Adaptive Focus

Do not use machine learning for the MVP.

Use a transparent rules-based model.

Inputs may include:

```text
planned duration
actual active duration
session completion
number of extensions
number of interruptions
break completion
user feedback: too short / right / too long
```

Example adjustment:

```python
if feedback == "too_short" and completion_rate > 0.8:
    next_duration += 5 * 60

elif feedback == "too_long":
    next_duration -= 5 * 60
```

Clamp recommendations to a sensible range.

Example:

```text
minimum focus recommendation: 20 min
maximum focus recommendation: 60 min
```

Keep user-selected manual durations available at all times.

---

## 11. Timer and Scheduler Design

### Do not implement timers by decrementing an integer every second

Avoid:

```python
remaining_seconds -= 1
```

This drifts when:

- the event loop is busy;
- the computer sleeps;
- the application is suspended;
- a timer callback is delivered late.

Instead store deadlines.

Example:

```python
deadline = monotonic_now + duration
remaining = max(0, deadline - monotonic_now)
```

The UI calculates remaining time from the deadline.

### Clock types

Use:

```python
time.monotonic_ns()
```

for measuring elapsed runtime intervals.

Store UTC timestamps in SQLite for durable history and restart reconciliation.

Use both concepts:

```text
monotonic time → runtime duration correctness
UTC wall time  → persistence, history, resume reconciliation
```

### QTimer strategy

Do not create one QTimer for every wellness feature.

Use a central scheduler.

Recommended wake frequency:

```text
Focus timer visible:       1 second
Background / tray mode:    5–15 seconds
Idle monitoring:           5 seconds
Persistence checkpoint:    transitions + at most once/minute
```

Use `Qt.CoarseTimer` for background work.

Use precise timers only where visual countdown precision actually matters.

The focus timer does not need millisecond precision.

---

## 12. Sleep and Resume Handling

Sleep must never be interpreted as focus time.

When sleep is detected:

```text
1. Persist current state.
2. Mark presence = SLEEPING.
3. Stop producing reminders.
4. Do not continue incrementing active-computer duration.
```

On wake:

```text
1. Mark presence appropriately.
2. Reconcile UTC timestamps.
3. Query actual idle state.
4. Decide whether the elapsed absence qualifies as a break.
5. Recalculate future deadlines.
6. Do not replay a queue of stale notifications.
```

### Native sources

Windows:

```text
WM_POWERBROADCAST
PBT_APMSUSPEND
PBT_APMRESUMEAUTOMATIC
PBT_APMRESUMESUSPEND
```

macOS:

```text
NSWorkspace willSleepNotification
NSWorkspace didWakeNotification
```

Linux:

```text
systemd-logind PrepareForSleep
```

Keep these implementations behind:

```python
class PlatformPowerMonitor(Protocol):
    sleep_started: Signal
    wake_completed: Signal
```

---

## 13. User Activity Detection

Do **not** install keyboard hooks.

Do **not** capture keystrokes.

Do **not** inspect typed text.

The application only needs:

```text
seconds since last user input
locked/unlocked state
sleep/wake state
```

### Windows

Use:

```text
GetLastInputInfo
```

through `ctypes`.

It is lightweight and intended for session idle detection.

For lock/unlock events use:

```text
WTSRegisterSessionNotification
WM_WTSSESSION_CHANGE
WTS_SESSION_LOCK
WTS_SESSION_UNLOCK
```

### macOS

Use native session/workspace APIs behind the macOS adapter.

Session activity can be observed through `NSWorkspace` session notifications.

Idle-time implementation should remain separate from session-lock implementation.

### Linux

Linux desktop environments vary significantly.

Prefer:

```text
XDG Desktop Portals
systemd-logind
Qt D-Bus
```

Do not assume X11 APIs are available when running under Wayland.

### Idle threshold

Recommended starting value:

```text
idle threshold: 90 seconds
```

Behavior:

```text
idle < 90 sec     → remain ACTIVE
idle >= 90 sec    → IDLE
locked            → LOCKED
system sleep      → SLEEPING
```

Make the threshold configurable internally even if it is not exposed in the first UI.

---

## 14. Detecting Real Breaks

ScreenCare cannot prove that a person walked around.

Therefore distinguish:

```text
Computer break
Movement break
User-confirmed walk
```

An idle period can automatically confirm:

```text
away-from-computer break
```

but should not be recorded as:

```text
walk completed
```

unless the user explicitly indicates it.

Suggested automatic rule:

```text
away >= 3 minutes
    → qualifies as meaningful computer break
```

If a user walks away before a scheduled break, the coordinator may credit that break and avoid immediately asking for another one.

---

## 15. "Idea Walk" Implementation

Idea Walk is a special break state.

```text
FOCUSING
   │
   ├── user presses "I'm stuck"
   ▼
IDEA_WALK
   │
   ▼
READY / FOCUSING
```

Default duration:

```text
5 minutes
```

During Idea Walk:

- focus timer pauses or completes according to user preference;
- no eye/hydration/movement notifications should fire;
- the application waits for user return;
- after return, optionally show one small note field;
- note storage is local;
- note capture can be disabled for privacy.

Do not require the user to keep the Idea Walk screen open.

---

## 16. Notification Architecture

Notifications must be treated as an **output channel**, not the application's source of truth.

Bad architecture:

```text
notification fired
    ↓
therefore break is due
```

Correct architecture:

```text
BreakEngine says break is due
    ↓
state is persisted
    ↓
NotificationService attempts to notify
```

If the OS suppresses a notification, application state remains correct.

### NotificationService

```python
class NotificationService:
    def send(self, notification: Notification) -> None: ...
    def withdraw(self, notification_id: str) -> None: ...
```

### MVP delivery

Use:

```text
QSystemTrayIcon
```

for simple desktop notifications and tray operation.

Before using it:

```text
QSystemTrayIcon.isSystemTrayAvailable()
QSystemTrayIcon.supportsMessages()
```

Provide an in-app fallback if the system tray is unavailable.

### Important

Qt documents that system configuration and user preferences can prevent tray messages from being displayed.

Therefore:

- never depend on a tray message to advance state;
- keep current status visible through the tray menu;
- show overdue state the next time the user opens ScreenCare;
- optionally provide a small non-intrusive break window for focus completion.

---

## 17. Fullscreen and Do Not Disturb

Do **not** make global fullscreen detection a hard MVP dependency.

Reliable cross-platform detection can require platform-specific APIs and, on some systems, additional permissions.

For the first version:

```text
- respect OS notification behavior;
- provide a manual Quiet Mode;
- provide "Pause reminders for 30/60/120 minutes";
- suppress notifications when ScreenCare itself detects LOCKED/SLEEPING/IDLE.
```

Later, add platform-specific fullscreen detection behind:

```python
class InterruptionContext:
    def should_defer_noncritical(self) -> bool: ...
```

Never read window titles or application content merely to determine whether notifications should be deferred.

---

## 18. System Tray Behavior

ScreenCare should continue running when the main window closes.

Tray menu:

```text
ScreenCare
──────────────
Current: Focus 32:14
Start / Pause Focus
Take a Break
Idea Walk
Drink Water ✓
Quiet for 1 hour
──────────────
Open ScreenCare
Settings
Quit
```

Closing the main window:

```text
hide UI
keep application running
```

Explicit **Quit**:

```text
persist state
close database cleanly
remove tray icon
exit process
```

---

## 19. Persistence Strategy

Use two persistence systems for different purposes.

### QSettings

Use for:

```text
theme
focus defaults
hydration interval
sound preference
notification preference
startup preference
onboarding completion
window position
```

### SQLite

Use for:

```text
focus history
break history
hydration events
symptom check-ins
adaptive-focus feedback
optional idea notes
```

Database location should come from:

```text
QStandardPaths.AppLocalDataLocation
```

Do not manually place files in arbitrary home-directory folders.

---

## 20. SQLite Configuration

On application startup:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 3000;
```

Why:

- WAL allows readers and a writer to operate concurrently;
- SQLite documents `synchronous=NORMAL` as a strong performance/safety balance for many WAL-mode applications;
- ScreenCare data is event/history data rather than financial transaction data;
- losing the last few seconds of wellness state after catastrophic power loss is preferable to excessive synchronous disk writes.

Never use:

```sql
PRAGMA synchronous = OFF;
```

for the production database.

---

## 21. Database Schema

Keep the schema intentionally small.

### focus_sessions

```sql
CREATE TABLE focus_sessions (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    task_label TEXT,
    started_at_utc TEXT NOT NULL,
    ended_at_utc TEXT,
    planned_seconds INTEGER NOT NULL,
    active_seconds INTEGER NOT NULL DEFAULT 0,
    extension_seconds INTEGER NOT NULL DEFAULT 0,
    outcome TEXT,
    feedback TEXT,
    created_at_utc TEXT NOT NULL
);

CREATE INDEX idx_focus_started
ON focus_sessions(started_at_utc);
```

### break_sessions

```sql
CREATE TABLE break_sessions (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    started_at_utc TEXT NOT NULL,
    ended_at_utc TEXT,
    away_seconds INTEGER NOT NULL DEFAULT 0,
    completion_source TEXT,
    created_at_utc TEXT NOT NULL
);

CREATE INDEX idx_break_started
ON break_sessions(started_at_utc);
```

### hydration_events

```sql
CREATE TABLE hydration_events (
    id TEXT PRIMARY KEY,
    occurred_at_utc TEXT NOT NULL,
    action TEXT NOT NULL,
    source TEXT NOT NULL
);

CREATE INDEX idx_hydration_time
ON hydration_events(occurred_at_utc);
```

### symptom_checkins

Optional feature:

```sql
CREATE TABLE symptom_checkins (
    id TEXT PRIMARY KEY,
    occurred_at_utc TEXT NOT NULL,
    headache INTEGER,
    eye_strain INTEGER,
    dry_eyes INTEGER,
    neck_tension INTEGER,
    fatigue INTEGER,
    note TEXT
);
```

Keep symptom tracking optional and disabled by default if it is not necessary for the initial release.

---

## 22. Database Write Policy

Do not update SQLite every second.

Persist:

```text
- when focus begins;
- when focus pauses/resumes;
- when break begins/ends;
- when hydration is logged;
- when user feedback is submitted;
- when application sleeps/quits;
- at most once every ~60 seconds while a session is running.
```

This minimizes I/O and battery impact.

For normal ScreenCare workloads, synchronous SQLite access is sufficiently small to remain on the application thread if transactions are short.

If analytics/export operations later become expensive, move those queries to a worker thread with its **own SQLite connection**.

Do not share one connection freely across threads.

---

## 23. Crash Recovery

Persist a lightweight active-session snapshot.

On startup:

```text
Was a session active when ScreenCare closed unexpectedly?
             │
       ┌─────┴─────┐
       │           │
      yes          no
       │           │
       ▼           ▼
reconcile time   normal start
```

Rules:

```text
restart within ~2 minutes
    → offer Resume Session

longer unexplained gap
    → close previous session as interrupted

system sleep recorded
    → exclude sleep interval from active focus
```

Never automatically claim that an unfinished focus session was completed.

---

## 24. UI Architecture

Use QML for presentation and Python for behavior.

Bad:

```qml
Timer {
    interval: 1000
    onTriggered: {
        remainingSeconds--
        // business logic
    }
}
```

Preferred:

```text
QML
  ↓ calls / observes
Python ViewModel
  ↓
FocusEngine
  ↓
Scheduler + persisted state
```

QML should display state, not own business rules.

### Expose narrow view models

Examples:

```text
FocusViewModel
DashboardViewModel
SettingsViewModel
BreakViewModel
```

Do not expose the entire database or coordinator directly to QML.

---

## 25. UI Performance

Avoid constantly rebuilding large QML object trees.

Guidelines:

- use properties and bindings rather than recreating components;
- animate only small UI elements;
- stop animations when the window is hidden;
- update the visible countdown once per second;
- do not redraw charts while the application is in tray-only mode;
- lazy-load statistics pages;
- load long-history queries only when requested.

The tray-only application should perform almost no rendering work.

---

## 26. Threading Model

Default:

```text
Main Qt thread
├── state machine
├── scheduler
├── small SQLite transactions
├── tray
└── UI
```

Use workers only for operations that can genuinely block:

```text
large exports
large analytics rebuilds
future network update checks
large imports
```

Use:

```text
QThreadPool / QRunnable
```

or a dedicated `QThread`.

Do not use:

```text
threading.Timer
```

for application scheduling.

Do not mix `asyncio` into the application unless a future feature clearly requires asynchronous network I/O.

---

## 27. Resource-Efficiency Targets

These are engineering targets, not guarantees.

On a typical supported desktop while ScreenCare is hidden in the tray:

```text
Idle CPU average:        target < 0.5%
Active timer CPU:        target < 1%
Memory:                  target < 150 MB
Idle polling:            no faster than every 5 sec
Database session writes: <= 1/minute except transitions
Network traffic:         zero for core app
```

Measure these targets on packaged builds, not only from the development interpreter.

Battery-conscious behavior:

```text
UI hidden
    → stop visual animations
    → use coarse scheduler wakeups
    → do not recalculate analytics
    → do not run unnecessary polling
```

---

## 28. Privacy Requirements

ScreenCare should **not** collect:

```text
keystrokes
screenshots
clipboard contents
browser history
document contents
window contents
camera data
microphone data
```

The activity monitor should answer questions such as:

```text
Is the user active?
How long have they been idle?
Is the session locked?
Did the computer sleep?
```

and nothing more.

Optional task labels and Idea Walk notes are user-entered data and remain local.

No cloud account should be required for the MVP.

---

## 29. Logging

Use Python's built-in `logging`.

Recommended rotating log:

```text
maximum file size: 2–5 MB
retained files:    2–3
```

Log:

```text
application start/stop
state transitions
platform adapter failures
database migration failures
notification delivery attempts
uncaught exceptions
```

Do not log:

```text
Idea Walk notes
symptom notes
task text
other private user-entered content
```

unless explicitly running a developer/debug build.

---

## 30. Settings Validation

All user-configurable durations should have safe bounds.

Example:

```text
focus duration:      10–120 min
short break:          1–30 min
hydration interval:  30–180 min
eye reminder:        10–60 min
quiet mode:          15–240 min
```

The UI may recommend narrower ranges, but the model should validate all inputs.

Never trust QML input values directly.

---

## 31. Platform Capability Interface

Define explicit capabilities.

```python
@dataclass(frozen=True)
class PlatformCapabilities:
    idle_detection: bool
    lock_detection: bool
    sleep_detection: bool
    native_notifications: bool
    tray_available: bool
    autostart: bool
    fullscreen_detection: bool
```

At runtime:

```text
detect capability
      │
      ├── supported → enable feature
      │
      └── unavailable → graceful fallback
```

Do not crash because a Linux desktop lacks a tray implementation or portal.

---

## 32. Windows Adapter

Recommended first-class support.

Use standard APIs through Python `ctypes` where practical.

Responsibilities:

```text
GetLastInputInfo          → idle duration
WTS session messages     → lock / unlock
WM_POWERBROADCAST         → sleep / wake
Qt tray / notification   → reminder presentation
```

Avoid installing:

```text
global keyboard hooks
global mouse hooks
background input capture
```

They are unnecessary.

---

## 33. macOS Adapter

Responsibilities:

```text
NSWorkspace session notifications
NSWorkspace sleep/wake notifications
idle-duration provider
menu-bar/tray integration
```

macOS permissions should be minimized.

Do not request Accessibility, Screen Recording, Camera, or Microphone permissions unless a later feature genuinely requires them.

ScreenCare's core feature set should be designed to work without those intrusive permissions.

Production distribution should use:

```text
Apple code signing
notarization
signed .app bundle
```

---

## 34. Linux Adapter

Linux should be treated as a capability-based platform because desktop environments differ.

Preferred integration:

```text
Qt
XDG Desktop Portals
D-Bus
systemd-logind where available
```

Use portals where appropriate for:

```text
notifications
background permission
autostart
session monitoring
```

Do not architect the application around X11-only techniques.

Wayland must be considered a normal target environment.

---

## 35. Startup / Background Launch

"Launch at login" should be optional.

Implement behind:

```python
class AutostartService:
    def is_enabled(self) -> bool: ...
    def enable(self) -> None: ...
    def disable(self) -> None: ...
```

Never make core application logic depend on the exact autostart mechanism.

On first install:

```text
Launch ScreenCare at login?
[Enable] [Not now]
```

The user must be able to disable it later.

---

## 36. Packaging Strategy

Use Qt's supported deployment tooling as the default path:

```text
pyside6-deploy
        ↓
      Nuitka
        ↓
platform-specific application
```

Current Qt documentation recommends `pyside6-deploy` for PySide6 desktop deployment and describes it as a Nuitka-based deployment tool.

### Prefer standalone mode for production

Although one-file distribution is convenient, an installed standalone bundle is preferable for ScreenCare because:

- Qt plugin/resource discovery is easier to inspect;
- startup does not depend on extracting a large application bundle each run;
- updates can replace application files through an installer;
- failures are easier to diagnose;
- antivirus/security tooling generally has a clearer installed application layout.

Example deployment configuration concept:

```ini
[nuitka]
mode = standalone
```

Use `pysidedeploy.spec` to explicitly exclude QML/Qt plugins that ScreenCare does not use.

Avoid bundling:

```text
QtWebEngine
QtMultimedia
Qt3D
```

unless a feature actually requires them.

This can materially reduce package size.

---

## 37. Build Matrix

Native desktop builds should be produced on their corresponding operating systems.

CI matrix:

```text
Windows runner
    → Windows package

macOS runner
    → signed macOS application

Linux runner
    → Linux package
```

Every release build should run:

```text
unit tests
integration tests
database migration tests
QML load smoke test
packaged-app startup test
```

---

## 38. Version Pinning

Do not ship from unconstrained dependencies.

Example:

```toml
[project]
name = "screencare"
version = "0.1.0"
requires-python = ">=3.13,<3.14"

dependencies = [
    "PySide6==6.11.2",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-qt",
    "ruff",
]
```

Platform-specific dependencies should use environment markers or separate dependency groups.

Upgrade dependencies deliberately after CI and packaged smoke tests pass.

---

## 39. Database Migrations

Do not introduce a heavy ORM merely for migrations.

Use a small migration table:

```sql
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL
);
```

Migration files can be Python functions:

```text
001_initial.py
002_add_feedback.py
003_add_symptoms.py
```

Every migration must be:

```text
versioned
transactional where possible
covered by a test
```

---

## 40. Testing Strategy

### Unit tests

Test pure logic without Qt where possible.

Examples:

```text
hydration merge window
adaptive duration rules
break qualification
notification suppression
deadline calculation
sleep reconciliation
state-machine transitions
```

### Scheduler tests

Never make tests actually wait 25 minutes.

Inject a clock:

```python
class Clock(Protocol):
    def monotonic_ns(self) -> int: ...
    def utc_now(self) -> datetime: ...
```

Production:

```text
SystemClock
```

Tests:

```text
FakeClock
```

Then:

```python
clock.advance(minutes=50)
scheduler.tick()
```

Tests run instantly and deterministically.

### Platform tests

Mock native APIs in normal CI.

Run a small number of real native integration tests on each OS runner.

### UI tests

Test:

```text
QML loads
main view opens
focus start button works
pause state appears
settings bindings work
break view can be dismissed
```

Do not attempt to prove all business logic through UI tests.

---

## 41. Required Failure Handling

The app should degrade gracefully.

### Database unavailable

```text
show recoverable error
attempt safe reopen
do not crash-loop
```

### Tray unavailable

```text
keep main window available
disable tray-only close behavior
```

### Idle API fails

```text
continue focus timer
disable automatic-away detection
log adapter failure
```

### Notification unavailable

```text
keep internal state correct
show notification inside app when visible
```

### System resume event missed

The scheduler must still notice a large discrepancy between expected ticks and current UTC time and trigger reconciliation.

---

## 42. Performance-Safe Analytics

Do not continuously recompute the dashboard.

Dashboard queries should run:

```text
when dashboard opens
after a relevant completed event
when user changes date range
```

Useful indexes:

```text
focus_sessions(started_at_utc)
break_sessions(started_at_utc)
hydration_events(occurred_at_utc)
symptom_checkins(occurred_at_utc)
```

For an MVP, SQLite can aggregate weeks or months of this event volume comfortably without a separate analytics database.

---

## 43. Data Retention

Default:

```text
keep local history until user deletes it
```

Provide:

```text
Delete all history
Export data
Reset settings
```

Optional future setting:

```text
Auto-delete detailed history after N months
```

Do not silently upload or sync wellness data.

---

## 44. Update Strategy

Do not build an auto-update system into the MVP.

First release:

```text
manual version check
official release download
signed installer
```

Later:

```text
optional update checker
signed update metadata
verified package signature
```

An update mechanism is security-sensitive and should not be improvised.

---

## 45. Recommended MVP Scope

### Build now

```text
✓ system tray
✓ Classic Pomodoro
✓ Deep Focus
✓ basic Adaptive Focus
✓ hourly hydration scheduling
✓ hydration/break merging
✓ eye-rest micro prompts
✓ idle detection
✓ automatic away-from-computer break credit
✓ sleep/resume reconciliation
✓ Idea Walk
✓ quiet mode
✓ SQLite history
✓ daily/weekly dashboard
✓ local settings
```

### Build after the core is stable

```text
○ native actionable notifications
○ launch-at-login on every OS
○ advanced fullscreen/presentation detection
○ symptom correlation
○ richer adaptive algorithm
○ automatic updates
○ cloud synchronization
○ mobile companion
```

---

## 46. Implementation Order

### Phase 1 — Core engine

```text
Clock abstraction
Scheduler
Focus state machine
Break engine
Hydration engine
WellnessCoordinator
Unit tests
```

No UI should be required to validate these pieces.

### Phase 2 — Persistence

```text
QSettings
SQLite
migrations
session recovery
statistics queries
```

### Phase 3 — Desktop shell

```text
PySide6 application
QML
tray
basic notifications
```

### Phase 4 — OS integration

Start with the developer's primary operating system.

Implement:

```text
idle
lock/unlock
sleep/wake
```

Then implement the same abstract interface for other platforms.

### Phase 5 — Packaging

```text
pyside6-deploy
Nuitka standalone build
installer
CI smoke testing
```

### Phase 6 — Polish

```text
adaptive-focus tuning
accessibility
theme
dashboard
onboarding
performance profiling
```

---

## 47. Acceptance Criteria

The MVP should not be considered complete until these scenarios work.

### Timer correctness

```text
Start a 25-minute session
sleep computer for 30 minutes
wake computer
```

Expected:

```text
sleep is not counted as 30 minutes of focused computer use
no burst of stale reminders occurs
state remains valid
```

### Natural break

```text
work 45 minutes
walk away for 6 minutes before break notification
return
```

Expected:

```text
away period is recognized
app does not immediately demand another break
```

### Hydration merge

```text
hydration due in 4 minutes
focus recovery due in 6 minutes
```

Expected:

```text
one combined recovery notification
```

### Notification failure

```text
OS suppresses notification
```

Expected:

```text
internal state remains correct
dashboard reflects due/completed state
```

### Restart

```text
app closes unexpectedly during focus
restart shortly afterwards
```

Expected:

```text
session can be reconciled without inventing completed work
```

### Tray mode

```text
main window hidden for 8 hours
```

Expected:

```text
low CPU usage
no continuous rendering
timers remain correct
database remains healthy
```

---

## 48. Architecture Rules for Claude / AI Coding Agents

When implementing ScreenCare, follow these rules strictly:

1. **Do not place business logic in QML.**
2. **Do not create independent timers for every reminder.**
3. **Do not use decrementing counters as the source of timer truth.**
4. **Do not record keyboard input, screenshots, clipboard contents, or application content.**
5. **Do not add a server unless a future feature genuinely requires one.**
6. **Do not add large dependencies when Qt or the Python standard library already provides the capability.**
7. **All OS-specific behavior must be behind an interface.**
8. **Every scheduled behavior must remain correct across sleep, idle, lock, restart, and delayed callbacks.**
9. **Notification delivery must never be the source of application state.**
10. **Persist transitions, not every timer tick.**
11. **Use capability detection and graceful fallbacks.**
12. **Optimize notification count before adding more reminders.**
13. **Test time-dependent logic with an injectable fake clock.**
14. **Keep the application functional offline.**
15. **Treat privacy and low resource consumption as product requirements, not later optimizations.**

---

# Research Basis

The recommendations above were checked against current official documentation available in September 2026.

### Qt / PySide6

- Qt for Python is Qt's official Python binding.
- Current PySide6 6.11 releases support CPython 3.10 through 3.14.
- Qt recommends `pyside6-deploy` for desktop deployment.
- `pyside6-deploy` is a wrapper around Nuitka.
- Qt's deployment configuration can exclude unused QML plugins.
- `QTimer` supports coarse timer modes specifically intended to reduce unnecessary wakeups.
- `QSystemTrayIcon` is supported across Windows, macOS, and compatible Linux desktop environments, but Qt warns that notification display depends on OS/user configuration.
- `QSettings` provides platform-independent application preferences.
- `QStandardPaths` provides platform-correct application data paths.

References:

- Qt for Python: https://doc.qt.io/qtforpython-6/
- PySide6 package: https://pypi.org/project/PySide6/
- Qt deployment: https://doc.qt.io/qtforpython-6/deployment/
- `pyside6-deploy`: https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html
- QTimer: https://doc.qt.io/qt-6/qtimer.html
- QSystemTrayIcon: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html
- QSettings: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSettings.html
- QStandardPaths: https://doc.qt.io/qt-6/qstandardpaths.html

### Nuitka

Current Nuitka releases support Python 3.14 and include PySide6 integration.

References:

- Nuitka current release: https://nuitka.net/changelog/Changelog.html
- Nuitka user manual: https://nuitka.net/user-documentation/user-manual.html

### Python timing

Python documents `time.monotonic_ns()` as a monotonic clock suitable for elapsed-time measurements without float precision loss.

Reference:

- Python `time`: https://docs.python.org/3/library/time.html

### SQLite

SQLite documents WAL mode as allowing readers and a writer to operate concurrently. Its documentation describes `synchronous=NORMAL` as a strong performance/safety balance for most WAL-mode applications, while noting that the most recent transaction can be lost after a system power failure even though database consistency is maintained.

References:

- SQLite WAL: https://www.sqlite.org/wal.html
- SQLite PRAGMA documentation: https://www.sqlite.org/pragma.html

### Windows

Microsoft documents `GetLastInputInfo` specifically as useful for input idle detection. Windows session-change messages expose lock/unlock events, while `WM_POWERBROADCAST` exposes suspend/resume events.

References:

- GetLastInputInfo: https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-getlastinputinfo
- WTSRegisterSessionNotification: https://learn.microsoft.com/windows/win32/api/wtsapi32/nf-wtsapi32-wtsregistersessionnotification
- WM_WTSSESSION_CHANGE: https://learn.microsoft.com/windows/win32/termserv/wm-wtssession-change
- WM_POWERBROADCAST: https://learn.microsoft.com/windows/win32/power/wm-powerbroadcast

### macOS

Apple's `NSWorkspace` exposes session activation/deactivation and sleep/wake notifications suitable for background desktop applications.

Reference:

- NSWorkspace: https://developer.apple.com/documentation/appkit/nsworkspace

### Linux

XDG Desktop Portals expose APIs for notifications, background activity, session monitoring, and autostart in desktop environments, while systemd-logind exposes sleep preparation and idle state where available.

References:

- XDG Desktop Portal documentation: https://flatpak.github.io/xdg-desktop-portal/docs/
- systemd-logind: https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html

---

## Final Recommended Stack

```text
Python 3.13
PySide6 6.11 / Qt 6.11
Qt Quick + QML
Qt event loop
Central deadline-based scheduler
Python time.monotonic_ns()
SQLite WAL
QSettings
QStandardPaths
Native OS activity adapters
QSystemTrayIcon + notification abstraction
pytest + pytest-qt
pyside6-deploy + Nuitka
platform-native signed installer
```

This architecture keeps ScreenCare:

```text
local
private
efficient
testable
cross-platform by design
resilient to sleep/idle/restarts
easy to extend
```
