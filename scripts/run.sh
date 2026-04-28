#!/bin/bash
# Web Monitor 便捷脚本
# 自动设置环境变量和路径

# 添加 uv 到 PATH
export PATH="$HOME/.local/bin:$PATH"

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 执行 monitor.py
uv run --with beautifulsoup4 python "$SCRIPT_DIR/monitor.py" "$@"
