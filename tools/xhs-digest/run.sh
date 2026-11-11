#!/bin/bash
# ./run.sh login   第一次扫码登录
# ./run.sh         刷一次并生成简报
cd "$(dirname "$0")"
exec .venv/bin/python xhs_digest.py "$@"
