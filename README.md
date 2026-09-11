# ScreenCare

ScreenCare is a local-first, privacy-first desktop wellness and focus
companion. It combines adaptive Pomodoro-style focus sessions with smart,
consolidated reminders for eye rest, hydration, movement, and breaks — aimed
at protecting deep focus without causing notification fatigue.

The full product vision and engineering specification live in this
project's docs and are the source of truth for implementation decisions:

- `ScreenCare — Concept.md`
- `ScreenCare — Technical.md`
- `ScreenCare — Implementation Standards.md`

See `ARCHITECTURE.md` for a short map of the system as currently built, and
`DEVELOPMENT.md` for day-to-day developer workflow.

## Supported platforms

Windows 10/11 is the first fully implemented and tested platform. The
architecture keeps all OS-specific behavior behind interfaces so macOS and
Linux adapters can be added later without changing core logic, but those
adapters do not exist yet.

## Status

Early scaffold. The application currently boots to a placeholder window;
none of the focus/break/hydration behavior is implemented yet. See
`ARCHITECTURE.md` for what exists today versus what's planned.

## Installation (development)

Requires Python 3.13 (`>=3.13,<3.14`).

```bash
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

python -m pip install -e ".[dev]"
```

## Running

```bash
python -m screencare
```

## Testing

```bash
pytest
```

UI tests that need a Qt platform plugin run headlessly via the
`QT_QPA_PLATFORM=offscreen` setting in `tests/conftest.py`, so no visible
window is required to run the suite.

## Linting

```bash
ruff check .
ruff format --check .
```

## Building

Packaging uses `pyside6-deploy` (a Nuitka-based tool) once there is a real
application to package. Not set up yet — see `ARCHITECTURE.md`.

## Privacy

ScreenCare runs entirely on-device. It makes no network requests, requires
no account, and does not collect keystrokes, screenshots, clipboard
contents, or window/document contents. It only ever needs to know: time
since last input, lock state, and sleep/wake state. All history and
settings stay in the OS-standard local application-data directory.
