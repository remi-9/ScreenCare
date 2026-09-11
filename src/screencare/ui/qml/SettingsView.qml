import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Every control here binds straight to SettingsViewModel, which is itself
// only a thin wrapper over AppSettings -- bounds are enforced there, not in
// QML (Technical.md section 30: "Never trust QML input values directly").
ScrollView {
    id: root
    clip: true
    contentWidth: availableWidth

    ColumnLayout {
        width: root.availableWidth
        spacing: 20

        Label {
            Layout.topMargin: 24
            Layout.leftMargin: 24
            text: qsTr("Focus")
            font.pixelSize: 13
            font.weight: Font.DemiBold
            color: "#9AA5AD"
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Label { text: qsTr("Focus duration (min)"); Layout.fillWidth: true; color: "#F2F5F7" }
            SpinBox {
                from: 10; to: 120; stepSize: 5
                value: settingsViewModel.focusMinutes
                onValueModified: settingsViewModel.focusMinutes = value
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Label { text: qsTr("Short break duration (min)"); Layout.fillWidth: true; color: "#F2F5F7" }
            SpinBox {
                from: 1; to: 30
                value: settingsViewModel.shortBreakMinutes
                onValueModified: settingsViewModel.shortBreakMinutes = value
            }
        }

        Label {
            Layout.leftMargin: 24
            text: qsTr("Hydration")
            font.pixelSize: 13
            font.weight: Font.DemiBold
            color: "#9AA5AD"
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Label { text: qsTr("Reminder interval (min)"); Layout.fillWidth: true; color: "#F2F5F7" }
            SpinBox {
                from: 30; to: 180; stepSize: 5
                value: settingsViewModel.hydrationIntervalMinutes
                onValueModified: settingsViewModel.hydrationIntervalMinutes = value
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Label { text: qsTr("Strict hourly reminders"); Layout.fillWidth: true; color: "#F2F5F7" }
            Switch {
                checked: settingsViewModel.hydrationStrict
                onToggled: settingsViewModel.hydrationStrict = checked
            }
        }

        Label {
            Layout.leftMargin: 24
            text: qsTr("Eye rest")
            font.pixelSize: 13
            font.weight: Font.DemiBold
            color: "#9AA5AD"
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Label { text: qsTr("Enable eye-rest prompts"); Layout.fillWidth: true; color: "#F2F5F7" }
            Switch {
                checked: settingsViewModel.eyeReminderEnabled
                onToggled: settingsViewModel.eyeReminderEnabled = checked
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            enabled: settingsViewModel.eyeReminderEnabled
            Label { text: qsTr("Reminder interval (min)"); Layout.fillWidth: true; color: "#F2F5F7" }
            SpinBox {
                from: 10; to: 60; stepSize: 5
                value: settingsViewModel.eyeReminderMinutes
                onValueModified: settingsViewModel.eyeReminderMinutes = value
            }
        }

        Label {
            Layout.leftMargin: 24
            text: qsTr("Notifications")
            font.pixelSize: 13
            font.weight: Font.DemiBold
            color: "#9AA5AD"
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Label { text: qsTr("Enable notifications"); Layout.fillWidth: true; color: "#F2F5F7" }
            Switch {
                checked: settingsViewModel.notificationsEnabled
                onToggled: settingsViewModel.notificationsEnabled = checked
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Label { text: qsTr("Sound"); Layout.fillWidth: true; color: "#F2F5F7" }
            Switch {
                checked: settingsViewModel.soundEnabled
                onToggled: settingsViewModel.soundEnabled = checked
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Label { text: qsTr("Quiet mode duration (min)"); Layout.fillWidth: true; color: "#F2F5F7" }
            SpinBox {
                from: 15; to: 240; stepSize: 15
                value: settingsViewModel.quietModeMinutes
                onValueModified: settingsViewModel.quietModeMinutes = value
            }
        }

        Label {
            Layout.leftMargin: 24
            text: qsTr("General")
            font.pixelSize: 13
            font.weight: Font.DemiBold
            color: "#9AA5AD"
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Label { text: qsTr("Launch at login"); Layout.fillWidth: true; color: "#F2F5F7" }
            Switch {
                checked: settingsViewModel.launchAtLogin
                onToggled: settingsViewModel.launchAtLogin = checked
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Layout.bottomMargin: 24
            Label { text: qsTr("Theme"); Layout.fillWidth: true; color: "#F2F5F7" }
            ComboBox {
                id: themeCombo
                model: ["system", "light", "dark"]
                currentIndex: model.indexOf(settingsViewModel.theme)
                onActivated: settingsViewModel.theme = model[currentIndex]
            }
        }
    }
}
