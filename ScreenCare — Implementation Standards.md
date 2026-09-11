# ScreenCare — Implementation Instructions

You are responsible for designing and implementing **ScreenCare**, a privacy-first desktop wellness and focus application.

Before writing or modifying any code, read the following project-context documents completely:

- `ScreenCare — Concept.md`
- `ScreenCare — Technical.md`

Treat those documents as the primary source of truth for the product vision and technical architecture.

If this prompt and the context documents appear to conflict, prefer the technical architecture in `ScreenCare — Technical.md` unless doing so would create a security, reliability, compatibility, or maintainability problem. In that case, explain the conflict briefly before choosing the safer design.

The objective is to produce a desktop application that is:

- reliable during all-day background use;
- efficient in CPU, memory, battery, and disk usage;
- privacy-first and local-first;
- easy to install and run;
- easy for another developer to understand;
- secure by default;
- resilient to crashes, sleep, wake, lock, unlock, idle periods, and restarts;
- visually polished but technically simple;
- modular enough for Windows, macOS, and Linux;
- non-invasive and unlikely to interfere with any other application or normal operating-system behavior.

---

# 1. Development Philosophy

Build ScreenCare as a **small, disciplined desktop application**, not as an unnecessarily complex distributed system.

Prefer:

```text
simple
explicit
testable
local
deterministic
maintainable
```

over:

```text
clever
over-engineered
dependency-heavy
cloud-dependent
difficult to debug
```

Do not introduce additional frameworks, services, runtimes, databases, or abstractions unless they solve a concrete problem.

Before adding any dependency, ask:

1. Can Python's standard library already solve this?
2. Can Qt already solve this?
3. Is this dependency actively maintained?
4. Does it materially improve reliability or maintainability?
5. Does it introduce permissions, background services, networking, or security risk?
6. Will it complicate packaging?

If the benefit is marginal, do not add it.

---

# 2. Target Architecture

Use the architecture defined in the technical specification.

The primary stack should remain:

```text
Python 3.13
PySide6 / Qt 6
Qt Quick / QML
SQLite
QSettings
QStandardPaths
pytest
pytest-qt
pyside6-deploy
Nuitka
```

Use Python for:

- application state;
- focus logic;
- hydration logic;
- recovery/break logic;
- activity monitoring;
- scheduling;
- persistence;
- adaptive focus behavior;
- platform abstractions;
- statistics;
- notification decisions.

Use QML primarily for:

- visual presentation;
- user interaction;
- bindings to view models;
- lightweight animation.

Do not move business rules into QML.

---

# 3. Core Architectural Rule

The application must be based around a **central event/state system**, not many independent timers.

Preferred flow:

```text
Operating System
      │
      ▼
Activity / Power / Session Adapters
      │
      ▼
Central Scheduler
      │
      ▼
Focus / Break / Hydration / Eye-Rest Engines
      │
      ▼
WellnessCoordinator
      │
      ├────────► NotificationService
      │
      ├────────► Persistence
      │
      └────────► View Models
                        │
                        ▼
                       QML
```

`WellnessCoordinator` should be responsible for deciding whether multiple events should:

- fire now;
- merge;
- defer;
- cancel;
- silently resolve;
- become part of a recovery break.

Avoid notification spam.

For example, if hydration is due within a few minutes of a scheduled focus break, combine them into one recovery event.

---

# 4. Safety: Do Not Interfere With Other Applications

ScreenCare must behave as a cooperative desktop application.

It must **never** intentionally:

- capture keyboard input;
- install global keyboard hooks;
- install global mouse hooks;
- intercept user keystrokes;
- alter keyboard shortcuts belonging to other applications;
- capture screenshots;
- read screen contents;
- inspect document contents;
- read clipboard contents;
- monitor browser history;
- inspect private application content;
- inject code into other processes;
- modify other processes;
- suspend other applications;
- block other applications;
- force-close applications;
- manipulate other windows without explicit user action;
- alter system-wide power settings;
- alter global notification settings;
- disable operating-system security features;
- bypass operating-system Focus / Do Not Disturb modes;
- require administrator/root privileges for normal operation;
- create privileged background daemons unnecessarily.

ScreenCare may observe only the minimum information needed for its purpose, such as:

```text
time since last user input
session locked/unlocked
system sleeping/waking
application's own state
```

Do not infer or collect more information than necessary.

---

# 5. Permission Minimization

Design the normal application so that it runs as a standard user.

Do not request:

```text
administrator privileges
root privileges
Accessibility permission
Screen Recording permission
Camera permission
Microphone permission
Location permission
Contacts permission
```

unless a future explicitly approved feature requires one.

If a feature would require a sensitive permission, first determine whether a less invasive implementation exists.

Prefer losing a convenience feature over requesting an excessive permission.

---

# 6. Privacy

ScreenCare is local-first.

Unless explicitly added later, the core application should make:

```text
zero network requests
```

Normal operation must not require:

- an account;
- authentication;
- cloud storage;
- telemetry;
- remote analytics;
- advertising;
- online APIs.

Do not silently introduce telemetry.

Do not use third-party analytics SDKs.

User data should stay in the application data directory.

Do not log sensitive user-provided information.

Specifically, logs must not contain:

```text
task descriptions
Idea Walk notes
symptom notes
private user text
```

Application logs may contain:

```text
state transitions
timestamps
errors
platform capability failures
database errors
notification attempts
version/build information
```

---

# 7. Timer Correctness

Never use decrementing integer counters as the source of truth.

Avoid logic such as:

```python
remaining_seconds -= 1
```

Use deadlines and elapsed time.

Use:

```python
time.monotonic_ns()
```

for runtime elapsed-duration measurement.

Use UTC wall-clock timestamps for:

- database history;
- restart reconciliation;
- reporting;
- persisted sessions.

Timers must remain logically correct when:

- callback delivery is delayed;
- the main thread briefly stalls;
- the laptop sleeps;
- the computer wakes;
- the application is minimized;
- the user locks the workstation;
- the process restarts.

The displayed timer may update once per second, but timer truth should not depend on receiving one callback every second.

---

# 8. Central Scheduling

Do not create dozens of independent `QTimer` instances.

Use one central scheduling mechanism responsible for upcoming deadlines.

Use coarse timers for background scheduling where appropriate.

When ScreenCare is hidden in the tray:

- reduce timer frequency;
- stop unnecessary animations;
- avoid dashboard recalculation;
- avoid unnecessary database queries;
- avoid unnecessary disk writes.

The application should wake only when useful.

---

# 9. Resource Efficiency

Treat efficiency as a product requirement.

Target approximately:

```text
Tray/background CPU average: < 0.5%
Active timer CPU:            < 1%
Memory target:                < 150 MB
Network activity:             0 for core operation
Idle polling:                 approximately every 5 seconds or slower
Database writes:              state transitions + occasional checkpoint
```

These are engineering targets rather than guarantees.

Measure performance using packaged production builds.

Do not optimize prematurely at the cost of correctness, but avoid obvious waste.

Examples of unacceptable behavior:

```text
polling every 100 ms
writing timer values to SQLite every second
recomputing dashboard analytics continuously
running hidden QML animations all day
constantly scanning processes/windows
performing filesystem scans
```

---

# 10. Persistence

Use:

```text
QSettings
```

for simple preferences.

Use:

```text
SQLite
```

for historical/application data.

Store files using paths obtained through:

```text
QStandardPaths
```

Do not create arbitrary files directly in the user's home folder.

Recommended SQLite configuration:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 3000;
```

Keep database transactions short.

Do not write timer state every second.

Persist meaningful transitions such as:

```text
focus start
pause
resume
focus end
break start
break end
hydration event
sleep
shutdown
important preference changes
periodic session checkpoint
```

---

# 11. Database Discipline

Keep the database schema small.

Do not introduce an ORM unless the project's complexity eventually justifies one.

Use explicit SQL repositories.

Provide versioned migrations.

Every migration should:

- have a version number;
- be deterministic;
- be transactional where possible;
- have a test;
- never silently destroy existing user data.

Database errors must fail gracefully.

A corrupted or unavailable database must not create an infinite crash loop.

---

# 12. Threading

Keep most logic on the Qt main thread because the application workload should be small.

Do not introduce background threads without need.

Use worker threads only for genuinely blocking operations such as:

- large exports;
- future network requests;
- expensive analytics over very large histories.

When workers are needed, prefer:

```text
QThreadPool
QRunnable
QThread
```

Do not use `threading.Timer` as the scheduling system.

Do not add asyncio unless a future feature genuinely requires substantial asynchronous I/O.

Never share one SQLite connection casually between threads.

Each worker performing database operations should obtain its own connection.

---

# 13. OS Integration

Hide all platform-specific functionality behind clean interfaces.

For example:

```python
class ActivityProvider(Protocol):
    def idle_seconds(self) -> float: ...
    def is_locked(self) -> bool: ...
```

```python
class PowerMonitor(Protocol):
    ...
```

```python
class AutostartService(Protocol):
    ...
```

Implement:

```text
WindowsAdapter
MacOSAdapter
LinuxAdapter
```

Core logic must not contain:

```python
if sys.platform == ...
```

spread throughout the codebase.

Keep those checks concentrated in bootstrap/factory code.

---

# 14. Graceful Capability Detection

Not every desktop environment supports every capability.

Represent this explicitly.

Example:

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

Unsupported optional features must degrade gracefully.

For example:

```text
idle API unavailable
    ↓
disable automatic away detection
    ↓
focus system continues working normally
```

Never crash because an optional desktop integration is unavailable.

---

# 15. Windows

On Windows, prefer standard Windows APIs rather than third-party monitoring libraries.

Appropriate APIs include:

```text
GetLastInputInfo
WTS session notifications
WM_WTSSESSION_CHANGE
WM_POWERBROADCAST
```

Use them through a small isolated adapter.

Do not install Windows services for the MVP.

Do not use elevated privileges.

Do not install global input hooks.

---

# 16. macOS

Use native macOS workspace/session notifications where appropriate.

Keep permissions minimal.

Do not require Accessibility or Screen Recording permission for core ScreenCare features.

Support proper application lifecycle behavior.

Production packaging should eventually use:

```text
code signing
notarization
proper .app bundle
```

---

# 17. Linux

Linux support must be capability-based.

Do not assume X11.

Treat Wayland as a normal environment.

Prefer:

```text
Qt
XDG Desktop Portals
D-Bus
systemd-logind where appropriate
```

Do not make desktop-specific behavior a hard requirement for core functionality.

---

# 18. Notifications

Notifications are presentation, not state.

Correct:

```text
BreakEngine decides break is due
        ↓
state persisted
        ↓
NotificationService attempts delivery
```

Incorrect:

```text
notification appears
        ↓
therefore break is due
```

Operating systems may suppress notifications.

The application must remain correct regardless.

Use one notification abstraction.

Avoid notification spam.

Respect system Focus / Do Not Disturb behavior rather than trying to bypass it.

---

# 19. Focus Modes

Implement the focus behavior described in the context documents.

At minimum:

```text
Classic Pomodoro
Deep Focus
Adaptive Focus
```

Adaptive Focus should initially use deterministic rules rather than machine learning.

Make its behavior explainable and predictable.

Never prevent the user from selecting their own duration.

Use conservative boundaries for automated recommendations.

---

# 20. Recovery Behavior

Focus sessions should integrate with:

```text
hydration
movement
eye rest
away-from-computer time
```

A recovery break should ideally consolidate these needs.

Example:

```text
Focus Complete

Time for a reset.

• Leave the screen
• Walk around
• Get some water
• Relax your eyes
```

Do not generate separate overlapping reminders when one consolidated intervention is sufficient.

---

# 21. Hydration

Hydration reminders should default to approximately hourly behavior as specified in the project context.

Allow personalization.

Do not prescribe a medically universal quantity of water.

Hydration should be mergeable into a nearby focus/recovery break.

Provide a strict-reminder option for users who prefer exact hourly notifications.

---

# 22. Eye-Rest Reminders

Eye-rest prompts should be subtle.

They should not aggressively interrupt a focus session.

Prefer a lightweight visual prompt.

Users must be able to:

```text
disable
customize
snooze
```

these reminders.

Do not make medical claims.

---

# 23. Activity and Break Recognition

ScreenCare may infer:

```text
computer inactivity
```

but must not claim to know exactly what the user did.

Example:

```text
6 minutes idle
```

may be recorded as:

```text
away-from-computer break
```

but not automatically as:

```text
walking exercise
```

unless confirmed by the user.

Avoid overstating sensor certainty.

---

# 24. Sleep / Wake

Sleep handling is mandatory.

When sleep begins:

```text
persist current state
suspend wellness notifications
exclude sleep from active-computer time
```

On resume:

```text
reconcile persisted timestamps
query current idle state
determine whether absence counts as a recovery break
recalculate deadlines
discard stale notification events
```

Never emit several overdue reminders immediately after wake.

---

# 25. Lock / Unlock

When the user locks their workstation:

```text
treat user as away
suppress normal wellness notifications
```

When they return:

```text
reconcile away duration
credit meaningful breaks where appropriate
continue from correct state
```

Do not assume workstation lock always means sleep.

---

# 26. Crash Recovery

ScreenCare should recover cleanly from an unexpected process exit.

Persist enough state to recognize an active session after restart.

On restart:

- do not invent completed focus time;
- do not assume unfinished sessions succeeded;
- reconcile using timestamps;
- offer a reasonable resume path when appropriate.

Crash recovery code must itself be simple and deterministic.

---

# 27. User Interface

The UI should feel:

```text
calm
minimal
modern
non-clinical
non-intrusive
```

Avoid clutter.

The application should not resemble enterprise monitoring software.

Prioritize:

```text
current state
time remaining
next recovery
start/pause controls
quick wellness actions
```

over excessive statistics.

Use accessibility-friendly:

- readable contrast;
- scalable text;
- keyboard navigation where reasonable;
- clear focus states;
- descriptive labels;
- reduced-motion-friendly behavior.

---

# 28. Tray Behavior

ScreenCare should normally remain available from the system tray/menu bar.

Closing the main window should normally:

```text
hide application window
keep ScreenCare running
```

Explicit Quit should:

```text
persist state
close database
remove tray icon
exit cleanly
```

If a system tray is unavailable, fall back to normal window behavior.

Never make the user unable to quit the application.

---

# 29. Startup Behavior

Launch-at-login should be:

```text
optional
transparent
easy to disable
```

Do not silently enable it.

Do not require startup persistence for ScreenCare to work.

Keep autostart behavior behind an abstraction.

---

# 30. Configuration

Validate every setting in Python.

Do not trust raw QML values.

Reasonable constraints should exist for:

```text
focus duration
break duration
hydration interval
eye-rest interval
quiet-mode duration
```

Invalid configuration should fall back safely.

Configuration corruption must not prevent application startup.

---

# 31. Error Handling

Errors should be handled deliberately.

Do not use broad exception suppression such as:

```python
try:
    ...
except Exception:
    pass
```

unless there is an extremely specific reason and a log entry.

At subsystem boundaries:

- catch expected failures;
- log useful technical details;
- present simple user-facing messages;
- preserve application stability.

Unexpected exceptions should reach a central logging mechanism.

---

# 32. Logging

Use Python's built-in `logging`.

Use rotating files.

Avoid excessive logs during normal operation.

Log:

```text
startup
shutdown
version
database migration
state transitions when useful
platform adapter failures
unexpected exceptions
packaging/runtime environment where useful
```

Never log private user content.

---

# 33. Code Quality Standards

Write production-quality Python.

Use:

- clear types;
- dataclasses where useful;
- enums for meaningful states;
- protocols/interfaces for platform boundaries;
- small functions;
- explicit return types on public APIs;
- descriptive names;
- docstrings where behavior is not obvious.

Avoid:

- enormous manager classes;
- unnecessary inheritance;
- magic global state;
- circular imports;
- hidden side effects;
- mutable module-level state;
- duplicate business logic;
- deeply nested conditionals.

Aim for functions that can be understood without reading the entire project.

---

# 34. Type Safety

Use type hints throughout important application and domain code.

Run a type checker during development.

Avoid unnecessary `Any`.

Platform-specific APIs may require localized exceptions, but do not allow weak typing to spread across the codebase.

---

# 35. Formatting and Linting

Configure:

```text
ruff
```

for linting and formatting.

The repository should have one documented command that checks code quality.

Example:

```bash
ruff check .
ruff format --check .
pytest
```

Prefer automatic formatting over subjective formatting discussions.

---

# 36. Testing

Testing is mandatory.

Prioritize pure unit tests for core behavior.

Critical areas:

```text
scheduler
focus state transitions
break logic
hydration merging
sleep reconciliation
idle reconciliation
adaptive focus rules
notification suppression
database migrations
crash recovery
```

Use an injectable clock.

Do not make automated tests actually wait minutes.

Example:

```python
clock.advance(minutes=50)
scheduler.tick()
```

Tests should be deterministic.

---

# 37. Regression Testing

Whenever fixing a bug:

1. reproduce the bug with a test when practical;
2. verify the test fails;
3. implement the fix;
4. verify the test passes;
5. ensure surrounding tests still pass.

Do not repeatedly patch symptoms without regression coverage.

---

# 38. UI Testing

Keep UI tests targeted.

Test that:

```text
application boots
QML loads
focus can start
focus can pause
break state appears
settings propagate correctly
main window can hide/reopen
application can quit
```

Do not duplicate all business-logic testing through UI automation.

---

# 39. Security

ScreenCare has a relatively small attack surface. Keep it that way.

Avoid:

```text
embedded web servers
open network ports
unnecessary subprocess execution
shell=True
dynamic code execution
eval
exec
loading untrusted plugins
unsafe deserialization
automatic execution of downloaded files
```

Treat all user-controlled paths and imported data as untrusted.

For subprocesses, pass argument arrays explicitly.

Never interpolate untrusted text into shell commands.

---

# 40. File Safety

Never overwrite arbitrary user files.

Exports should:

- require a user-selected destination;
- avoid replacing an existing file without confirmation;
- use safe encodings;
- close file handles correctly.

Internal state should live only inside ScreenCare's designated application-data directory.

---

# 41. Package Supply-Chain Safety

Keep third-party dependencies minimal.

Pin runtime dependencies.

Before adding a new runtime dependency, verify:

```text
maintainer/repository legitimacy
recent maintenance
license compatibility
package name correctness
whether Qt/Python already provides equivalent functionality
```

Do not add packages simply because an AI-generated example uses them.

---

# 42. Packaging

Use:

```text
pyside6-deploy
Nuitka
```

as the primary production packaging approach unless testing reveals a concrete blocker.

Prefer a normal standalone application/install layout over a self-extracting one-file executable.

Explicitly exclude unused Qt modules.

Do not package large unnecessary modules such as:

```text
QtWebEngine
QtMultimedia
Qt3D
```

unless required.

---

# 43. Setup Experience

A developer should be able to clone the repository and get started with a small number of commands.

Provide:

```text
README.md
pyproject.toml
clear virtual-environment instructions
single dependency install command
single run command
single test command
single build command
```

Target something approximately like:

```bash
python -m venv .venv

# activate environment

python -m pip install -e ".[dev]"

python -m screencare
```

Testing:

```bash
pytest
```

Quality:

```bash
ruff check .
```

Build:

```bash
pyside6-deploy
```

Adapt exact commands to the final repository structure.

---

# 44. No Hidden Manual Setup

Avoid requiring developers to manually:

```text
copy DLL files
edit absolute filesystem paths
install random binary utilities
set undocumented environment variables
modify the registry
edit system configuration
```

If external system tooling is required for packaging, document it explicitly.

Running the application in development mode should remain simple.

---

# 45. Configuration Files

Keep project configuration centralized.

Prefer:

```text
pyproject.toml
pysidedeploy.spec
```

rather than many unrelated configuration files.

Document any non-obvious settings.

---

# 46. Documentation

Maintain:

```text
README.md
ARCHITECTURE.md
DEVELOPMENT.md
```

README should cover:

```text
what ScreenCare is
supported platforms
installation
development setup
how to run
how to test
how to build
privacy model
```

ARCHITECTURE should explain:

```text
state engine
scheduler
platform abstraction
persistence
notifications
QML/Python boundary
```

Do not make documentation excessively verbose.

Update it whenever architecture changes meaningfully.

---

# 47. Comments

Prefer understandable code over excessive comments.

Comments should explain:

```text
why
platform quirks
non-obvious safety behavior
important timing assumptions
```

Avoid comments that merely restate the code.

---

# 48. Git Discipline

Keep commits logically scoped.

Do not combine:

```text
architecture refactor
UI redesign
dependency upgrade
database migration
feature implementation
```

into one giant change when avoidable.

Never commit:

```text
virtual environments
build artifacts
temporary databases
logs
IDE cache directories
OS metadata
secrets
```

Provide an appropriate `.gitignore`.

---

# 49. Implementation Workflow

Work incrementally.

Do not try to implement every ScreenCare feature simultaneously.

Use this sequence.

## Phase 1 — Repository foundation

Create:

```text
pyproject.toml
package structure
linting
test setup
application bootstrap
minimal QML window
```

Confirm:

```text
app starts
tests run
linting runs
```

before proceeding.

## Phase 2 — Pure core domain

Implement without OS-specific APIs:

```text
Clock
FakeClock
Scheduler
FocusEngine
BreakEngine
HydrationEngine
EyeRestEngine
WellnessCoordinator
```

Write strong unit tests.

## Phase 3 — Persistence

Implement:

```text
QSettings
SQLite
migrations
repositories
session snapshots
restart recovery
```

Test migrations and recovery.

## Phase 4 — Desktop UI

Build:

```text
dashboard
focus screen
break screen
Idea Walk
settings
tray integration
```

Keep all business logic outside QML.

## Phase 5 — First platform integration

Implement:

```text
idle
lock
sleep
wake
```

for the developer's current primary OS.

Do this through platform interfaces.

## Phase 6 — Packaging

Produce a packaged build early.

Measure:

```text
startup time
memory
CPU
package size
background behavior
sleep/wake correctness
```

Do not wait until the end of the project to test packaging.

## Phase 7 — Other operating systems

Add adapters one at a time.

Do not change core logic merely to accommodate platform differences unless absolutely necessary.

## Phase 8 — Polish

Only after stability:

```text
adaptive-focus improvements
analytics
onboarding
themes
accessibility refinements
advanced notification behavior
```

---

# 50. Definition of Done for Every Feature

A feature is not complete merely because it appears to work once.

For every feature, ensure:

```text
implementation complete
unit tests where applicable
error path considered
sleep/wake considered
restart considered
privacy considered
resource cost considered
platform compatibility considered
documentation updated if needed
lint/type checks pass
existing tests pass
```

---

# 51. Avoid Premature Features

Do not add the following unless explicitly requested later:

```text
accounts
cloud synchronization
social features
gamification systems
AI assistant
LLM integration
browser extension
mobile companion
team dashboards
employer monitoring
screen recording
productivity surveillance
website blocking
application blocking
automatic medical recommendations
```

Build the core exceptionally well first.

---

# 52. Medical Boundaries

ScreenCare is a wellness/productivity application.

Do not implement claims such as:

```text
prevents headaches
treats eye strain
diagnoses dehydration
detects medical conditions
```

Use language such as:

```text
encourages healthier computer-use habits
supports regular breaks
helps users remember hydration
helps reduce long uninterrupted sessions
```

The software should never behave as a medical diagnostic system.

---

# 53. User Control

The user must remain in control.

Every reminder system should provide reasonable controls such as:

```text
disable
adjust
snooze
quiet mode
skip
```

Do not punish users for skipping breaks.

Do not implement addictive streak mechanics by default.

Do not artificially create urgency.

---

# 54. Reliability Before Visual Polish

When forced to choose, prioritize in this order:

```text
1. correctness
2. safety
3. data integrity
4. low interference
5. resource efficiency
6. maintainability
7. usability
8. visual polish
```

A beautiful timer that breaks after laptop sleep is unacceptable.

A slightly simpler UI with correct state recovery is preferable.

---

# 55. Decision-Making Rule

When encountering an implementation choice not explicitly covered by the context documents, choose the option that:

1. requests fewer permissions;
2. uses fewer dependencies;
3. performs less background work;
4. keeps more data local;
5. creates fewer OS side effects;
6. is easier to test;
7. is easier to remove or replace later;
8. follows standard Qt/Python patterns.

Document important architectural decisions.

---

# 56. Before Writing Significant Code

For each substantial milestone:

1. inspect the existing repository;
2. inspect the relevant project-context requirements;
3. identify existing abstractions before creating new ones;
4. avoid duplicate implementations;
5. state the files/components you intend to modify;
6. implement the smallest coherent slice;
7. run relevant tests;
8. run linting;
9. inspect failures rather than bypassing them;
10. leave the repository in a runnable state.

Do not rewrite working architecture unnecessarily.

---

# 57. When Something Is Uncertain

Do not invent APIs or platform behavior.

If unsure about:

```text
Qt behavior
PySide6 API
Windows API
macOS API
XDG Portal behavior
Nuitka packaging
SQLite behavior
```

verify it against current official documentation before implementation.

Prefer primary documentation over random tutorials or old Stack Overflow snippets.

---

# 58. Initial Deliverable

Begin by reviewing both context files and the existing repository.

Then produce a concise implementation assessment containing:

```text
Current repository state
Architecture you intend to preserve
First implementation milestone
Files you expect to create/change
Any important risks or contradictions discovered
```

After that, begin implementing the first coherent milestone.

Do not create a giant speculative codebase in one pass.

Work iteratively and keep the application runnable after each milestone.

---

# 59. Final Engineering Principle

ScreenCare should feel invisible when it is not needed and helpful when it is.

The underlying engineering should follow the same principle.

The application should:

```text
wake rarely
observe minimally
store locally
interrupt intelligently
fail gracefully
recover correctly
remain easy to quit
remain easy to uninstall
never take control away from the user
```

Build ScreenCare as software a user could comfortably leave running throughout every workday without worrying about privacy, system performance, instability, or interference with the rest of their computer.