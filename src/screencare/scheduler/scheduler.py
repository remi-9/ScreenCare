"""The central deadline registry.

Every engine schedules its own named deadlines here instead of owning a
timer of its own — one shared mechanism instead of many independent
``QTimer``s (``ScreenCare — Technical.md`` section 11,
``ScreenCare — Implementation Standards.md`` section 8). Whatever drives
the real event loop (a Qt timer, from Phase 4 onward) only needs to call
:meth:`Scheduler.tick` periodically; this class has no Qt dependency and no
opinion on how often that happens.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from screencare.scheduler.clock import Clock


@dataclass
class _Entry:
    due_ns: int
    callback: Callable[[], None]


class Scheduler:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._entries: dict[str, _Entry] = {}

    def schedule_once(self, key: str, delay_seconds: float, callback: Callable[[], None]) -> None:
        """Schedule ``callback`` to fire ``delay_seconds`` from now under
        ``key``. Scheduling again under the same key replaces it."""
        if delay_seconds < 0:
            raise ValueError(f"delay_seconds must be >= 0, got {delay_seconds!r}")
        due_ns = self._clock.monotonic_ns() + int(delay_seconds * 1_000_000_000)
        self._entries[key] = _Entry(due_ns=due_ns, callback=callback)

    def cancel(self, key: str) -> None:
        """Remove a scheduled deadline. A no-op if it isn't scheduled."""
        self._entries.pop(key, None)

    def is_scheduled(self, key: str) -> bool:
        return key in self._entries

    def seconds_until(self, key: str) -> float | None:
        """Seconds remaining until ``key`` is due, or ``None`` if it isn't
        scheduled. Can be negative if it's already overdue but hasn't been
        ticked yet."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        return (entry.due_ns - self._clock.monotonic_ns()) / 1_000_000_000

    def tick(self) -> list[str]:
        """Fire and remove every deadline that is now due.

        Returns the keys that fired, in the order they became due. A
        callback that reschedules a *different* key which is also already
        due will not be fired again within the same ``tick()`` call — it
        waits for the next tick, which keeps this bounded and predictable.
        """
        now_ns = self._clock.monotonic_ns()
        due_keys = sorted(
            (key for key, entry in self._entries.items() if entry.due_ns <= now_ns),
            key=lambda key: self._entries[key].due_ns,
        )
        fired: list[str] = []
        for key in due_keys:
            entry = self._entries.pop(key, None)
            if entry is None:
                continue  # an earlier callback in this same tick already cancelled it
            entry.callback()
            fired.append(key)
        return fired
