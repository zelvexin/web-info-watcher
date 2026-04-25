#!/usr/bin/env python3
"""
Web Monitor 循环检查脚本
在指定时间窗口内，每隔一段时间循环检查所有监控的网站

用法:
    python periodic_check.py <interval_minutes> <start_datetime> <end_datetime>

参数:
    interval_minutes: 检查间隔（分钟）
    start_datetime: 开始监控时间 (格式: YYYY-MM-DD HH:MM)
    end_datetime: 结束监控时间 (格式: YYYY-MM-DD HH:MM)

示例:
  python periodic_check.py 1 "2026-04-25 19:45" "2026-04-25 19:50"
  # 从 19:45 到 19:50，每1分钟检查一次
"""

import json
import os
import subprocess
import sys
import argparse
import time
from datetime import datetime
from pathlib import Path

# 配置
DATA_DIR = Path(os.environ.get("WEB_MONITOR_DIR", Path.home() / ".web-monitor"))
WATCHES_FILE = DATA_DIR / "watches.json"
SCRIPT_DIR = Path(__file__).parent
LOG_FILE = DATA_DIR / "periodic_check.log"


def log_message(message: str):
    """记录日志到文件并输出到控制台"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}"
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, 'a') as f:
        f.write(log_line + "\n")
        f.flush()
    print(log_line, flush=True)


def parse_datetime(datetime_str: str) -> datetime:
    """解析日期时间字符串"""
    return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')


def is_within_monitoring_window(start_time: datetime, end_time: datetime) -> bool:
    """检查当前时间是否在监控时间窗口内"""
    now = datetime.now()
    
    today_start = datetime.combine(now.date(), start_time.time())
    today_end = datetime.combine(now.date(), end_time.time())
    
    if start_time.date() != end_time.date():
        # 跨天的情况
        return (now >= start_time) or (now <= end_time)
    else:
        # 同一天的情况
        return today_start <= now <= today_end


def load_watches() -> dict:
    """加载 watches.json"""
    if WATCHES_FILE.exists():
        return json.loads(WATCHES_FILE.read_text())
    return {"watches": []}


def perform_check_all():
    """执行一次完整的网站检查"""
    data = load_watches()
    watches = data.get("watches", [])
    
    if not watches:
        log_message("⚠️  没有监控项需要检查")
        return True
    
    log_message(f"发现 {len(watches)} 个监控项，开始检查...")
    
    for i, watch in enumerate(watches, 1):
        name = watch.get('name', '')
        url = watch.get('url', '')
        identifier = name if name else url
        
        log_message(f"[{i}/{len(watches)}] 检查: {identifier[:50]}...")
        
        try:
            result = subprocess.run(
                ['bash', f'{SCRIPT_DIR}/run.sh', 'check', identifier],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        log_message(f"  📤 {line}")
            
            if result.stderr:
                for line in result.stderr.strip().split('\n'):
                    if line.strip():
                        log_message(f"  ⚠️  {line}")
            
            if result.returncode == 0:
                log_message(f"  ✅ 检查完成")
            else:
                log_message(f"  ❌ 检查失败 (返回码: {result.returncode})")
                
        except subprocess.TimeoutExpired:
            log_message(f"  ⏱️  检查超时")
        except Exception as e:
            log_message(f"  ❌ 检查异常: {e}")
    
    log_message(f"✅ 本次检查完成，共检查 {len(watches)} 个监控项")
    return True


def scheduled_check_loop(interval_minutes: int, start_time: str, end_time: str):
    """
    执行循环检查（从 periodic_check.py 的主逻辑）
    
    Args:
        interval_minutes: 检查间隔（分钟）
        start_time: 开始时间 (YYYY-MM-DD HH:MM)
        end_time: 结束时间 (YYYY-MM-DD HH:MM)
    """
    try:
        start_datetime = parse_datetime(start_time)
        end_datetime = parse_datetime(end_time)
    except ValueError as e:
        log_message(f"❌ 时间参数错误: {e}")
        return 1
    
    # 检查当前时间是否在监控窗口内
    if not is_within_monitoring_window(start_datetime, end_datetime):
        now = datetime.now()
        log_message(f"⏸️  当前时间 {now.strftime('%Y-%m-%d %H:%M')} 不在监控时间窗口内")
        log_message(f"   监控窗口: {start_datetime.strftime('%Y-%m-%d %H:%M')} - {end_datetime.strftime('%Y-%m-%d %H:%M')}")
        
        if now > end_datetime:
            log_message("❌ 监控窗口已结束")
            return 0
        
        if now < start_datetime:
            wait_seconds = (start_datetime - now).total_seconds()
            log_message(f"⏳ 等待到 {start_datetime.strftime('%H:%M')} ({int(wait_seconds)} 秒)...")
            
            try:
                time.sleep(wait_seconds)
                log_message(f"⏰ 到达开始时间 {start_datetime.strftime('%H:%M')}")
            except KeyboardInterrupt:
                log_message("❌ 用户中断等待")
                return 1
        
        if not is_within_monitoring_window(start_datetime, end_datetime):
            log_message(f"⏸️  等待后仍不在监控时间窗口内，跳过检查")
            return 0
    
    log_message(f"✅ 当前时间 {datetime.now().strftime('%H:%M')} 在监控窗口内，开始循环检查...")
    log_message(f"🔄 每 {interval_minutes} 分钟检查一次")
    
    # 循环检查
    check_count = 0
    while True:
        check_count += 1
        log_message("")
        log_message(f"🔔 第 {check_count} 次检查开始")
        
        # 执行检查
        perform_check_all()
        
        # 检查是否还在监控窗口内
        if not is_within_monitoring_window(start_datetime, end_datetime):
            now = datetime.now()
            log_message("")
            log_message(f"⏸️  监控窗口已结束 (当前时间: {now.strftime('%H:%M')})")
            log_message(f"✅ 循环检查结束，共执行 {check_count} 次检查")
            return 0
        
        # 等待下一次检查
        wait_seconds = interval_minutes * 60
        
        now = datetime.now()
        time_to_end = (end_datetime - now).total_seconds()
        
        if time_to_end < wait_seconds:
            log_message(f"⏰ 距离窗口结束不足 {interval_minutes} 分钟，准备退出")
        else:
            log_message(f"⏳ 等待 {interval_minutes} 分钟后进行下一次检查...")
            try:
                time.sleep(wait_seconds)
            except KeyboardInterrupt:
                log_message("❌ 用户中断等待")
                return 1
    
    return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Web Monitor 循环检查脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python periodic_check.py 1 "2026-04-25 19:45" "2026-04-25 19:50"
  # 从 19:45 到 19:50，每1分钟检查一次
        '''
    )
    
    parser.add_argument(
        'interval',
        type=int,
        help='检查间隔（分钟）'
    )
    
    parser.add_argument(
        'start_time',
        type=str,
        help='开始监控时间 (格式: YYYY-MM-DD HH:MM)'
    )
    
    parser.add_argument(
        'end_time',
        type=str,
        help='结束监控时间 (格式: YYYY-MM-DD HH:MM)'
    )
    
    args = parser.parse_args()
    
    # 执行循环检查
    exit_code = scheduled_check_loop(args.interval, args.start_time, args.end_time)
    
    log_message(f"程序结束 (退出码: {exit_code})")
    log_message("")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

# 导出的函数，供其他模块使用
__all__ = [
    "log_message",
    "parse_datetime",
    "is_within_monitoring_window",
    "load_watches",
    "perform_check_all"
]
