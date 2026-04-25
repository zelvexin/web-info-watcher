#!/bin/bash
# Web Monitor 便捷脚本
# 自动设置环境变量和路径

# 设置 web-monitor 数据目录（在 skill 目录内）
export WEB_MONITOR_DIR="/workspace/projects/workspace/skills/web-monitor/data"

# 添加 uv 到 PATH
export PATH="$HOME/.local/bin:$PATH"

# 切换到 workspace 目录
cd /workspace/projects/workspace

# 执行 web-monitor 命令
uv run --with beautifulsoup4 python skills/web-monitor/scripts/monitor.py "$@"
