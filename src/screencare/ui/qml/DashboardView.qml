import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Concept.md's "Focus & Wellness Dashboard": a few explainable behavioral
// counts, not a running screen-time total. Data only ever refreshes when
// this tab becomes visible (see Main.qml) or via the button below --
// Technical.md section 42 forbids recomputing it on a timer.
Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 24

        RowLayout {
            Layout.fillWidth: true

            Label {
                text: qsTr("Dashboard")
                font.pixelSize: 18
                font.weight: Font.Medium
                color: "#F2F5F7"
                Layout.fillWidth: true
            }

            Button {
                text: qsTr("Refresh")
                flat: true
                onClicked: dashboardViewModel.refresh()
            }
        }

        GridLayout {
            columns: 2
            columnSpacing: 16
            rowSpacing: 16
            Layout.fillWidth: true

            ColumnLayout {
                Layout.fillWidth: true
                Label { text: qsTr("Today"); color: "#9AA5AD"; font.pixelSize: 13 }
                Label {
                    text: qsTr("%1 min focused").arg(dashboardViewModel.todayFocusMinutes)
                    color: "#F2F5F7"; font.pixelSize: 20
                }
                Label {
                    text: qsTr("%1 sessions · %2 breaks")
                        .arg(dashboardViewModel.todaySessionsCompleted)
                        .arg(dashboardViewModel.todayBreaksTaken)
                    color: "#C7D0D6"; font.pixelSize: 13
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Label { text: qsTr("Last 7 days"); color: "#9AA5AD"; font.pixelSize: 13 }
                Label {
                    text: qsTr("%1 min focused").arg(dashboardViewModel.weekFocusMinutes)
                    color: "#F2F5F7"; font.pixelSize: 20
                }
                Label {
                    text: qsTr("%1 sessions · %2 breaks")
                        .arg(dashboardViewModel.weekSessionsCompleted)
                        .arg(dashboardViewModel.weekBreaksTaken)
                    color: "#C7D0D6"; font.pixelSize: 13
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
