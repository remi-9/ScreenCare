# Notes for AI agents

- Product intent: `docs/concept.md`. Current plan: `docs/PLAN.md`. Design:
  `ARCHITECTURE.md`, `docs/UI.md`. That's enough context for almost any task.
- The old PySide6 desktop app and its specs live only at git tag
  `desktop-final`. Ignore them unless a task is explicitly about that version.
- Keep it small: business rules live in `screencare/rules.py` as pure
  functions over `(session, action, now)`. No new layers, protocols, or
  adapter classes without a concrete second use.
- Comments explain non-obvious *why*. No spec section citations.
- Done = `pytest` passes, `ruff check --fix . && ruff format .` applied.
