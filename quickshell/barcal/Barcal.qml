// barcal — calendar widget for the Omarchy bar, powered by Caldir.
//
// Renders the JSON emitted by `barcal-render`: a date label on the bar with
// a month-grid popup whose event days are tinted with the active Omarchy
// theme's accent. Refreshes on a timer and immediately when
// `barcal-watcher` bumps the revision marker after `caldir sync`.
//
// Follows the shape of first-party bar widgets (omarchy.clock) and of
// third-party plugins (dev.reuk.sysstats): a Panel root so the widget joins
// the bar's panel navigation, a WidgetButton as the bar slot, and a
// KeyboardPanel popup with the shared panel chrome.

import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "barcal.barcal"
  ipcTarget: "barcal.barcal"

  readonly property int refreshMs: Math.max(5, setting("interval", 60)) * 1000

  // ---- State from `barcal-render` stdout JSON.
  property string barText: ""
  property string barClass: "no-events"
  property var palette: ({})
  property var eventsByDate: ({})
  property string revisionPath: ""
  property string renderFirstDay: "sunday"

  readonly property bool hasEvents: barClass === "has-events"
  readonly property string firstDay: renderFirstDay === "monday" ? "monday" : "sunday"
  readonly property color accent: palette.accent !== undefined ? palette.accent : Color.accent

  // ---- Today / viewed month. Today rolls over at midnight via SystemClock.
  property date today: new Date()
  readonly property string todayKey: root.dayKey(today.getFullYear(), today.getMonth(), today.getDate())
  property int viewYear: today.getFullYear()
  property int viewMonth: today.getMonth()
  readonly property bool viewingCurrentMonth: viewYear === today.getFullYear() && viewMonth === today.getMonth()

  readonly property color ink: bar ? bar.foreground : Color.foreground

  // The ModuleSlot sizes itself from the widget's implicit size; Panel does
  // not forward its children's, so the bar button has to be explicit.
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  // ---- Grid geometry, mirroring omarchy.clock's calendar popup.
  readonly property int cellWidth: Style.space(52)
  readonly property int cellHeight: Style.space(34)
  readonly property int cellSpacing: Style.space(2)
  readonly property int weekColumnWidth: Style.space(32)
  readonly property int gutterWidth: Style.space(14)

  function dayKey(year, month, day) {
    return year + "-" + ("0" + (month + 1)).slice(-2) + "-" + ("0" + day).slice(-2)
  }

  function isoWeek(year, month, day) {
    var date = new Date(year, month, day)
    date.setHours(0, 0, 0, 0)
    date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7))
    var week1 = new Date(date.getFullYear(), 0, 4)
    return 1 + Math.round(((date - week1) / 86400000 - 3 + ((week1.getDay() + 6) % 7)) / 7)
  }

  // Always six rows, so the popup is exactly as tall in February as in
  // August — the same read-out contract as the clock's grid.
  function computeGrid() {
    var offset = root.firstDay === "monday" ? 1 : 0
    var first = new Date(root.viewYear, root.viewMonth, 1)
    var start = new Date(first)
    start.setDate(first.getDate() - ((first.getDay() - offset) + 7) % 7)

    var weeks = []
    for (var w = 0; w < 6; w++) {
      var days = []
      for (var d = 0; d < 7; d++) {
        var day = new Date(start)
        day.setDate(start.getDate() + w * 7 + d)
        var key = root.dayKey(day.getFullYear(), day.getMonth(), day.getDate())
        var bucket = root.eventsByDate[key]
        days.push({
          key: key,
          day: day.getDate(),
          inMonth: day.getMonth() === root.viewMonth,
          hasEvents: bucket !== undefined,
          count: bucket !== undefined ? bucket.count : 0,
          today: key === root.todayKey
        })
      }
      var weekStart = new Date(start)
      weekStart.setDate(start.getDate() + w * 7)
      weeks.push({
        week: root.isoWeek(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate()),
        days: days
      })
    }
    return weeks
  }

  readonly property var weeks: root.computeGrid()

  function titlesText(key) {
    var bucket = root.eventsByDate[key]
    if (bucket === undefined || bucket.titles === undefined) return ""
    return bucket.titles.join(" · ")
  }

  function refresh() {
    if (!renderProc.running) renderProc.running = true
  }

  function scheduleRetry() {
    if (renderRetries >= 3) return
    renderRetries++
    renderRetryTimer.restart()
  }

  function goToToday() {
    root.viewYear = today.getFullYear()
    root.viewMonth = today.getMonth()
  }

  function moveMonth(delta) {
    var y = root.viewYear
    var m = root.viewMonth + delta
    while (m < 0) { m += 12; y-- }
    while (m > 11) { m -= 12; y++ }
    root.viewYear = y
    root.viewMonth = m
  }

  function openAgenda() {
    if (root.bar)
      root.bar.run("omarchy-launch-floating-terminal-with-presentation barcal-render --agenda-today")
  }

  function weekdayLabel(weekday) {
    return String(Qt.locale().dayName(weekday, Locale.ShortFormat)).replace(/\.$/, "").toUpperCase()
  }

  // Qt day numbers run Monday=1..Sunday=7; the grid renders Sunday- or
  // Monday-first order from the renderer's `week.firstDay`.
  function weekdayQtDay(index) {
    if (root.firstDay === "monday") return index + 1
    return index === 0 ? 7 : index
  }

  property int renderRetries: 0

  onOpenedChanged: {
    if (root.opened) root.refresh()
  }

  SystemClock {
    id: clock
    precision: SystemClock.Minutes
    onDateChanged: {
      if (root.dayKey(clock.date.getFullYear(), clock.date.getMonth(), clock.date.getDate()) === root.todayKey) return
      var followToday = root.viewingCurrentMonth
      root.today = clock.date
      if (followToday) root.goToToday()
    }
  }

  // ---- Periodic render + retry on failure.
  Timer {
    id: renderTimer
    interval: root.refreshMs
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Timer {
    id: renderRetryTimer
    interval: 2500
    onTriggered: root.refresh()
  }

  Process {
    id: renderProc
    command: ["barcal-render"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var raw = String(text || "").trim()
        if (!raw) {
          root.scheduleRetry()
          return
        }
        try {
          var data = JSON.parse(raw)
          root.barText = data.text || ""
          root.barClass = data.class || "no-events"
          root.palette = data.palette || {}
          root.renderFirstDay = data.week ? (data.week.firstDay || "sunday") : "sunday"
          root.revisionPath = data.revisionPath || ""
          var byDate = {}
          if (data.events) for (var i = 0; i < data.events.length; i++) {
            var entry = data.events[i]
            byDate[entry.date] = entry
          }
          root.eventsByDate = byDate
          root.renderRetries = 0
        } catch (err) {
          root.scheduleRetry()
        }
      }
    }
  }

  // ---- Instant refresh: the watcher bumps this file after caldir sync.
  FileView {
    id: revisionView
    watchChanges: true
    path: root.revisionPath !== "" ? "file://" + root.revisionPath : ""
    onFileChanged: root.refresh()
  }

  // ---- Bar button: date, prefixed with a dot when today has events.
  WidgetButton {
    id: button
    bar: root.bar
    text: root.hasEvents ? "● " + root.barText : root.barText
    tooltipText: root.hasEvents ? "Calendar — you have events today" : "Calendar"
    horizontalMargin: 8.75
    verticalPadding: 8.75

    onPressed: function(b) {
      if (b === Qt.RightButton) root.openAgenda()
      else root.toggle()
    }
  }

  // ---- Popup: month grid with event days.
  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(430))
    contentHeight: panel.fittedContentHeight(column.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onMoveRequested: function(dx, dy) {
        if (dx !== 0) root.moveMonth(dx)
        if (dy !== 0) root.moveMonth(dy * 12)
      }
      onActivateRequested: root.goToToday()
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Style.space(8)

        PanelHero {
          title: "Calendar"
          meta: root.barText
          foreground: root.ink
          fontFamily: root.fontFamily

          iconComponent: Text {
            text: "\uF0CED"
            color: root.hasEvents ? root.accent : root.ink
            font.family: root.fontFamily
            font.pixelSize: Style.font.display
          }

          trailingControl: Item {
            width: Style.space(44)
            height: Style.space(28)

            PanelActionButton {
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              iconText: "\uF0510"
              tooltipText: "Today's agenda"
              foreground: root.ink
              fontFamily: root.fontFamily
              onClicked: root.openAgenda()
            }
          }
        }

        // ---- Month grid: week numbers in a left gutter, then seven day
        //      columns. Six rows always, like the clock's calendar.
        Item {
          width: parent.width
          height: gridColumn.y + gridColumn.height

          WheelHandler {
            onWheel: function(event) {
              if (event.angleDelta.y === 0) return
              root.moveMonth(event.angleDelta.y > 0 ? -1 : 1)
            }
          }

          Column {
            id: gridColumn
            y: Style.space(8)
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Style.space(3)

            Row {
              spacing: root.cellSpacing

              Rectangle {
                width: root.weekColumnWidth
                height: Style.space(16)
                radius: Style.cornerRadius

                Text {
                  anchors.centerIn: parent
                  text: "W"
                  color: Qt.darker(root.ink, 1.9)
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.letterSpacing: 1
                  font.bold: true
                }
              }

              Item {
                width: root.gutterWidth
                height: Style.space(16)
              }

              Repeater {
                model: ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

                Text {
                  width: root.cellWidth
                  height: Style.space(16)
                  horizontalAlignment: Text.AlignHCenter
                  verticalAlignment: Text.AlignVCenter
                  text: root.weekdayLabel(root.weekdayQtDay(index))
                  color: Qt.darker(root.ink, 1.5)
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.letterSpacing: 1
                  font.bold: true
                }
              }
            }

            Repeater {
              model: root.weeks

              Row {
                required property var modelData
                spacing: root.cellSpacing

                Text {
                  width: root.weekColumnWidth
                  height: root.cellHeight
                  horizontalAlignment: Text.AlignHCenter
                  verticalAlignment: Text.AlignVCenter
                  text: modelData.week
                  color: Qt.darker(root.ink, 1.9)
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }

                Item {
                  width: root.gutterWidth
                  height: root.cellHeight
                }

                Repeater {
                  model: modelData.days

                  Rectangle {
                    required property var modelData

                    width: root.cellWidth
                    height: root.cellHeight
                    radius: Style.cornerRadius
                    color: modelData.inMonth && modelData.hasEvents
                      ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.14)
                      : "transparent"
                    border.width: modelData.today ? Style.spacing.hairline : 0
                    border.color: Style.normalBorderFor(root.ink, root.accent)

                    Text {
                      anchors.centerIn: parent
                      text: modelData.day
                      color: modelData.inMonth
                        ? (modelData.hasEvents ? root.accent : root.ink)
                        : Qt.darker(root.ink, 2.2)
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.body
                      font.bold: modelData.today
                    }

                    Rectangle {
                      anchors.horizontalCenter: parent.horizontalCenter
                      anchors.bottom: parent.bottom
                      anchors.bottomMargin: Style.space(3)
                      width: Style.space(4)
                      height: Style.space(4)
                      radius: width / 2
                      visible: modelData.hasEvents
                      color: root.accent
                    }

                    MouseArea {
                      id: dayMouse
                      anchors.fill: parent
                      hoverEnabled: true
                      acceptedButtons: Qt.NoButton

                      PanelToolTip {
                        visible: modelData.hasEvents && dayMouse.containsMouse
                        text: modelData.count > 1
                          ? root.titlesText(modelData.key)
                          : (root.titlesText(modelData.key) || "Event")
                        fontFamily: root.fontFamily
                      }
                    }
                  }
                }
              }
            }
          }

          Rectangle {
            x: gridColumn.x + root.weekColumnWidth + root.cellSpacing + Math.round((root.gutterWidth - width) / 2)
            y: gridColumn.y + Style.space(16) + gridColumn.spacing
            width: Style.spacing.hairline
            height: gridColumn.height - Style.space(16) - gridColumn.spacing
            color: root.ink
            opacity: 0.1
          }
        }

        // ---- Month stepping.
        Item {
          width: parent.width
          height: monthNav.height

          Item {
            id: monthNav
            anchors.horizontalCenter: parent.horizontalCenter
            width: gridColumn.width
            height: monthLabel.implicitHeight + Style.space(10)

            Text {
              id: monthLabel
              anchors.horizontalCenter: parent.horizontalCenter
              anchors.verticalCenter: parent.verticalCenter
              width: Style.space(130)
              horizontalAlignment: Text.AlignHCenter
              text: Qt.formatDate(new Date(root.viewYear, root.viewMonth, 1), "MMMM yyyy").toUpperCase()
              color: Qt.darker(root.ink, 1.4)
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              font.letterSpacing: 1
            }

            PanelActionButton {
              anchors.left: parent.left
              anchors.leftMargin: -Style.space(8)
              anchors.verticalCenter: parent.verticalCenter
              iconText: "\uF0141"
              tooltipText: "Previous month"
              foreground: root.ink
              fontFamily: root.fontFamily
              onClicked: root.moveMonth(-1)
            }

            PanelActionButton {
              anchors.right: parent.right
              anchors.rightMargin: -Style.space(8)
              anchors.verticalCenter: parent.verticalCenter
              iconText: "\uF0142"
              tooltipText: "Next month"
              foreground: root.ink
              fontFamily: root.fontFamily
              onClicked: root.moveMonth(1)
            }
          }
        }
      }
    }
  }
}
