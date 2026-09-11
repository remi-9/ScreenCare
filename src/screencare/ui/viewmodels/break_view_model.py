"""``BreakViewModel``: the narrow surface ``BreakView.qml`` needs to show and
dismiss a recovery break, an idea walk, or the post-break "ready" screen —
split out from :class:`~screencare.ui.viewmodels.focus_view_model.FocusViewModel`
per the four named view models in ``ScreenCare — Technical.md`` section 24.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot

from screencare.app.session import AppSession
from screencare.domain.enums import FocusState
from screencare.domain.errors import InvalidStateTransition

logger = logging.getLogger(__name__)


class BreakViewModel(QObject):
    changed = Signal()

    def __init__(self, session: AppSession, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._session = session

    def refresh(self) -> None:
        self.changed.emit()

    # -- properties -----------------------------------------------------------

    @Property(bool, notify=changed)
    def isRecoveryDue(self) -> bool:
        return self._session.focus_state is FocusState.RECOVERY_DUE

    @Property(bool, notify=changed)
    def isBreaking(self) -> bool:
        return self._session.focus_state is FocusState.BREAKING

    @Property(bool, notify=changed)
    def isReady(self) -> bool:
        return self._session.focus_state is FocusState.READY

    @Property(bool, notify=changed)
    def isIdeaWalk(self) -> bool:
        return self._session.focus_state is FocusState.IDEA_WALK

    @Property(bool, notify=changed)
    def includeHydration(self) -> bool:
        return self._session.pending_recovery_includes_hydration

    @Property(bool, notify=changed)
    def canFinishCurrentThought(self) -> bool:
        return self.isRecoveryDue

    @Property(bool, notify=changed)
    def canExtend(self) -> bool:
        return self.isRecoveryDue and self._session.extensions_used < self._session.max_extensions

    # -- actions --------------------------------------------------------------

    @Slot()
    def startBreak(self) -> None:
        self._run(self._session.start_break)

    @Slot()
    def endBreak(self) -> None:
        self._run(self._session.end_break)

    @Slot()
    def extend(self) -> None:
        self._run(self._session.extend)

    @Slot()
    def finishCurrentThought(self) -> None:
        self._run(self._session.finish_current_thought)

    @Slot()
    def acknowledgeReady(self) -> None:
        self._run(self._session.acknowledge_ready)

    def _run(self, action) -> None:
        try:
            action()
        except InvalidStateTransition:
            logger.warning("Ignored an out-of-order break action", exc_info=True)
