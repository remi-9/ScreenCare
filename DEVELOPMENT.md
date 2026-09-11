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

As engine/scheduler code lands in Phase 2, tests must drive time via an
injectable `FakeClock` rather than real `sleep()` calls — see
`ScreenCare — Implementation Standards.md` §36.

## Linting and formatting

```bash
ruff check .
ruff format --check .
```

Fix reported issues rather than suppressing them. Formatting itself is not
subjective here — run `ruff format .` to apply it rather than
hand-formatting to match.

## Building

Not set up yet. The plan (per `ScreenCare — Technical.md` §36) is
`pyside6-deploy` (a `pyside6-deploy`/Nuitka standalone build), configured
via `pysidedeploy.spec` once there's a real application to package —
targeted for the Phase 6 milestone in `ARCHITECTURE.md`.

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
