# Development guide

## Setup

Requires Python 3.13 (`>=3.13,<3.14` — see `ScreenCare — Technical.md` §3
for why this version is pinned rather than the newest available).

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
python -m pip install -e ".[dev]"
```

This installs the app plus `pytest`, `pytest-qt`, and `ruff`.

## Running the app

```bash
python -m screencare
```

This should open a small window titled "ScreenCare". If it doesn't, check
the console output — `app/bootstrap.py` logs and returns exit code 1 when
the root QML fails to load, rather than failing silently.

## Testing

```bash
pytest
```

- `tests/unit/` — pure-Python tests with no Qt dependency. These must
  always be runnable, even in an environment without PySide6 installed.
- `tests/ui/` — tests that touch Qt/QML. Each such module starts with
  `pytest.importorskip("PySide6")` so the suite degrades gracefully instead
  of erroring out where PySide6 isn't installed, but runs for real
  wherever it is (your dev machine, CI, packaged-build smoke tests).
- `tests/conftest.py` forces `QT_QPA_PLATFORM=offscreen` so UI tests never
  need a visible display or window focus to pass.

All engine/scheduler tests drive time via the injectable `FakeClock`
(`screencare.scheduler.clock`) rather than real `sleep()` calls — see
`ScreenCare — Implementation Standards.md` §36. The pattern:

```python
clock = FakeClock()
scheduler = Scheduler(clock)
engine = FocusEngine(clock, scheduler)
engine.start(plan)
clock.advance(minutes=25)   # instantaneous — no real waiting
scheduler.tick()            # fires any deadlines that are now due
```

New time-dependent code should follow the same shape rather than adding a
real timer or `time.sleep` anywhere in a test.

## Linting and formatting

```bash
ruff check .
ruff format --check .
```

Fix reported issues rather than suppressing them. Formatting itself is not
subjective here — run `ruff format .` to apply it rather than
hand-formatting to match.

## Building a standalone Windows executable

```powershell
pip install nuitka   # or let the build script do it
.\packaging\build_windows.ps1
```

That wraps `pyside6-deploy -c pysidedeploy.spec`, which itself wraps
Nuitka (`ScreenCare — Technical.md`'s "Final Recommended Stack": "
`pyside6-deploy` and Nuitka"). Requires a working dev install (`pip
install -e ".[dev]"`) with PySide6 present, plus Nuitka's own build
prerequisites (a C compiler — on Windows, either MSVC via the Visual
Studio Build Tools, or MinGW64, which Nuitka can offer to download on
first run). The build takes several minutes; output lands under `.\dist\`
as a folder (`mode = standalone` in `pysidedeploy.spec` — deliberately not
the tool's default `onefile`, which self-extracts to a temp directory on
every launch; see the comment in that file for why that matters for an
always-running, launch-at-login background app).

**This can only be built and verified on a real Windows machine** —
Nuitka needs a native C toolchain and PySide6, neither available in the
cloud sandbox this project has otherwise been developed in. After
building, run this smoke-test checklist by hand (`Technical.md` §40's
"platform tests... run a small number of real native integration tests"
and §47's acceptance criteria, applied to the packaged build specifically
rather than just the dev environment):

1. Launch `dist\ScreenCare.dist\main.exe` directly (not via `python
   -m screencare`) — no console window should appear, and the tray icon
   should show up within a couple of seconds. (The executable is named
   `main.exe`, after `input_file`'s module name in `pysidedeploy.spec`,
   not after `[app] title` — confirmed by inspecting the actual build
   output, not assumed.) If nothing visibly happens when you launch it,
   see "Diagnosing a silent failure" below before assuming the build is
   broken.
2. Start a focus session, then close the main window — it should
   minimize to the tray rather than quitting (Phase 4).
3. Lock the session, wait, and unlock it; sleep and wake the machine
   during a focus session — neither should be counted as focus time
   (Phase 5).
4. Check Task Manager while the window is hidden in the tray for a
   few minutes: CPU usage should be negligible and memory stable, not
   climbing (`Technical.md` §47's "Tray mode" acceptance scenario).
5. Quit from the tray menu, then relaunch — history and settings from
   step 2 should still be there (SQLite database persisted under
   `%LOCALAPPDATA%`).
6. Toggle "launch at login" in Settings and confirm the entry actually
   appears/disappears in Windows' Startup Apps (Phase 5's autostart).

Note that none of this — the spec file, the icon, the build script — has
actually been run in this project yet; it's built and reasoned through
carefully against current `pyside6-deploy`/Nuitka documentation, but only
the user's machine can confirm it produces a working executable.

### Diagnosing a silent failure

`pysidedeploy.spec` builds with `--windows-console-mode=disable`, which
compiles `main.exe` as a Windows GUI-subsystem binary: it has no console
I/O at all, ever, regardless of how it's launched. `bootstrap.py` does log
and return exit code 1 when startup fails (see `app/bootstrap.py`), but
those log calls have no handler configured for the packaged build, so with
the console disabled **a startup crash is completely silent** — no window,
no console output, no log file, just a process that starts and exits.
That's a real gap, not expected behavior, if it happens. To see what's
actually going wrong:

1. Temporarily rebuild with the console enabled: in `pysidedeploy.spec`,
   change `--windows-console-mode=disable` to `--windows-console-mode=force`
   under `[nuitka]`, re-run `.\packaging\build_windows.ps1`, then launch
   `dist\ScreenCare.dist\main.exe` from a PowerShell window (not by
   double-clicking) so any traceback prints to that terminal. Revert the
   spec change once you've diagnosed the issue — `disable` is the intended
   shipped setting for a background app.
2. Separately (this doesn't need a rebuild): check Windows Security →
   Protection history for a blocked/quarantined entry, and Event Viewer →
   Windows Logs → Application for an "Application Error" entry timestamped
   around the failed launch. A freshly built, unsigned Nuitka executable
   is exactly the kind of thing SmartScreen or antivirus heuristics flag,
   and that can look like "nothing happens" if the block is silent.

## Workflow for new milestones

Before writing significant code for the next milestone:

1. Re-read the relevant section(s) of the three project docs.
2. Check what already exists in the repo — don't duplicate an existing
   abstraction.
3. State the smallest coherent slice and which files it touches.
4. Implement it.
5. Run `pytest` and `ruff check . && ruff format --check .`; fix failures
   rather than bypassing them.
6. Confirm `python -m screencare` still starts.
7. Leave the repository in a runnable state before moving on.

This mirrors `ScreenCare — Implementation Standards.md` §56 and §50
("Definition of Done").
