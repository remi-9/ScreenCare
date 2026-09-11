"""Qt application bootstrap.

Builds the Qt application, the real ``AppSession`` (persistence, engines,
notifications wired together), the view models, and the root QML window,
then hands control to the Qt event loop. This module is wiring only — see
``ARCHITECTURE.md``. It is deliberately split into small, separately
callable functions (``open_database``, ``build_app_session``,
``create_engine``) rather than one long ``run()`` body, so a test can build
the same real QML engine and view-model graph this module builds, without
having to fake anything.

Uses ``QApplication`` rather than a bare ``QGuiApplication`` (Phase 1)
because ``QSystemTrayIcon``/``QMenu``/``QAction`` live in the widgets-based
tray stack (``ScreenCare — Technical.md`` section 16's MVP notification
delivery mechanism) -- ``QApplication`` is a ``QGuiApplication`` subclass,
so ``QQmlApplicationEngine`` and Qt Quick work exactly the same under it.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from screencare.app.session import AppSession
from screencare.domain.enums import FocusState
from screencare.notifications.base import InMemoryNotificationService, NotificationService
from screencare.notifications.tray_service import TrayNotificationService
from screencare.persistence.database import Database, DatabaseError
from screencare.persistence.paths import default_database_path
from screencare.persistence.repositories import (
    BreakSessionRepository,
    FocusSessionRepository,
    HydrationEventRepository,
    IdeaWalkNoteRepository,
)
from screencare.persistence.session_recovery import RecoveryAction, SessionSnapshotRepository
from screencare.persistence.settings import AppSettings, QSettingsBackend
from screencare.platform.factory import PlatformAdapters, build_platform_adapters
from screencare.scheduler.clock import Clock, SystemClock
from screencare.scheduler.scheduler import Scheduler
from screencare.ui.viewmodels.break_view_model import BreakViewModel
from screencare.ui.viewmodels.dashboard_view_model import DashboardViewModel
from screencare.ui.viewmodels.focus_view_model import FocusViewModel
from screencare.ui.viewmodels.settings_view_model import SettingsViewModel

logger = logging.getLogger(__name__)

QML_DIR = Path(__file__).resolve().parent.parent / "ui" / "qml"
MAIN_QML = QML_DIR / "Main.qml"

# Technical.md §25/§27: update the visible countdown once a second while a
# window is open; fall back to a much coarser tick while hidden in the tray
# so an all-day background session stays close to idle.
VISIBLE_TICK_MS = 1_000
HIDDEN_TICK_MS = 5_000


def open_database() -> Database:
    """Open the real on-disk database, degrading rather than crash-looping
    if it can't be (``Technical.md`` section 41: "Database unavailable ->
    show recoverable error, attempt safe reopen, do not crash-loop"). Falls
    back to an in-memory database as a last resort so the app stays usable
    for the session even if the disk copy is unrecoverable; history just
    won't survive a restart in that degraded case."""
    path = default_database_path()
    try:
        return Database.open(path, clock=SystemClock())
    except DatabaseError:
        logger.exception("Could not open the database at %s; attempting a safe reopen", path)

    try:
        quarantined = path.with_name(path.name + ".corrupt")
        if path.exists():
            path.replace(quarantined)
        return Database.open(path, clock=SystemClock())
    except DatabaseError:
        logger.exception("Safe reopen also failed; continuing with an in-memory database")
        return Database.open_in_memory(clock=SystemClock())


def build_app_session(
    *,
    database: Database,
    settings: AppSettings,
    notifier: NotificationService,
    on_changed=None,
    clock: Clock | None = None,
) -> AppSession:
    clock = clock or SystemClock()
    scheduler = Scheduler(clock)
    return AppSession(
        clock=clock,
        scheduler=scheduler,
        settings=settings,
        focus_repo=FocusSessionRepository(database.connection, clock),
        break_repo=BreakSessionRepository(database.connection, clock),
        hydration_repo=HydrationEventRepository(database.connection),
        idea_walk_note_repo=IdeaWalkNoteRepository(database.connection, clock),
        snapshot_repo=SessionSnapshotRepository(database.connection),
        notifier=notifier,
        on_changed=on_changed,
    )


def _build_tray_pixmap() -> QPixmap:
    """A small generated icon rather than a shipped asset: a calm, single
    color dot that reads clearly at tray size on light or dark taskbars."""
    size = 32
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#4FA3D1"))
    painter.setPen(QColor("#1D2B33"))
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.end()
    return pixmap


def build_tray_icon() -> QSystemTrayIcon | None:
    """``None`` if no system tray is available -- callers must fall back to
    normal window behavior rather than assuming this always succeeds
    (``Technical.md`` section 41: "Tray unavailable -> keep main window
    available, disable tray-only close behavior")."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.warning("No system tray available; falling back to normal window behavior")
        return None
    tray_icon = QSystemTrayIcon(QIcon(_build_tray_pixmap()))
    tray_icon.setToolTip("ScreenCare")
    return tray_icon


def create_engine(
    app: QApplication,
    *,
    app_session: AppSession,
    focus_vm: FocusViewModel,
    break_vm: BreakViewModel,
    settings_vm: SettingsViewModel,
    dashboard_vm: DashboardViewModel,
    tray_available: bool,
) -> QQmlApplicationEngine:
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
    context = engine.rootContext()
    context.setContextProperty("focusViewModel", focus_vm)
    context.setContextProperty("breakViewModel", break_vm)
    context.setContextProperty("settingsViewModel", settings_vm)
    context.setContextProperty("dashboardViewModel", dashboard_vm)
    context.setContextProperty("trayAvailable", tray_available)
    engine.load(QUrl.fromLocalFile(str(MAIN_QML)))
    return engine


def _sync_autostart(adapters: PlatformAdapters, settings: AppSettings) -> None:
    """Make the real Windows autostart entry match the stored preference.
    Previous phases only round-tripped ``launch_at_login`` as a setting;
    this is what actually registers/removes it (Phase 5). Never raises --
    an unavailable or failing autostart adapter must not crash the app
    (``Technical.md`` section 41)."""
    if adapters.autostart_service is None:
        return
    try:
        adapters.autostart_service.set_enabled(settings.launch_at_login)
    except OSError:
        logger.exception("Failed to sync the Windows autostart entry")


def _wire_tray_menu(
    tray_icon: QSystemTrayIcon,
    *,
    app: QApplication,
    app_session: AppSession,
    settings: AppSettings,
    focus_vm: FocusViewModel,
    show_window,
) -> QMenu:
    """Builds the tray menu from ``ScreenCare — Technical.md`` section 18.
    Kept as a plain ``QMenu`` (not QML) since it's OS chrome, not
    application UI -- consistent with using ``QSystemTrayIcon`` itself."""
    menu = QMenu()

    status_action = QAction("Current: Stopped", menu)
    status_action.setEnabled(False)
    menu.addAction(status_action)

    start_pause_action = QAction("Start Focus", menu)
    take_break_action = QAction("Take a Break", menu)
    idea_walk_action = QAction("Idea Walk", menu)
    drink_water_action = QAction("Drink Water", menu)
    quiet_action = QAction(f"Quiet for {settings.quiet_mode_minutes} min", menu)
    menu.addAction(start_pause_action)
    menu.addAction(take_break_action)
    menu.addAction(idea_walk_action)
    menu.addAction(drink_water_action)
    menu.addAction(quiet_action)
    menu.addSeparator()

    open_action = QAction("Open ScreenCare", menu)
    quit_action = QAction("Quit", menu)
    menu.addAction(open_action)
    menu.addAction(quit_action)

    def _refresh_status() -> None:
        state = app_session.focus_state
        if state is FocusState.FOCUSING:
            minutes, seconds = divmod(int(app_session.remaining_seconds), 60)
            status_action.setText(f"Current: Focus {minutes:02d}:{seconds:02d}")
            start_pause_action.setText("Pause Focus")
            start_pause_action.setEnabled(True)
        elif state is FocusState.PAUSED:
            status_action.setText("Current: Paused")
            start_pause_action.setText("Resume Focus")
            start_pause_action.setEnabled(True)
        elif state is FocusState.STOPPED:
            status_action.setText("Current: Stopped")
            start_pause_action.setText("Start Focus")
            start_pause_action.setEnabled(True)
        else:
            status_action.setText(f"Current: {state.value.replace('_', ' ').title()}")
            start_pause_action.setEnabled(False)
        take_break_action.setEnabled(state is FocusState.RECOVERY_DUE)
        idea_walk_action.setEnabled(state is FocusState.FOCUSING)

    def _start_pause() -> None:
        state = app_session.focus_state
        if state is FocusState.STOPPED:
            focus_vm.startClassic()
        elif state is FocusState.FOCUSING:
            focus_vm.pause()
        elif state is FocusState.PAUSED:
            focus_vm.resume()

    start_pause_action.triggered.connect(_start_pause)
    take_break_action.triggered.connect(lambda: app_session.start_break())
    idea_walk_action.triggered.connect(focus_vm.startIdeaWalk)
    drink_water_action.triggered.connect(focus_vm.logDrink)
    quiet_action.triggered.connect(focus_vm.enterQuietMode)
    open_action.triggered.connect(show_window)
    quit_action.triggered.connect(app.quit)
    tray_icon.activated.connect(
        lambda reason: show_window() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
    )

    focus_vm.changed.connect(_refresh_status)
    _refresh_status()

    tray_icon.setContextMenu(menu)
    return menu


def run(argv: list[str]) -> int:
    """Create the Qt application, wire everything up, load ``Main.qml``, and
    run the event loop. Returns the process exit code."""
    app = QApplication(argv)
    app.setOrganizationName("Pivotly")
    app.setApplicationName("ScreenCare")

    database = open_database()
    settings = AppSettings(QSettingsBackend())

    tray_icon = build_tray_icon()
    notifier: NotificationService
    if tray_icon is not None:
        notifier = TrayNotificationService(tray_icon)
    else:
        notifier = InMemoryNotificationService()

    view_models: list = []

    def _notify_changed() -> None:
        for vm in view_models:
            vm.refresh()

    app_session = build_app_session(
        database=database, settings=settings, notifier=notifier, on_changed=_notify_changed
    )

    startup_recovery = app_session.reconcile_startup()
    if startup_recovery.action is not RecoveryAction.NONE:
        logger.info("Startup recovery: %s", startup_recovery.action.value)
    app_session.begin()

    focus_vm = FocusViewModel(app_session)
    break_vm = BreakViewModel(app_session)
    view_models.extend([focus_vm, break_vm])

    # Filled in once the root window exists, below; a settings change before
    # then (unlikely -- QML hasn't loaded yet) just skips the autostart sync.
    adapters_holder: list[PlatformAdapters] = []

    def _on_settings_changed() -> None:
        app_session.apply_settings_changed()
        if adapters_holder:
            _sync_autostart(adapters_holder[0], settings)

    settings_vm = SettingsViewModel(settings, on_settings_changed=_on_settings_changed)
    dashboard_vm = DashboardViewModel(
        clock=SystemClock(),
        focus_repo=FocusSessionRepository(database.connection, SystemClock()),
        break_repo=BreakSessionRepository(database.connection, SystemClock()),
        hydration_repo=HydrationEventRepository(database.connection),
    )

    engine = create_engine(
        app,
        app_session=app_session,
        focus_vm=focus_vm,
        break_vm=break_vm,
        settings_vm=settings_vm,
        dashboard_vm=dashboard_vm,
        tray_available=tray_icon is not None,
    )

    if not engine.rootObjects():
        logger.error("Failed to load root QML file: %s", MAIN_QML)
        return 1

    root_window = engine.rootObjects()[0]

    # Built here rather than alongside app_session: the Windows adapter
    # needs the QML root window's native handle to register for
    # session-change notifications (Phase 5 -- idle/lock/sleep-wake).
    adapters = build_platform_adapters(root_window)
    adapters_holder.append(adapters)
    app_session.attach_platform_adapters(
        activity_provider=adapters.activity_provider, power_monitor=adapters.power_monitor
    )
    _sync_autostart(adapters, settings)

    def _show_window() -> None:
        root_window.show()
        root_window.raise_()
        root_window.requestActivate()

    if tray_icon is not None:
        _wire_tray_menu(
            tray_icon,
            app=app,
            app_session=app_session,
            settings=settings,
            focus_vm=focus_vm,
            show_window=_show_window,
        )
        tray_icon.show()
        # Tray keeps the app alive; Main.qml's own onClosing handler (guarded
        # by the trayAvailable context property) hides instead of closing.
        app.setQuitOnLastWindowClosed(False)
    else:
        # No tray to fall back to: never leave the user unable to quit
        # (Implementation Standards.md section 28).
        app.setQuitOnLastWindowClosed(True)

    timer = QTimer()
    timer.setTimerType(Qt.TimerType.CoarseTimer)

    def _on_tick() -> None:
        app_session.tick()
        focus_vm.refresh()
        break_vm.refresh()

    timer.timeout.connect(_on_tick)
    timer.start(VISIBLE_TICK_MS)

    def _on_visible_changed(visible: bool) -> None:
        timer.setInterval(VISIBLE_TICK_MS if visible else HIDDEN_TICK_MS)

    root_window.visibleChanged.connect(_on_visible_changed)

    def _on_quit() -> None:
        # Technical.md §18: "Explicit Quit: persist state, close database
        # cleanly, remove tray icon, exit process."
        app_session.shutdown()
        database.close()
        if tray_icon is not None:
            tray_icon.hide()

    app.aboutToQuit.connect(_on_quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(run(sys.argv))
