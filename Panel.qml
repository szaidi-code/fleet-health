import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons

Panel {
  id: root
  moduleName: "fleet.health"
  ipcTarget: "fleet.health"
  manageIpc: false

  IpcHandler {
    target: "fleet.health"
    function toggle() { root.toggle() }
    function open() { root.open() }
    function close() { root.close() }
    function refresh() { root.refresh() }
  }

  property bool connected: false
  property string serverUrl: (settings && settings.serverUrl) || "https://localhost:1337"
  property string clusterStatus: "Unknown"
  property int totalNodes: 0
  property int onlineNodes: 0
  property int offlineNodes: 0
  property real avgLoad1m: 0.0
  property real totalRamGb: 0.0
  property real usedRamGb: 0.0
  property real ramPercent: 0.0
  property string kernelVersion: "Linux"
  property var nodes: []
  property string statusError: ""
  property string activeTab: "all" // "all" or specific host

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property color barIconColor: connected ? (offlineNodes > 0 ? urgent : foreground) : dim

  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  function refresh() {
    if (!reportProc.running) reportProc.running = true
  }

  function openConsole() {
    Qt.openUrlExternally(serverUrl)
    root.close()
  }

  function copyText(val, label) {
    if (root.bar && typeof root.bar.run === "function") {
      root.bar.run("wl-copy " + val)
      root.bar.run("omarchy-notification-send -g 󰒋 'Fleet DM' 'Copied " + label + ": " + val + "'")
    }
  }

  Process {
    id: reportProc
    command: [
      Quickshell.env("HOME") + "/.local/bin/omarchy-fleet-health-report"
    ]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var data = JSON.parse(String(text || "").trim())
          root.connected = data.connected === true
          root.serverUrl = data.server_url || root.serverUrl
          var sum = data.summary || {}
          root.clusterStatus = sum.status || "Unknown"
          root.totalNodes = sum.total_nodes || 0
          root.onlineNodes = sum.online_nodes || 0
          root.offlineNodes = sum.offline_nodes || 0
          root.avgLoad1m = sum.avg_load_1m || 0.0
          root.totalRamGb = sum.total_ram_gb || 0.0
          root.usedRamGb = sum.used_ram_gb || 0.0
          root.ramPercent = sum.ram_percent || 0.0
          root.kernelVersion = sum.kernel_version || "Linux"
          root.nodes = data.nodes || []
          root.statusError = data.error || ""
        } catch (e) {
          root.connected = false
          root.statusError = "Failed to parse Fleet report"
        }
      }
    }
  }

  Timer {
    id: refreshTimer
    interval: ((settings && settings.refreshIntervalSec) || 15) * 1000
    repeat: true
    running: true
    onTriggered: root.refresh()
  }

  Component.onCompleted: root.refresh()
  onOpenedChanged: if (opened) root.refresh()

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰒋"
    foreground: root.barIconColor
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) root.refresh()
      else if (buttonCode === Qt.MiddleButton) root.openConsole()
      else root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(480))
    contentHeight: panel.fittedContentHeight(mainCol.implicitHeight + Style.spacing.xl * 2, Style.space(680))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTextKey: function(t) {
        if (t === "r" || t === "R") root.refresh()
        else if (t === "o" || t === "O") root.openConsole()
      }

      Flickable {
        id: panelFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: mainCol.implicitHeight + Style.spacing.xl * 2
        clip: true

        Column {
          id: mainCol
          width: parent.width - Style.spacing.xl * 2
          anchors.horizontalCenter: parent.horizontalCenter
          anchors.top: parent.top
          anchors.topMargin: Style.spacing.xl
          spacing: Style.spacing.lg

          // ==================== 1. HERO / CLUSTER HEALTH ====================
          BorderSurface {
            width: parent.width
            implicitHeight: heroCol.implicitHeight + Style.spacing.lg * 2
            color: Style.selectedFillFor(root.foreground, Color.accent)
            radius: Style.cornerRadius

            Column {
              id: heroCol
              anchors.fill: parent
              anchors.margins: Style.spacing.lg
              spacing: Style.spacing.md

              RowLayout {
                width: parent.width

                Text {
                  text: "󰒋"
                  font.family: root.fontFamily
                  font.pixelSize: Style.space(26)
                  color: root.connected ? root.foreground : root.dim
                }

                ColumnLayout {
                  Layout.fillWidth: true
                  spacing: 1

                  Text {
                    text: "Fleet DM Health Report"
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.title
                    font.bold: true
                    color: root.foreground
                  }

                  Text {
                    text: root.connected ? (root.serverUrl + " • " + root.onlineNodes + "/" + root.totalNodes + " nodes online") : (root.statusError || "Disconnected")
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    color: root.dim
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                  }
                }

                BorderSurface {
                  implicitWidth: statusBadgeText.implicitWidth + Style.spacing.md * 2
                  implicitHeight: statusBadgeText.implicitHeight + Style.spacing.xs * 2
                  radius: Style.cornerRadius
                  color: root.clusterStatus === "Healthy" ? root.alpha(Color.accent, 0.2) : root.alpha(root.urgent, 0.2)

                  Text {
                    id: statusBadgeText
                    anchors.centerIn: parent
                    text: root.clusterStatus.toUpperCase()
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    font.bold: true
                    color: root.clusterStatus === "Healthy" ? Color.accent : root.urgent
                  }
                }
              }

              // ---------- Cluster Telemetry Pills ----------
              RowLayout {
                width: parent.width
                spacing: Style.spacing.sm

                // CPU Load Pill
                BorderSurface {
                  Layout.fillWidth: true
                  implicitHeight: Style.space(48)
                  radius: Style.cornerRadius
                  color: Color.popups.background

                  Column {
                    anchors.centerIn: parent
                    spacing: 2
                    Text {
                      text: "AVG CPU LOAD"
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      color: root.dim
                      anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                      text: root.avgLoad1m.toFixed(2)
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.body
                      font.bold: true
                      color: root.foreground
                      anchors.horizontalCenter: parent.horizontalCenter
                    }
                  }
                }

                // Memory Pill
                BorderSurface {
                  Layout.fillWidth: true
                  implicitHeight: Style.space(48)
                  radius: Style.cornerRadius
                  color: Color.popups.background

                  Column {
                    anchors.centerIn: parent
                    spacing: 2
                    Text {
                      text: "RAM USED"
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      color: root.dim
                      anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                      text: root.ramPercent.toFixed(1) + "% (" + root.usedRamGb + "G)"
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.body
                      font.bold: true
                      color: root.foreground
                      anchors.horizontalCenter: parent.horizontalCenter
                    }
                  }
                }

                // Kernel Pill
                BorderSurface {
                  Layout.fillWidth: true
                  implicitHeight: Style.space(48)
                  radius: Style.cornerRadius
                  color: Color.popups.background

                  Column {
                    anchors.centerIn: parent
                    spacing: 2
                    Text {
                      text: "KERNEL"
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      color: root.dim
                      anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                      text: root.kernelVersion
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.body
                      font.bold: true
                      color: root.foreground
                      anchors.horizontalCenter: parent.horizontalCenter
                    }
                  }
                }
              }
            }
          }

          // ==================== 2. NODES HEALTH BREAKDOWN ====================
          RowLayout {
            width: parent.width

            Text {
              text: "Cluster Nodes (" + root.nodes.length + ")"
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              color: root.foreground
              Layout.fillWidth: true
            }

            Button {
              text: "Open Web Console"
              fontFamily: root.fontFamily
              fontSize: Style.font.caption
              onClicked: root.openConsole()
            }
          }

          Repeater {
            model: root.nodes

            BorderSurface {
              required property var modelData
              required property int index

              width: mainCol.width
              implicitHeight: hostCardCol.implicitHeight + Style.spacing.md * 2
              radius: Style.cornerRadius
              color: Color.popups.background
              borderSpec: Border.flat(root.dim, 1)

              Column {
                id: hostCardCol
                anchors.fill: parent
                anchors.margins: Style.spacing.md
                spacing: Style.spacing.md

                // Host Header
                RowLayout {
                  width: parent.width

                  Text {
                    text: "󰌢 " + modelData.hostname
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.body
                    font.bold: true
                    color: root.foreground
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                  }

                  Text {
                    text: modelData.ip
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    color: root.dim
                  }

                  Text {
                    text: "• " + modelData.status.toUpperCase()
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    font.bold: true
                    color: modelData.status === "online" ? Color.accent : root.urgent
                  }
                }

                // OS & Kernel line
                Text {
                  text: "Kernel " + modelData.kernel.version + " • Uptime: " + (modelData.kernel.uptime_human || "online") + " • " + modelData.os + " (osquery " + modelData.osquery + ")"
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  color: root.dim
                  width: parent.width
                  elide: Text.ElideRight
                }

                // CPU & Load Bar
                Column {
                  width: parent.width
                  spacing: 2

                  RowLayout {
                    width: parent.width
                    Text {
                      text: "CPU: " + modelData.cpu.brand + " (" + modelData.cpu.cores + " cores)"
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      color: root.foreground
                      Layout.fillWidth: true
                      elide: Text.ElideRight
                    }
                    Text {
                      text: "Load: " + modelData.cpu.load_1m.toFixed(2) + " (1m) / " + modelData.cpu.load_5m.toFixed(2) + " (5m)"
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      color: root.dim
                    }
                  }

                  Rectangle {
                    width: parent.width
                    height: Style.space(4)
                    radius: 2
                    color: Style.selectedFillFor(root.foreground, Color.accent)

                    Rectangle {
                      width: Math.min(parent.width, (modelData.cpu.load_1m / modelData.cpu.cores) * parent.width)
                      height: parent.height
                      radius: 2
                      color: (modelData.cpu.load_1m / modelData.cpu.cores) > 0.8 ? root.urgent : Color.accent
                    }
                  }
                }

                // Memory & Allocation Bar
                Column {
                  width: parent.width
                  spacing: 2

                  RowLayout {
                    width: parent.width
                    Text {
                      text: "Memory: " + modelData.memory.used_mb + " MB used / " + modelData.memory.total_mb + " MB (" + modelData.memory.percent + "%)"
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      color: root.foreground
                      Layout.fillWidth: true
                    }
                    Text {
                      text: "Free: " + modelData.memory.free_mb + " MB • Cached: " + modelData.memory.cached_mb + " MB"
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      color: root.dim
                    }
                  }

                  Rectangle {
                    width: parent.width
                    height: Style.space(4)
                    radius: 2
                    color: Style.selectedFillFor(root.foreground, Color.accent)

                    Rectangle {
                      width: Math.min(parent.width, (modelData.memory.percent / 100.0) * parent.width)
                      height: parent.height
                      radius: 2
                      color: modelData.memory.percent > 85 ? root.urgent : Color.accent
                    }
                  }
                }
              }

              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.copyText(modelData.ip, "node IP")
              }
            }
          }
        }
      }
    }
  }
}
