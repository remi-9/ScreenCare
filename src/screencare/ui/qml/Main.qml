import QtQuick
import QtQuick.Window

// Phase 1 placeholder window. Presentation only — no business logic
// belongs in QML (ScreenCare — Technical.md, section 24). This will be
// replaced by the real focus timer / dashboard views in later phases.
Window {
    id: root

    width: 420
    height: 280
    minimumWidth: 360
    minimumHeight: 240
    visible: true
    title: qsTr("ScreenCare")
    color: "#101418"

    Column {
        anchors.centerIn: parent
        spacing: 12
        width: 320

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: qsTr("ScreenCare")
            font.pixelSize: 28
            font.weight: Font.Medium
            color: "#F2F5F7"
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width
            text: qsTr("Focus and wellness companion — coming together, one milestone at a time.")
            font.pixelSize: 14
            color: "#9AA5AD"
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
