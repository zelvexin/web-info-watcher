#!/bin/bash
# Web Monitor 定期检查脚本
# 每分钟检查所有监控的网站是否有更新

# 设置 web-monitor 数据目录
export WEB_MONITOR_DIR="/workspace/projects/workspace/skills/web-monitor/data"

# 脚本目录
SCRIPT_DIR="/workspace/projects/workspace/skills/web-monitor/scripts"

# 监控配置
# ==================
# 检查间隔（分钟）
INTERVAL=1

# 开始监控时间（年-月-日 时:分）
START_TIME="2026-04-25 20:17"

# 结束监控时间（年-月-日 时:分）
END_TIME="2026-04-25 20:20"
# ==================

# 切换到工作目录
cd /workspace/projects/workspace

# 执行 Python 脚本，传递参数
python3 "$SCRIPT_DIR/periodic_check.py" "$INTERVAL" "$START_TIME" "$END_TIME"
