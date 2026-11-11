#!/bin/bash
# 只需运行一次：建立独立的 Python 环境并安装浏览器自动化库
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then
  echo "没有找到 python3。请先在终端运行： xcode-select --install   装完后重新运行本脚本。"
  exit 1
fi
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet playwright
if [ ! -d "/Applications/Google Chrome.app" ]; then
  echo "没有检测到 Chrome，下载一个自带的 Chromium（约 150MB）…"
  .venv/bin/playwright install chromium
fi
chmod +x run.sh schedule.sh
echo "安装完成。下一步运行： ./run.sh login"
