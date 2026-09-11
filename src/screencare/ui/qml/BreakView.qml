import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The full-window recovery break, straight from Concept.md's "Recovery
// Breaks" and "Flow Protection" sections. Never ends the focus session on
// its own -- every action here maps to one BreakViewModel slot, which
// calls straight through to AppSession.
Rectangle {
    id: root
    color: "#0B0F13"

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 20
        width: Math.min(root.width - 64, 380)

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: breakViewModel.isReady ? qsTr("Ready when you are") : qsTr("Focus complete")
            font.pixelSize: 26
            font.weight: Font.Medium
            color: "#F2F5F7"
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            visible: !breakViewModel.isReady
            text: qsTr("Time for a reset.")
            font.pixelSize: 15
            color: "#C7D0D6"
        }

        ColumnLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 6
            visible: !breakViewModel.isReady

            Label { text: "🚶  " + qsTr("Walk around"); color: "#C7D0D6"; font.pixelSize: 14 }
            Label {
                text: "💧  " + qsTr("Drink or refill water")
                visible: breakViewModel.includeHydration
                color: "#C7D0D6"
                font.pixelSize: 14
            }
            Label { text: "👀  " + qsTr("Look into the distance"); color: "#C7D0D6"; font.pixelSize: 14 }
            Label {
                text: "🙆  " + qsTr("Move your neck and shoulders")
                color: "#C7D0D6"
                font.pixelSize: 14
            }
        }

        // -- Recovery due: Flow Protection choices ---------------------------

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 10
            visible: breakViewModel.isRecoveryDue

            Button {
                Layout.fillWidth: true
                text: qsTr("Start Break")
                highlighted: true
                onClicked: breakViewModel.startBreak()
            }
            Button {
                Layout.fillWidth: true
                text: qsTr("Finish Current Thought")
                enabled: breakViewModel.canFinishCurrentThought
                onClicked: breakViewModel.finishCurrentThought()
            }
            Button {
                Layout.fillWidth: true
                text: qsTr("Extend 5 Minutes")
                enabled: breakViewModel.canExtend
                onClicked: breakViewModel.extend()
            }
        }

        // -- Breaking: come back whenever ------------------------------------

        Button {
            Layout.alignment: Qt.AlignHCenter
            visible: breakViewModel.isBreaking
            text: qsTr("I'm back")
            highlighted: true
            onClicked: breakViewModel.endBreak()
        }

        // -- Ready: acknowledge and move on -----------------------------------

        Button {
            Layout.alignment: Qt.AlignHCenter
            visible: breakViewModel.isReady
            text: qsTr("Done")
            highlighted: true
            onClicked: breakViewModel.acknowledgeReady()
        }
    }
}
