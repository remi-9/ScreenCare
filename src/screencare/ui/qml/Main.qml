import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts

// The real desktop shell (Phase 4). Presentation only, per
// ScreenCare — Technical.md section 24: every value shown here is read
// from a view model (focusViewModel / breakViewModel / settingsViewModel /
// dashboardViewModel), and every action calls straight back into one.
Window {
    id: root

    width: 460
    height: 640
    minimumWidth: 380
    minimumHeight: 520
    visible: true
    title: qsTr("ScreenCare")
    color: "#101418"

    // Technical.md section 18/28: closing the main window should hide it
    // and keep ScreenCare running in the tray, not quit -- but only when a
    // tray actually exists to fall back to (trayAvailable is a context
    // property set once at startup by app/bootstrap.py).
    onClosing: (close) => {
        if (trayAvailable) {
            close.accepted = false
            root.hide()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        TabBar {
            id: tabBar
            Layout.fillWidth: true

            TabButton { text: qsTr("Focus") }
            TabButton { text: qsTr("Dashboard") }
            TabButton { text: qsTr("Settings") }
        }

        StackLayout {
            id: stack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex
            // "Dashboard queries should run ... when the dashboard opens" --
            // Technical.md section 42 -- never on a timer.
            onCurrentIndexChanged: if (currentIndex === 1) dashboardViewModel.refresh()

            FocusView { }
            DashboardView { }
            SettingsView { }
        }
    }

    // The recovery-break / "ready" overlay takes over the whole window,
    // matching Concept.md's full-context break screen. An idea walk stays
    // inline inside FocusView instead -- it's a short pause within the
    // session, not a separate interruption.
    BreakView {
        anchors.fill: parent
        visible: breakViewModel.isRecoveryDue || breakViewModel.isBreaking || breakViewModel.isReady
        z: 10
    }

    Component.onCompleted: dashboardViewModel.refresh()
}
