# Notes for AI agents

- Product intent: `docs/concept.md`. Current plan: `docs/PLAN.md`. Design:
  `ARCHITECTURE.md`, `docs/UI.md`. That's enough context for almost any task.
- **Don't read `docs/archive/`** unless the task is explicitly about the old
  desktop app. It's ~100 KB of superseded spec.
- Keep it small: business rules live in `screencare/rules.py` as pure
  functions over `(session, action, now)`. No new layers, protocols, or
  adapter classes without a concrete second use.
- Comments explain non-obvious *why*. No spec section citations.
- Done = `pytest` passes, `ruff check --fix . && ruff format .` applied.
