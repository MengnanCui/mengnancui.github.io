#!/bin/bash
# 设置每天定时运行：  ./schedule.sh 12:30
# 取消定时：          ./schedule.sh off
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
LABEL="local.xhs-digest"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl unload "$PLIST" 2>/dev/null || true
if [ "$1" = "off" ]; then
  rm -f "$PLIST"
  echo "已取消定时。"
  exit 0
fi
if ! [[ "$1" =~ ^([0-9]{1,2}):([0-9]{2})$ ]]; then
  echo "用法： ./schedule.sh 12:30    或    ./schedule.sh off"
  exit 1
fi
HOUR=$((10#${BASH_REMATCH[1]}))
MIN=$((10#${BASH_REMATCH[2]}))

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$DIR/run.sh</string></array>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>$HOUR</integer>
    <key>Minute</key><integer>$MIN</integer>
  </dict>
  <key>StandardOutPath</key><string>$DIR/last-run.log</string>
  <key>StandardErrorPath</key><string>$DIR/last-run.log</string>
</dict></plist>
EOF
launchctl load "$PLIST"
echo "已设置：每天 $1 自动刷一次并打开简报。如果当时 Mac 在睡眠，会在唤醒后补跑。"
