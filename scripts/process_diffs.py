#!/usr/bin/env python3
"""
Web Monitor Diff 文件处理脚本（简化版，作为模块导入）
使用 LLM 分析 diff 文件，提取招生信息，并发送邮件
"""

import json
import os
import sys
import argparse
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import List, Dict, Optional
import subprocess
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

# 配置
DATA_DIR = Path(os.environ.get("WEB_MONITOR_DIR", Path.home() / ".web-monitor"))
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
LOG_FILE = DATA_DIR / "process_diffs.log"

# Email configuration
TARGET_EMAIL = "20223002145@hainanu.edu.cn"
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 587
SMTP_USER = "3160142733@qq.com"
SMTP_PASSWORD = ""  # 需要填写授权码

# LLM configuration
DEEPSEEK_API_KEY = "sk-2bb769aed53c454d967aa296500ff781"
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1/chat/completions"
RELEVANT_TOPICS = ["夏令营", "预推免", "考研", "博士招生", "硕士招生"]


def log_message(message: str):
    """记录日志到文件"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}"
    with open(LOG_FILE, 'a', encoding="utf-8") as f:
        f.write(log_line + "\n")
        f.flush()


def parse_datetime(datetime_str: str) -> datetime:
    """解析日期时间字符串"""
    return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')


def call_llm(prompt: str, system_prompt: str = None, temperature: float = 0.3) -> str:
    """调用 DeepSeek LLM API"""
    import requests
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": temperature,
        "stream": False
    }
    
    try:
        response = requests.post(DEEPSEEK_API_BASE, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0].get("message", {}).get("content", "")
        return ""
    except Exception as e:
        log_message(f"❌ LLM API call failed: {e}")
        return ""


def is_relevant_content(diff_content: str) -> bool:
    """检查 diff 内容是否包含招生相关主题"""
    system_prompt = """You are a content classification expert. Determine if the content contains any of these topics:
- Summer camp (夏令营)
- Pre-admission (预推免)
- Graduate entrance exam (考研)
- PhD admission (博士招生)
- Master's admission (硕士招生)

Return only "YES" or "NO", nothing else."""
    
    user_prompt = f"Please determine if the following content contains admissions information:\n\n{diff_content}\n\nReturn YES or NO:"
    response = call_llm(user_prompt, system_prompt, temperature=0.1)
    return "YES" in response.upper()


def extract_relevant_lines(diff_content: str) -> list:
    """提取包含招生信息的行"""
    system_prompt = """You are an information extraction expert. Extract all lines related to admissions from the diff content.

Each line format is: link text | link URL

Only extract lines related to these topics:
- Summer camp (夏令营)
- Pre-admission (预推免)
- Graduate entrance exam (考研)
- PhD admission (博士招生)
- Master's admission (硕士招生)

Return format as JSON array, each element contains:
- topic: link text
- url: link URL

Return only JSON, nothing else."""
    
    user_prompt = f"Please extract all admissions-related lines from the following diff:\n\n{diff_content}\n\nReturn JSON format:"
    response = call_llm(user_prompt, system_prompt, temperature=0.2)
    
    try:
        data = json.loads(response.strip())
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        log_message(f"❌ Failed to parse LLM response: {e}")
        return []


def fetch_url_details(url: str) -> dict:
    """访问 URL，提取标题和正文内容"""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) web-monitor/1.0"
    }
    
    req = Request(url, headers=req_headers)
    
    try:
        with urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            
            # 提取标题
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""
            
            # 提取正文内容
            for script in soup(["script", "style"]):
                script.decompose()
            
            body = soup.find("body")
            text_content = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)
            
            lines = [line.strip() for line in text_content.split("\n") if line.strip()]
            content = "\n".join(lines[:2000])
            
            return {"title": title, "content": content}
            
        except ImportError:
            return {"title": "", "content": html[:5000]}
        
    except HTTPError as e:
        return {"title": "", "content": f"HTTP Error: {e.code} {e.reason}"}
    except URLError as e:
        return {"title": "", "content": f"Connection Error: {e.reason}"}
    except Exception as e:
        return {"title": "", "content": f"Error: {str(e)}"}


def save_detail_file(diff_file: Path, details: list) -> Path:
    """保存详细信息到 detail 文件"""
    stem = diff_file.stem
    new_name = stem.replace("_diff_", "_detail_") + ".txt"
    detail_path = SNAPSHOTS_DIR / new_name
    
    content_lines = []
    content_lines.append(f"Detail file - Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content_lines.append("=" * 80)
    content_lines.append("")
    
    for i, detail in enumerate(details, 1):
        content_lines.append(f"[Info {i}]")
        content_lines.append(f"Topic: {detail.get('topic', 'N/A')}")
        content_lines.append(f"URL: {detail.get('url', 'N/A')}")
        content_lines.append(f"Title: {detail.get('title', 'N/A')}")
        content_lines.append("")
        content_lines.append("Content:")
        content_lines.append("-" * 80)
        content_lines.append(detail.get('content', 'N/A'))
        content_lines.append("")
        content_lines.append("=" * 80)
        content_lines.append("")
    
    try:
        detail_path.write_text("\n".join(content_lines), encoding="utf-8")
        log_message(f"✅ Saved detail file: {new_name}")
        return detail_path
    except Exception as e:
        log_message(f"❌ Failed to save detail file: {e}")
        return None


def summarize_details(detail_content: str) -> list:
    """使用 LLM 对每条信息做总结"""
    system_prompt = """You are an information summarization expert. Please summarize the detailed information.

Requirements:
1. Summarize each info separately, do not merge multiple items
2. Summaries should be concise and highlight key information (school, major, deadline, requirements, etc.)
3. Return format as JSON array, each element is a summary string
4. Return only JSON, nothing else

Each item contains: topic, url, title, and content."""
    
    user_prompt = f"Please summarize the following detailed information:\n\n{detail_content}\n\nReturn JSON array of summaries:"
    response = call_llm(user_prompt, system_prompt, temperature=0.3)
    
    try:
        data = json.loads(response.strip())
        if isinstance(data, list):
            summaries = [str(item) if not isinstance(item, str) else item for item in data]
            return summaries
        return []
    except Exception as e:
        log_message(f"❌ Failed to parse LLM response: {e}")
        return []


def save_summarize_file(detail_file: Path, summaries: list, details: list) -> Path:
    """保存总结到 summarize 文件"""
    stem = detail_file.stem
    new_name = stem.replace("_detail_", "_summarize_") + ".txt"
    summarize_path = SNAPSHOTS_DIR / new_name
    
    # 根据文件名前缀确定信息来源
    source_mapping = {
        "SYSU_SE_": "【中山大学软工学院新信息】",
        "LOG": "【LOG 新信息】",
    }
    source_title = "【博客园新信息"]  # 默认值
    for prefix, title in source_mapping.items():
        if new_name.startswith(prefix):
            source_title = title
            break
    
    content_lines = []
    content_lines.append(f"{source_title} - 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content_lines.append("=" * 80)
    content_lines.append("")
    
    for i, (summary, detail) in enumerate(zip(summaries, details), 1):
        content_lines.append(f"【信息 {i}】")
        content_lines.append(summary)
        content_lines.append("")
        content_lines.append(f"原文链接: {detail.get('url', 'N/A')}")
        content_lines.append("-" * 80)
        content_lines.append("")
    
    try:
        summarize_path.write_text("\n".join(content_lines), encoding="utf-8")
        log_message(f"✅ Saved summarize file: {new_name}")
        return summarize_path
    except Exception as e:
        log_message(f"❌ Failed to save summarize file: {e}")
        return None


def push_to_email(summarize_file: Path, content: str) -> bool:
    """推送到邮箱"""
    if not SMTP_USER or not SMTP_PASSWORD:
        log_message("⚠️  Warning: SMTP_USER and SMTP_PASSWORD not configured")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = TARGET_EMAIL
        msg['Subject'] = f"招生信息汇总 - {summarize_file.stem}"
        
        body = MIMEText(content, 'plain', 'utf-8')
        msg.attach(body)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        log_message(f"✅ Email sent to {TARGET_EMAIL}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        log_message(f"❌ SMTP 认证失败")
        return False
    except smtplib.SMTPException as e:
        log_message(f"❌ SMTP 错误: {e}")
        return False
    except Exception as e:
        log_message(f"❌ 发送邮件失败: {e}")
        return False


def mark_as_done(filepath: Path) -> Path:
    """重命名文件，添加 _done 后缀"""
    stem = filepath.stem
    suffix = filepath.suffix
    new_name = f"{stem}_done{suffix}"
    new_path = filepath.parent / new_name
    
    try:
        filepath.rename(new_path)
        log_message(f"✅ Marked as done: {new_name}")
        return new_path
    except Exception as e:
        log_message(f"❌ Failed to mark as done: {e}")
        return filepath


def find_unprocessed_diffs() -> list:
    """查找所有未处理的 diff 文件"""
    if not SNAPSHOTS_DIR.exists():
        return []
    
    diff_files = list(SNAPSHOTS_DIR.glob("*diff_*.txt"))
    unprocessed = [f for f in diff_files if "_done" not in f.name]
    return unprocessed


def process_diff_files():
    """处理所有未处理的 diff 文件"""
    unprocessed = find_unprocessed_diffs()
    
    if not unprocessed:
        log_message("No unprocessed diff files")
        return True
    
    log_message(f"Processing {len(unprocessed)} unprocessed diff files")
    
    for diff_file in unprocessed:
        log_message(f"\n{'=' * 80}")
        log_message(f"Processing: {diff_file.name}")
        log_message('=' * 80)
        
        try:
            diff_content = diff_file.read_text(encoding="utf-8")
            log_message(f"✅ Read diff file, length: {len(diff_content)} chars")
            
            if not is_relevant_content(diff_content):
                log_message("✅ No admissions info, skipping")
                mark_as_done(diff_file)
                continue
            
            log_message("✅ Contains admissions info")
            
            relevant_lines = extract_relevant_lines(diff_content)
            if not relevant_lines:
                log_message("⚠️  No relevant lines extracted")
                mark_as_done(diff_file)
                continue
            
            log_message(f"✅ Extracted {len(relevant_lines)} relevant lines")
            
            details = []
            for i, item in enumerate(relevant_lines, 1):
                url = item.get('url', '')
                topic = item.get('topic', '')
                
                if not url:
                    continue
                
                log_message(f"[{i}/{len(relevant_lines)}] Fetching: {topic[:50]}...")
                
                page_data = fetch_url_details(url)
                detail = {
                    "topic": topic,
                    "url": url,
                    "title": page_data.get('title', ''),
                    "content": page_data.get('content', '')
                }
                details.append(detail)
            
            if not details:
                log_message("⚠️  No details fetched")
                mark_as_done(diff_file)
                continue
            
            log_message(f"✅ Fetched {len(details)} details")
            
            detail_path = save_detail_file(diff_file, details)
            if not detail_path:
                continue
            
            detail_content = detail_path.read_text(encoding="utf-8")
            summaries = summarize_details(detail_content)
            if not summaries:
                log_message("⚠️  No summaries generated")
                continue
            
            log_message(f"✅ Generated {len(summaries)} summaries")
            
            summarize_path = save_summarize_file(detail_path, summaries, details)
            if not summarize_path:
                continue
            
            summarize_content = summarize_path.read_text(encoding="utf-8")
            email_sent = push_to_email(summarize_path, summarize_content)
            if email_sent:
                log_message("✅ Email sent successfully")
                mark_as_done(summarize_path)
            else:
                log_message("⚠️  Email sending failed")
            
            mark_as_done(detail_path)
            mark_as_done(diff_file)
            
            log_message(f"✅ Processing completed: {diff_file.name}")
            
        except Exception as e:
            log_message(f"❌ Processing failed: {e}")
            import traceback
            traceback.print_exc()
    
    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Web Monitor Diff 文件处理脚本（简化版）'
    )
    parser.add_argument(
        'interval',
        type=int,
        help='检查间隔（分钟）'
    )
    parser.add_argument(
        'start_time',
        type=str,
        help='开始时间 (YYYY-MM-DD HH:MM)'
    )
    parser.add_argument(
        'end_time',
        type=str,
        help='结束时间 (YYYY-MM-DD HH:MM)'
    )
    
    args = parser.parse_args()
    
    # 执行循环检查
    from periodic_check import scheduled_check_loop
    exit_code = scheduled_check_loop(args.interval, args.start_time, args.end_time)
    log_message(f"程序结束 (退出码: {exit_code})")
    log_message("")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
