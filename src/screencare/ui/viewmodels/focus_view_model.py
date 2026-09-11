"""``FocusViewModel``: the QML-facing surface over :class:`~screencare.app.session.AppSession`
for the focus timer and its controls (``ScreenCare — Technical.md`` section 24).

Deliberately thin — every property is a read-through to ``AppSession``, and
every slot just calls straight through to it and swallows an
``InvalidStateTransition`` (a stale button click racing a state change is a
UI nuisance, not a crash). All business rules stay in ``AppSession`` and the
Phase 2 engines beneath it; QML only ever sees state, never decides it.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot

from screencare.app.session import AppSession
from screencare.domain.enums import FocusMode
from screencare.domain.errors import InvalidStateTransition

logger = logging.getLogger(__name__)


class FocusViewModel(QObject):
    changed = Signal()

    def __init__(self, session: AppSession, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._session = session

    def refresh(self) -> None:
        """Re-evaluate every property. Called after every ``AppSession``
        mutation (immediate feedback) and once per UI tick (so the visible
        countdown keeps moving even when nothing else changed)."""
        self.changed.emit()

    # -- properties -----------------------------------------------------------

    @Property(str, notify=changed)
    def state(self) -> str:
        return self._session.focus_state.value

    @Property(str, notify=changed)
    def mode(self) -> str:
        mode = self._session.focus_mode
        return mode.value if mode is not None else ""

    @Property(str, notify=changed)
    def taskLabel(self) -> str:
        return self._session.task_label or ""

    @Property(int, notify=changed)
    def remainingSeconds(self) -> int:
        return int(self._session.remaining_seconds)

    @Property(int, notify=changed)
    def activeSeconds(self) -> int:
        return int(self._session.active_seconds)

    @Property(int, notify=changed)
    def extensionsUsed(self) -> int:
        return self._session.extensions_used

    @Property(int, notify=changed)
    def maxExtensions(self) -> int:
        return self._session.max_extensions

    @Property(bool, notify=changed)
    def canExtend(self) -> bool:
        return self._session.extensions_used < self._session.max_extensions

    @Property(int, notify=changed)
    def adaptiveFocusMinutes(self) -> int:
        return self._session.adaptive_focus_seconds // 60

    @Property(str, notify=changed)
    def reminderText(self) -> str:
        return self._session.reminder_text

    @Property(bool, notify=changed)
    def isQuiet(self) -> bool:
        return self._session.is_quiet

    # -- actions --------------------------------------------------------------

    @Slot(str)
    def startClassic(self, task_label: str = "") -> None:
        self._run(lambda: self._session.start_focus(FocusMode.CLASSIC, task_label or None))

    @Slot(str)
    def startDeepFocus(self, task_label: str = "") -> None:
        self._run(lambda: self._session.start_focus(FocusMode.DEEP_FOCUS, task_label or None))

    @Slot(str)
    def startAdaptive(self, task_label: str = "") -> None:
        self._run(lambda: self._session.start_focus(FocusMode.ADAPTIVE, task_label or None))

    @Slot()
    def pause(self) -> None:
        self._run(self._session.pause)

    @Slot()
    def resume(self) -> None:
        self._run(self._session.resume)

    @Slot()
    def extend(self) -> None:
        self._run(self._session.extend)

    @Slot()
    def finishCurrentThought(self) -> None:
        self._run(self._session.finish_current_thought)

    @Slot()
    def startIdeaWalk(self) -> None:
        self._run(self._session.start_idea_walk)

    @Slot(str)
    def returnFromIdeaWalk(self, note: str = "") -> None:
        self._run(lambda: self._session.return_from_idea_walk(resume_focus=True, note=note or None))

    @Slot()
    def endSessionFromIdeaWalk(self) -> None:
        self._run(lambda: self._session.return_from_idea_walk(resume_focus=False))

    @Slot()
    def stop(self) -> None:
        self._run(self._session.stop)

    @Slot()
    def dismissReminder(self) -> None:
        self._run(self._session.dismiss_reminder)

    @Slot()
    def logDrink(self) -> None:
        self._run(self._session.log_drink)

    @Slot()
    def enterQuietMode(self) -> None:
        self._run(self._session.enter_quiet_mode)

    @Slot()
    def exitQuietMode(self) -> None:
        self._run(self._session.exit_quiet_mode)

    def _run(self, action) -> None:
        try:
            action()
        except InvalidStateTransition:
            logger.warning("Ignored an out-of-order focus action", exc_info=True)
