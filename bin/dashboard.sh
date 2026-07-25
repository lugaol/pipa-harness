#!/bin/bash
# dashboard.sh — start/stop the pipa_harness dashboard on :8080
set -eu
APP="$(cd "$(dirname "$0")/.." && pwd)/tools/dashboard/app.py"
PIDFILE="$(cd "$(dirname "$0")/.." && pwd)/state/dashboard.pid"
LOGFILE="$(cd "$(dirname "$0")/.." && pwd)/state/dashboard.log"
mkdir -p "$(dirname "$PIDFILE")"

case "${1:-start}" in
  start)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "dashboard already running (pid $(cat "$PIDFILE"))"
      exit 0
    fi
    echo "starting dashboard on :8080 ..."
    nohup python3 "$APP" > "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 1
    if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "  [ok] dashboard up — http://localhost:8080"
    else
      echo "  [!!] failed to start — see $LOGFILE"
      rm -f "$PIDFILE"
      exit 1
    fi
    ;;
  stop)
    if [ -f "$PIDFILE" ]; then
      kill "$(cat "$PIDFILE")" 2>/dev/null || true
      rm -f "$PIDFILE"
      echo "dashboard stopped"
    else
      echo "dashboard not running"
    fi
    ;;
  status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "dashboard running (pid $(cat "$PIDFILE")) — http://localhost:8080"
    else
      echo "dashboard not running"
    fi
    ;;
  *)
    echo "usage: $0 {start|stop|status}"
    exit 2
    ;;
esac
