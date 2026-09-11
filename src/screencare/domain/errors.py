"""Shared domain-level exceptions."""

from __future__ import annotations


class InvalidStateTransition(RuntimeError):
    """Raised when an engine method is called from a state that doesn't
    support it (e.g. pausing a session that was never started).

    This is a programming-error signal, not a user-facing condition — the
    caller (a view model, later) is expected to only offer the actions
    valid for the current state in the first place. Engines raise this
    instead of silently no-op'ing so a bug is caught in tests rather than
    producing a subtly wrong session record.
    """
