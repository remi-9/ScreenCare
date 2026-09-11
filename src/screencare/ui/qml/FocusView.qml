import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Priorities per Implementation Standards.md section 27: current state,
// time remaining, next recovery, start/pause controls, quick wellness
// actions -- over statistics (that's DashboardView's job).
Item {
    id: root

    function formatTime(totalSeconds) {
        var s = Math.max(0, Math.floor(totalSeconds))
        var m = Math.floor(s / 60)
        var sec = s % 60
        return (m < 10 ? "0" + m : m) + ":" + (sec < 10 ? "0" + sec : sec)
    }

    function modeLabel(mode) {
        if (mode === "classic") return qsTr("Classic Pomodoro")
        if (mode === "deep_focus") return qsTr("Deep Focus")
        if (mode === "adaptive") return qsTr("Adaptive Focus")
        return ""
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 22
        width: Math.min(root.width - 48, 360)

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 8

            Label {
                text: focusViewModel.state === "stopped" ? qsTr("Ready to focus")
                      : root.modeLabel(focusViewModel.mode)
                font.pixelSize: 15
                color: "#9AA5AD"
            }

            Label {
                text: qsTr("· Quiet")
                visible: focusViewModel.isQuiet
                font.pixelSize: 15
                color: "#6E97B5"
            }
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            visible: focusViewModel.state === "focusing" || focusViewModel.state === "paused"
            text: root.formatTime(focusViewModel.remainingSeconds)
            font.pixelSize: 56
            font.weight: Font.Light
            color: "#F2F5F7"
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            visible: focusViewModel.taskLabel !== "" &&
                     (focusViewModel.state === "focusing" || focusViewModel.state === "paused")
            text: focusViewModel.taskLabel
            font.pixelSize: 14
            color: "#C7D0D6"
        }

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: reminderLabel.implicitWidth + 24
            Layout.preferredHeight: reminderLabel.implicitHeight + 16
            visible: focusViewModel.reminderText !== ""
            radius: 8
            color: "#1B2530"

            Label {
                id: reminderLabel
                anchors.centerIn: parent
                text: focusViewModel.reminderText
                color: "#CFE8FF"
                font.pixelSize: 13
            }

            MouseArea {
                anchors.fill: parent
                onClicked: focusViewModel.dismissReminder()
            }
        }

        // -- Stopped: choose how to start ------------------------------------

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 10
            visible: focusViewModel.state === "stopped"

            TextField {
                id: taskField
                Layout.fillWidth: true
                placeholderText: qsTr("What are you working on? (optional)")
            }

            Button {
                Layout.fillWidth: true
                text: qsTr("Classic Pomodoro (25 min)")
                onClicked: focusViewModel.startClassic(taskField.text)
            }
            Button {
                Layout.fillWidth: true
                text: qsTr("Deep Focus (50 min)")
                onClicked: focusViewModel.startDeepFocus(taskField.text)
            }
            Button {
                Layout.fillWidth: true
                text: qsTr("Adaptive Focus (%1 min)").arg(focusViewModel.adaptiveFocusMinutes)
                onClicked: focusViewModel.startAdaptive(taskField.text)
            }
        }

        // -- Focusing / paused: controls --------------------------------------

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 12
            visible: focusViewModel.state === "focusing" || focusViewModel.state === "paused"

            Button {
                text: focusViewModel.state === "paused" ? qsTr("Resume") : qsTr("Pause")
                onClicked: {
                    if (focusViewModel.state === "paused") focusViewModel.resume()
                    else focusViewModel.pause()
                }
            }
            Button {
                text: qsTr("I'm Stuck")
                enabled: focusViewModel.state === "focusing"
                onClicked: focusViewModel.startIdeaWalk()
            }
            Button {
                text: qsTr("Stop")
                onClicked: focusViewModel.stop()
            }
        }

        // -- Idea walk: a short pause, handled inline ---------------------------

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 10
            visible: focusViewModel.state === "idea_walk"

            Label {
                Layout.fillWidth: true
                text: qsTr("Take a 5-minute walk. Don't force it — just give yourself space.")
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                color: "#C7D0D6"
            }

            TextField {
                id: ideaNoteField
                Layout.fillWidth: true
                placeholderText: qsTr("Anything come to mind? (optional)")
            }

            Button {
                Layout.fillWidth: true
                text: qsTr("Back to focus")
                onClicked: {
                    focusViewModel.returnFromIdeaWalk(ideaNoteField.text)
                    ideaNoteField.text = ""
                }
            }
            Button {
                Layout.fillWidth: true
                text: qsTr("End session instead")
                onClicked: focusViewModel.endSessionFromIdeaWalk()
            }
        }

        Button {
            Layout.alignment: Qt.AlignHCenter
            text: focusViewModel.isQuiet ? qsTr("End quiet mode") : qsTr("Quiet for a while")
            flat: true
            onClicked: {
                if (focusViewModel.isQuiet) focusViewModel.exitQuietMode()
                else focusViewModel.enterQuietMode()
            }
        }
    }
}
