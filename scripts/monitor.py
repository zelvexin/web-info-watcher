#!/usr/bin/env python3
"""
web-info-watcher: Track web pages for changes and get alerts.
Stores snapshots, computes diffs, supports CSS selectors for targeted monitoring.
"""

import argparse
import hashlib
import json
import os
import time
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin
from difflib import unified_diff

# Optional dependencies (graceful fallback)
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

DATA_DIR = Path(os.environ.get("WEB_INFO_WATCHER_DIR", Path(__file__).parent.parent / "data"))
WATCHES_FILE = DATA_DIR / "watches.json"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"

# Global variable to store the summary pool file path for this monitoring session
SUMMARY_POOL_FILE = None

# Configuration directory and file
CONFIG_DIR = Path(os.environ.get("WEB_INFO_WATCHER_CONFIG_DIR",
                                  Path(__file__).parent.parent / "config"))
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    """Load configuration from config.json

    All parameters (monitoring, email, LLM) are loaded from config.json.
    No default values are provided - the config file must exist and be valid.

    Returns:
        dict: Configuration dictionary

    Raises:
        FileNotFoundError: If config file does not exist
        json.JSONDecodeError: If config file has invalid JSON format
    """
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {CONFIG_FILE}\n"
            f"Please create a config file at this location.\n"
            f"Refer to documentation for the required structure."
        )

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON format in config file: {CONFIG_FILE}\n"
            f"Error: {e.msg}",
            e.doc,
            e.pos
        )


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

def load_watches() -> dict:
    if WATCHES_FILE.exists():
        return json.loads(WATCHES_FILE.read_text())
    return {"watches": []}

def save_watches(data: dict):
    WATCHES_FILE.write_text(json.dumps(data, indent=2))

def slug(url: str) -> str:
    """Create a filesystem-safe slug from a URL."""
    return hashlib.md5(url.encode()).hexdigest()[:12]

def get_safe_filename(name: str) -> str:
    """Convert name to a safe filename, replace invalid characters with underscores."""
    unsafe_chars = r'[\\/:*?"<>|\s]'
    safe_name = re.sub(unsafe_chars, '_', name)
    return safe_name[:50]

def get_formatted_time() -> str:
    """Return formatted datetime string for diff filenames: YYYY-MM-DD_HH-MM-SS"""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def extract_links_from_html(html: str, base_url: str) -> list:
    """Extract all links from HTML, return (text, URL) list"""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href:
            continue
        
        link_text = a_tag.get_text(strip=True).replace("\n", " ").replace("\r", "")
        if not link_text:
            link_text = "[无文本描述]"
        
        absolute_url = urljoin(base_url, href)
        
        if absolute_url.startswith(("http://", "https://")):
            links.append( (link_text, absolute_url) )
    
    links = list(set(links))
    links.sort(key=lambda x: x[0])
    return links

def format_links_to_string(links: list) -> str:
    """Format links list as readable text"""
    if not links:
        return "[无链接]"
    
    lines = []
    lines.append(f"{'链接文本':<60} | 链接URL")  # 表头
    lines.append("-" * 120)  # 分隔线
    
    for text, url in links:
        # 文本过长截断
        short_text = text[:55] + "..." if len(text) > 55 else text
        lines.append(f"{short_text:<60} | {url}")
    
    return "\n".join(lines)

def fetch_content(url: str, selector: str = None, headers: dict = None) -> str:
    """Fetch web page and extract all links"""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) web-info-watcher/1.0"
    }
    if headers:
        req_headers.update(headers)
    
    req = Request(url, headers=req_headers)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.reason}")
    except URLError as e:
        raise RuntimeError(f"Connection error: {e.reason}")
    
    if HAS_BS4:
        links = extract_links_from_html(raw, url)
    else:
        print("Warning: beautifulsoup4 not installed, returning raw HTML", file=sys.stderr)
        return raw
    
    # 格式化为文本
    return format_links_to_string(links)

def normalize_text(text: str) -> str:
    """Normalize text to reduce noise from timestamps, ads, etc."""
    lines = text.split("\n")
    # Remove empty lines and normalize whitespace
    lines = [re.sub(r'\s+', ' ', line.strip()) for line in lines if line.strip()]
    return "\n".join(lines)

def cmd_add(args):
    """Add a URL to watch."""
    ensure_dirs()
    data = load_watches()
    
    # Check for duplicate
    for w in data["watches"]:
        if w["url"] == args.url:
            print(f"该网站已处于监控列表中: {args.url}")
            return
    
    watch = {
        "url": args.url,
        "name": args.name or args.url[:60],
        "selector": args.selector,
        "added": datetime.now(timezone.utc).isoformat(),
        "last_check": None,
        "last_change": None,
        "check_count": 0,
        "change_count": 0,
    }
    data["watches"].append(watch)
    save_watches(data)
    
    # Take initial snapshot
    try:
        content = fetch_content(args.url, args.selector)
        content = normalize_text(content)
        safe_name = get_safe_filename(args.name or args.url)
        snap_path = SNAPSHOTS_DIR / f"{safe_name}.txt"
        snap_path.write_text(content)
        print(f"✅ 网站添加成功，并生成初始快照(首次获取内容): {watch['name']}")
    except Exception as e:
        print(f"⚠️  网站添加成功，但首次获取内容失败: {e}")

def cmd_remove(args):
    """Remove a URL from watch list."""
    ensure_dirs()
    data = load_watches()
    original = len(data["watches"])
    data["watches"] = [w for w in data["watches"] if w["url"] != args.url and w["name"] != args.url]
    if len(data["watches"]) < original:
        save_watches(data)
        print(f"✅ 成功移除网站: {args.url}")
    else:
        print(f"该网站未找到: {args.url}")

def cmd_list(args):
    """List all watched URLs."""
    ensure_dirs()
    data = load_watches()
    if not data["watches"]:
        print("当前没有正在监控的网站，请使用 add 命令添加.")
        return
    
    fmt = getattr(args, 'format', 'text')
    if fmt == 'json':
        print(json.dumps(data["watches"], indent=2))
        return
    
    for i, w in enumerate(data["watches"], 1):
        status = "never checked" if not w['last_check'] else f"已检测 {w['check_count']} 次，发生 {w['change_count']} 次更新"
        sel = f" [选择器: {w['selector']}]" if w.get("selector") else ""
        print(f"{i}. {w['name']}")
        print(f"   URL: {w['url']}{sel}")
        print(f"   状态: {status}")
        if w.get("last_change"):
            print(f"   最近一次更新: {w['last_change']}")
        print()

def cmd_check(args):
    """Check all (or one) watched URLs for changes."""
    ensure_dirs()
    data = load_watches()
    
    if not data["watches"]:
        print("当前没有正在监控的网站.")
        return
    
    watches_to_check = data["watches"]
    if args.url:
        watches_to_check = [w for w in data["watches"] if w["url"] == args.url or w["name"] == args.url]
        if not watches_to_check:
            print(f"未找到指定的监控网站: {args.url}")
            return
    
    results = []
    for watch in watches_to_check:
        url = watch["url"]
        safe_name = get_safe_filename(watch["name"] or watch["url"])
        snap_path = SNAPSHOTS_DIR / f"{safe_name}.txt"
        
        try:
            new_content = fetch_content(url, watch.get("selector"))
            new_content = normalize_text(new_content)
        except Exception as e:
            results.append({"name": watch["name"], "url": url, "error": str(e)})
            continue
        
        watch["last_check"] = datetime.now(timezone.utc).isoformat()
        watch["check_count"] = watch.get("check_count", 0) + 1
        
        if snap_path.exists():
            old_content = snap_path.read_text()
            if old_content == new_content:
                results.append({"name": watch["name"], "url": url, "changed": False})
            else:
                # Compute diff
                old_lines = old_content.split("\n")
                new_lines = new_content.split("\n")
                diff = list(unified_diff(old_lines, new_lines, n=2, lineterm=""))
                
                # Count meaningful changes
                added = [l for l in diff if l.startswith("+") and not l.startswith("+++")]
                removed = [l for l in diff if l.startswith("-") and not l.startswith("---")]
                
                watch["last_change"] = datetime.now(timezone.utc).isoformat()
                watch["change_count"] = watch.get("change_count", 0) + 1
                
                # Save new snapshot
                snap_path.write_text(new_content)

                # Save diff (only additions - + lines)
                formatted_time = get_formatted_time()
                diff_path = SNAPSHOTS_DIR / f"{safe_name}_diff_{formatted_time}.txt"

                # 只保留新增内容（+ 开头的行，排除 +++ 文件标记）
                additions_only = [line for line in diff if line.startswith("+") and not line.startswith("+++")]
                diff_path.write_text("\n".join(additions_only))
                
                result = {
                    "name": watch["name"],
                    "url": url,
                    "changed": True,
                    "added_lines": len(added),
                    "removed_lines": len(removed),
                    "diff_preview": "\n".join(diff[:30]),
                }
                results.append(result)
        else:
            # First snapshot
            snap_path.write_text(new_content)
            results.append({"name": watch["name"], "url": url, "changed": False, "note": "initial snapshot"})
    
    save_watches(data)
    
    # Output
    fmt = getattr(args, 'format', 'text')
    if fmt == 'json':
        print(json.dumps(results, indent=2))
        return
    
    changes_found = False
    for r in results:
        if r.get("error"):
            print(f"❌ {r['name']}: {r['error']}")
        elif r.get("changed"):
            changes_found = True
            print(f"🔔 发现更新: {r['name']}")
            print(f"   URL: {r['url']}")
            print(f"   +{r['added_lines']} lines / -{r['removed_lines']} lines")
            if r.get("diff_preview"):
                print(f"   Preview:")
                for line in r["diff_preview"].split("\n")[:10]:
                    print(f"     {line}")
            print()
        elif r.get("note"):
            print(f"📸 {r['name']}: {r['note']}")
        else:
            print(f"✅ {r['name']}: 该网站没有更新")
    
    if not changes_found and not any(r.get("error") for r in results):
        print("\n该网站没有找到更新内容.")

def cmd_diff(args):
    """Show the last diff for a URL."""
    ensure_dirs()
    data = load_watches()
    
    watch = None
    for w in data["watches"]:
        if w["url"] == args.url or w["name"] == args.url:
            watch = w
            break
    
    if not watch:
        print(f"未找到网站: {args.url}")
        return
    
    safe_name = get_safe_filename(watch["name"] or watch["url"])
    # Find latest diff file
    diffs = sorted(SNAPSHOTS_DIR.glob(f"{safe_name}_diff_*.txt"), reverse=True)
    if not diffs:
        print(f"该网站暂无变化记录: {watch['name']}")
        return
    
    print(f"最近一次变化（diff）: {watch['name']}")
    print(f"URL: {watch['url']}")
    print("-" * 60)
    print(diffs[0].read_text())

def cmd_snapshot(args):
    """Show the current snapshot for a URL."""
    ensure_dirs()
    data = load_watches()
    
    watch = None
    for w in data["watches"]:
        if w["url"] == args.url or w["name"] == args.url:
            watch = w
            break
    
    if not watch:
        print(f"未找到网站: {args.url}")
        return
    
    safe_name = get_safe_filename(watch["name"] or watch["url"])
    snap_path = SNAPSHOTS_DIR / f"{safe_name}.txt"
    if not snap_path.exists():
        print(f"该网站暂无快照记录: {watch['name']}")
        return
    
    content = snap_path.read_text()
    if args.lines:
        lines = content.split("\n")[:args.lines]
        print("\n".join(lines))
    else:
        print(content[:5000])


# ==================== Scheduled Push Function ====================

import subprocess
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests


def log_message(message: str):
    """Log message to periodic_check.log file"""
    log_file = DATA_DIR / "periodic_check.log"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}"
    with open(log_file, 'a') as f:
        f.write(log_line + "\n")
        f.flush()
    print(log_line, flush=True)


def parse_datetime(datetime_str: str) -> datetime:
    """Parse datetime string in format YYYY-MM-DD HH:MM"""
    return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')


def is_within_monitoring_window(start_time: datetime, end_time: datetime) -> bool:
    """Check if current time is within monitoring window"""
    now = datetime.now()
    return start_time <= now <= end_time

def perform_check_all():
    """Perform a complete check on all monitored websites"""
    data = load_watches()
    watches = data.get("watches", [])
    
    if not watches:
        log_message("⚠️  No websites to monitor")
        return True
    
    log_message(f"共发现 {len(watches)} 个监控网站，开始检测...")
    
    for i, watch in enumerate(watches, 1):
        name = watch.get('name', '')
        url = watch.get('url', '')
        identifier = name if name else url
        
        log_message(f"[{i}/{len(watches)}] 正在检测: {identifier[:50]}...")
        
        try:
            result = subprocess.run(
                ['bash', f'{Path(__file__).parent}/run.sh', 'check', identifier],
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
                log_message(f"  ✅ 该网站检查结束")
            else:
                log_message(f"  ❌ 该网站检查失败 (code: {result.returncode})")
                
        except subprocess.TimeoutExpired:
            log_message(f"  ⏱️  检查超时")
        except Exception as e:
            log_message(f"  ❌ 检查出错: {e}")
    
    log_message(f"✅ 全部检查结束，共检查 {len(watches)} 个网站")
    return True


def call_llm(prompt: str, temperature: float, system_prompt: str = None) -> str:
    """Call DeepSeek LLM API

    All LLM configuration (api_key, api_base, model) is loaded from config.json.
    The temperature parameter must be provided by the caller from config.json.

    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        temperature: Temperature parameter (must be loaded from config.json)

    Returns:
        str: LLM response content
    """
    config = load_config()
    llm_config = config["llm"]

    headers = {
        "Authorization": f"Bearer {llm_config['api_key']}",
        "Content-Type": "application/json"
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": llm_config["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": False
    }

    try:
        response = requests.post(llm_config["api_base"], headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0].get("message", {}).get("content", "")
        return ""
    except Exception as e:
        log_message(f"❌ LLM API 调用失败: {e}")
        return ""

def is_relevant_content(diff_content: str) -> bool:
    """使用 LLM 判断 diff 内容是否包含及时、具体的招生通知"""

    system_prompt = """你是一个高校通知分类专家。你的任务是判断 diff 内容中是否出现“新增的、具体的、及时性的招生通知或公告”。

只有满足以下条件之一，才返回 YES：
1. 内容是具体通知、公告、公示、名单、安排、简章、报名、复试、调剂、考核等文章；
2. 内容明确涉及硕士招生、博士招生、推免、预推免、夏令营、优秀大学生夏令营、招生宣讲；
3. 内容看起来是学院近期发布的一条具体新闻或通知，而不是网站固定栏目。

以下情况必须返回 NO：
1. 只有学院首页链接，例如“中山大学人工智能学院 | https://sai.sysu.edu.cn/”；
2. 登录页、后台页、用户中心页面；
3. 只有“招生信息”“培养方案”“研究生教育”等栏目导航链接；
4. 只是网站菜单、栏目入口、固定页面、导航栏变化；
5. 只有 URL，没有具体通知标题；
6. 泛泛出现“招生信息”四个字，但没有具体通知内容。

请严格判断。只返回 YES 或 NO，不要解释。"""

    user_prompt = f"""请判断下面 diff 内容中，是否包含“新增的具体招生通知/公告”。

diff 内容：
{diff_content}

判断规则：
- 如果只是栏目链接、导航链接、首页链接、登录链接，返回 NO。
- 如果是具体招生通知、公告、公示、名单、报名安排、考核安排、招生简章，返回 YES。
- 只返回 YES 或 NO。"""

    config = load_config()
    response = call_llm(user_prompt, temperature=config["llm"]["relevance_check_temperature"], system_prompt=system_prompt)
    return response.strip().upper() == "YES"


def extract_relevant_lines(diff_content: str) -> list:
    """Extract lines containing admissions information from diff"""
    system_prompt = """你是一个信息抽取专家。请从给定的 diff 内容中提取所有与招生相关的行。

每一行的格式为：链接文本 | 链接 URL

只提取以下主题相关的内容：
- 夏令营
- 预推免
- 考研
- 博士招生
- 硕士招生

返回格式为 JSON 数组，每个元素包含：
- topic：链接文本
- url：链接 URL

只返回 JSON，不要输出任何其他内容。"""
    
    user_prompt = f"""请从以下 diff 内容中提取所有与招生相关的行：

{diff_content}

请以 JSON 格式返回："""
    config = load_config()
    response = call_llm(user_prompt, temperature=config["llm"]["extraction_temperature"], system_prompt=system_prompt)
    
    # Log the raw response for debugging
    if not response or not response.strip():
        log_message("⚠️  LLM 返回为空")
        return []
    
    # Try to extract JSON from markdown code block if present
    cleaned_response = response.strip()
    if cleaned_response.startswith("```json"):
        cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
    elif cleaned_response.startswith("```"):
        cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
    
    cleaned_response = cleaned_response.strip()
    
    try:
        data = json.loads(cleaned_response)
        if isinstance(data, list):
            return data
        log_message(f"⚠️  LLM 返回的 JSON 不是列表类型: {type(data)}")
        return []
    except json.JSONDecodeError as e:
        log_message(f"❌ 无法将 LLM 返回结果解析为 JSON: {e}")
        log_message(f"   原始返回内容（前200字符）: {response[:200]}")
        return []
    except Exception as e:
        log_message(f"❌ 解析 LLM 返回结果时发生未知错误: {e}")
        return []


def fetch_url_details(url: str) -> dict:
    """Fetch and extract title and content from URL"""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) web-info-watcher/1.0"
    }
    
    req = Request(url, headers=req_headers)
    
    try:
        with urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        
        if not HAS_BS4:
            return {"title": "", "content": html[:5000]}
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        
        # Extract body content
        for script in soup(["script", "style"]):
            script.decompose()
        
        body = soup.find("body")
        text_content = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)
        
        lines = [line.strip() for line in text_content.split("\n") if line.strip()]
        content = "\n".join(lines[:2000])
        
        return {"title": title, "content": content}
        
    except HTTPError as e:
        return {"title": "", "content": f"HTTP Error: {e.code} {e.reason}"}
    except URLError as e:
        return {"title": "", "content": f"Connection Error: {e.reason}"}
    except Exception as e:
        return {"title": "", "content": f"Error: {str(e)}"}


def save_detail_file(diff_file: Path, details: list) -> Path:
    """Save detailed information to detail file"""
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
        log_message(f"✅ 已保存 detail file: {new_name}")
        return detail_path
    except Exception as e:
        log_message(f"❌ detail file 保存失败: {e}")
        return None


def summarize_details(detail_content: str) -> list:
    """使用 LLM 对详细内容进行总结"""
    system_prompt = """你是一个信息总结专家，请对给定的详细信息进行总结。

要求：
1. 每一条信息分别总结，不要将多条内容合并
2. 总结内容应简洁，突出关键信息（如：学校、专业、截止时间、申请要求等）
3. 返回格式为 JSON 数组，每个元素是一个总结字符串
4. 只返回 JSON，不要输出任何其他内容

每条信息包含：topic、url、title 和 content。"""
    
    user_prompt = f"""请总结以下详细信息：

{detail_content}

请以 JSON 数组形式返回总结结果："""

    config = load_config()
    response = call_llm(user_prompt, temperature=config["llm"]["summary_temperature"], system_prompt=system_prompt)
    
    # Log the raw response for debugging
    if not response or not response.strip():
        log_message("⚠️  总结内容为空")
        return []
    
    # Try to extract JSON from markdown code block if present
    cleaned_response = response.strip()
    if cleaned_response.startswith("```json"):
        cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
    elif cleaned_response.startswith("```"):
        cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
    
    cleaned_response = cleaned_response.strip()
    
    try:
        data = json.loads(cleaned_response)
        if isinstance(data, list):
            summaries = [str(item) if not isinstance(item, str) else item for item in data]
            return summaries
        log_message(f"⚠️  LLM总结时返回的是 JSON，但不是列表List形式: {type(data)}")
        return []
    except json.JSONDecodeError as e:
        log_message(f"❌ LLM总结时JSON 解析失败: {e}")
        log_message(f"   原始结果 (前200字符): {response[:200]}")
        return []
    except Exception as e:
        log_message(f"❌ LLM总结时发生了未知异常: {e}")
        return []


def save_summarize_file(detail_file: Path, summaries: list, details: list) -> Path:
    """Save summary entry to the summary pool file"""
    global SUMMARY_POOL_FILE
    
    stem = detail_file.stem
    new_name = stem.replace("_detail_", "_summarize_") + ".txt"
    summarize_path = SNAPSHOTS_DIR / new_name
    
    # Determine source based on filename prefix
    source_mapping = {
        "SYSU_SE_": "中山大学软工学院",
        "SYSU_CS_": "中山大学计算机学院",
        "SYSU_AI_": "中山大学人工智能学院",
        "SYSU_CST_": "中山大学网络空间安全学院",
        "CSDN_blog": "CSDN博客",
    }
  
    for prefix, name in source_mapping.items():
        if new_name.startswith(prefix):
            source_name = name
            break
    
    # Generate content for each summary entry
    entries = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for i, (summary, detail) in enumerate(zip(summaries, details), 1):
        # Format: 【timestamp source_name】
        entries.append(f"【{timestamp} {source_name}新信息】")
        entries.append(summary)
        entries.append("")
        entries.append(f"原文链接: {detail.get('url', 'N/A')}")
        entries.append("-" * 80)
        entries.append("")
    
    # Save to individual summarize file (for historical record)
    try:
        summarize_path.write_text("\n".join(entries), encoding="utf-8")
    except Exception as e:
        return None
    
    # Append to summary pool file (for email sending)
    if SUMMARY_POOL_FILE and SUMMARY_POOL_FILE.exists():
        with open(SUMMARY_POOL_FILE, 'a', encoding='utf-8') as f:
            f.write("\n".join(entries) + "\n")
    
    return summarize_path


def push_to_email(summary_pool_path: Path) -> bool:
    """Send summary to email with all historical information

    All email configuration (SMTP server, port, user, authorization code, target)
    is loaded from config.json.

    Note: email.smtp.password field stores the SMTP authorization code, not the login password.

    Args:
        summary_pool_path: Path to the summary pool file containing all historical entries

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    config = load_config()
    email_config = config["email"]

    if not email_config["smtp"]["user"] or not email_config["smtp"]["password"]:
        log_message("⚠️  警告：SMTP_USER 和 SMTP_PASSWORD 未配置")
        return False

    try:
        # Read all information from summary pool file
        if summary_pool_path and summary_pool_path.exists():
            content = summary_pool_path.read_text(encoding='utf-8')
        else:
            content = ""
        
        # Split into independent information blocks
        blocks = []
        current_block = []
        
        for line in content.split('\n'):
            if line.startswith('【') and '新信息】' in line:
                if current_block:
                    blocks.append('\n'.join(current_block))
                current_block = [line]
            else:
                current_block.append(line)
        
        if current_block:
            blocks.append('\n'.join(current_block))
        
        # Sort by time in reverse order (newest first)
        blocks.sort(reverse=True)
        
        # Combine all blocks (newest first)
        final_content = '\n'.join(blocks)
        
        msg = MIMEMultipart()
        msg['From'] = email_config["smtp"]["user"]
        msg['To'] = email_config["target"]
        msg['Subject'] = "中山大学招生信息推送"

        body = MIMEText(final_content, 'plain', 'utf-8')
        msg.attach(body)

        with smtplib.SMTP(email_config["smtp"]["server"], email_config["smtp"]["port"]) as server:
            server.starttls()
            server.login(email_config["smtp"]["user"], email_config["smtp"]["password"])
            server.send_message(msg)

        log_message(f"✅ Email已经成功发送至：{email_config['target']}")
        return True

    except smtplib.SMTPAuthenticationError:
        log_message(f"❌ SMTP 身份验证失败（请检查授权码是否正确）")
        return False
    except smtplib.SMTPException as e:
        log_message(f"❌ SMTP 错误: {e}")
        return False
    except Exception as e:
        log_message(f"❌ 无法发送 Email: {e}")
        return False


def mark_as_done(filepath: Path) -> Path:
    """Rename file to mark as done"""
    # Check if already marked
    if "_done" in filepath.stem:
        log_message(f"⚠️  该文件已经被标记为 done: {filepath.name}")
        return filepath
    
    stem = filepath.stem
    suffix = filepath.suffix
    new_name = f"{stem}_done{suffix}"
    new_path = filepath.parent / new_name
    
    try:
        filepath.rename(new_path)
        return new_path
    except Exception as e:
        log_message(f"❌无法重命名为 done 格式: {e}")
        return filepath

def mark_as_unrelated(filepath: Path) -> Path:
    """Rename file to mark as unrelated"""
    # Check if already marked
    if "_unrelated" in filepath.stem or "_done" in filepath.stem:
        log_message(f"⚠️  该文件已经被标记为 done 或 unrelated: {filepath.name}")
        return filepath
    
    stem = filepath.stem
    suffix = filepath.suffix
    new_name = f"{stem}_unrelated{suffix}"
    new_path = filepath.parent / new_name
    
    try:
        filepath.rename(new_path)
        return new_path
    except Exception as e:
        log_message(f"❌ 无法重命名为 unrelated 格式: {e}")
        return filepath


def find_unprocessed_diffs() -> list:
    """Find all unprocessed diff files"""
    if not SNAPSHOTS_DIR.exists():
        return []
    
    diff_files = list(SNAPSHOTS_DIR.glob("*diff_*.txt"))
    #diff中标了done和unrelated的都排除
    unprocessed = [f for f in diff_files if "_done" not in f.name and "_unrelated" not in f.name]
    return unprocessed


def process_diff_files():
    """Process all unprocessed diff files"""
    unprocessed = find_unprocessed_diffs()
    
    if not unprocessed:
        log_message("没有需要处理的diff_file")
        return True
    
    log_message(f"正在处理 {len(unprocessed)} 个未处理的 diff_file")
    
    for diff_file in unprocessed:
        log_message(f"\n{'=' * 80}")
        log_message(f"正在处理的diff_file: {diff_file.name}")
        
        try:
            diff_content = diff_file.read_text(encoding="utf-8")
            
            if not is_relevant_content(diff_content):
                log_message("⚠️  在diff文件中没有查询到相关信息的更新")
                mark_as_unrelated(diff_file)
                continue
            
            relevant_lines = extract_relevant_lines(diff_content)
            if not relevant_lines:
                log_message("⚠️  在diff文件中没有查询到相关信息的更新")
                mark_as_unrelated(diff_file)
                continue
            
            log_message(f"✅ 抓取了 {len(relevant_lines)} 行相关内容")
            
            details = []
            for i, item in enumerate(relevant_lines, 1):
                url = item.get('url', '')
                topic = item.get('topic', '')
                
                if not url:
                    continue
                
                page_data = fetch_url_details(url)
                detail = {
                    "topic": topic,
                    "url": url,
                    "title": page_data.get('title', ''),
                    "content": page_data.get('content', '')
                }
                details.append(detail)
            
            if not details:
                log_message("⚠️ 找不到详细信息页面")
                mark_as_unrelated(diff_file)
                continue
            
            detail_path = save_detail_file(diff_file, details)
            if not detail_path:
                continue
            
            detail_content = detail_path.read_text(encoding="utf-8")
            summaries = summarize_details(detail_content)
            if not summaries:
                continue
            
            summarize_path = save_summarize_file(detail_path, summaries, details)
            if not summarize_path:
                continue
            
            email_sent = push_to_email(SUMMARY_POOL_FILE)
            if email_sent:
                mark_as_done(summarize_path)
            
            mark_as_done(detail_path)
            mark_as_done(diff_file)
            
            log_message(f"✅ 信息更新处理结束: {diff_file.name}")
            
        except Exception as e:
            log_message(f"❌ 处理出错: {e}")
            import traceback
            traceback.print_exc()
    
    return True


def summarize_check_results(start_time: datetime) -> dict:
    """
    Summarize the results of this round of checks.

    Scans for newly created summarize files (created after start_time)
    and counts them by source prefix.

    Args:
        start_time: The time when the check started

    Returns:
        dict: A dictionary with source names as keys and counts as values
              e.g., {"中山大学软工学院": 2, "中山大学计算机学院": 1}
    """
    source_mapping = {
        "SYSU_SE_": "中山大学软工学院",
        "SYSU_CS_": "中山大学计算机学院",
        "SYSU_AI_": "中山大学人工智能学院",
        "SYSU_CST_": "中山大学网络空间安全学院",
        # 测试用
        "CSDN_blog_": "CSDN博客",
    }

    results = {}

    # Find all summarize files
    if not SNAPSHOTS_DIR.exists():
        return results

    summarize_files = list(SNAPSHOTS_DIR.glob("*_summarize_*.txt"))

    for file in summarize_files:
        # Check if file was created after start_time
        file_mtime = datetime.fromtimestamp(file.stat().st_mtime)

        if file_mtime >= start_time:
            # Determine source from filename prefix
            for prefix, name in source_mapping.items():
                if file.name.startswith(prefix):
                    results[name] = results.get(name, 0) + 1
                    break

    return results


def scheduled_push():
    """
    Scheduled push function - Monitor websites for new admissions information and push to user.

    This function runs in a monitoring time window, periodically checks all monitored websites,
    processes new diff files, analyzes content with LLM, and pushes summaries via email.

    All parameters (start_time, end_time, interval, email config, LLM config)
    are loaded from config.json. No command line arguments are accepted.

    Configuration is loaded from: /workspace/projects/workspace/skills/web-info-watcher/config/config.json
    """
    global SUMMARY_POOL_FILE
    
    # Load configuration
    config = load_config()
    monitoring_config = config["monitoring"]

    # Create summary pool file for this monitoring session
    summary_pool_filename = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    summary_pool_path = SNAPSHOTS_DIR / summary_pool_filename
    
    # Initialize empty summary pool file
    summary_pool_path.write_text("", encoding='utf-8')
    SUMMARY_POOL_FILE = summary_pool_path

    # Load monitoring parameters from config
    start_time_str = monitoring_config["start_time"]
    end_time_str = monitoring_config["end_time"]
    interval = monitoring_config["interval"]

    log_message("=" * 40)
    log_message("启动定时推送服务")
    log_message("=" * 40)
    log_message(f"开始时间: {start_time_str}")
    log_message(f"结束时间: {end_time_str}")
    log_message(f"每次检测的间隔: {interval} 分钟")
    log_message("=" * 40)

    try:
        start_datetime = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
        end_datetime = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M')
    except ValueError as e:
        log_message(f"❌ 时间格式错误: {e}")
        return 1
    
    # Check if current time is within monitoring window
    if not is_within_monitoring_window(start_datetime, end_datetime):
        now = datetime.now()
        log_message(f"⏸️  当前时间 {now.strftime('%Y-%m-%d %H:%M')} 不在监控时间范围内")
        log_message(f"   监控时间范围：{start_datetime.strftime('%Y-%m-%d %H:%M')} - {end_datetime.strftime('%Y-%m-%d %H:%M')}")
        
        if now > end_datetime:
            log_message("❌ 监控时间已结束")
            return 0
        
        if now < start_datetime:
            wait_seconds = (start_datetime - now).total_seconds()
            log_message(f"⏳ 等待至 {start_datetime.strftime('%H:%M')}（约 {int(wait_seconds)} 秒）...")
            try:
                time.sleep(wait_seconds)
                log_message(f"⏰ 已到达开始时间{start_datetime.strftime('%H:%M')}")
            except KeyboardInterrupt:
                log_message("❌ 用户中断等待")
                return 1
        
        if not is_within_monitoring_window(start_datetime, end_datetime):
            log_message("⏸️  等待后仍未进入监控时间窗口")
            return 0
    
    log_message(f"✅ 当前时间 {datetime.now().strftime('%H:%M')} 在监控时间范围内，开始执行循环...")
    log_message(f"🔄 每 {interval} 分钟执行一次检测")
    
    # Monitoring loop
    check_count = 0
    while True:
        check_count += 1
        log_message("")
        log_message(f"🔔 第 {check_count} 次检测开始")

        # Record start time for this check
        check_start_time = datetime.now()

        # Step 1: Perform website check (from periodic_check.py)
        log_message(f"🚀🚀🚀  第1步：检测监控列表中的网站更新")
        perform_check_all()
        # Step 2: Process diff files (from process_diffs.py)
        log_message("🚀🚀🚀 第2步：检查更新内容，如包含指定主题则进行自动推送")
        process_diff_files()

        # Summarize results of this check
        results = summarize_check_results(check_start_time)
        if results:
            log_message("")
            log_message("本轮检查结束，共检查到以下相关信息并推送到邮箱：")
            for source, count in results.items():
                log_message(f"{source} {count}条新消息")
        else:
            log_message("")
            log_message("本轮检查结束，未检测到相关信息")
        log_message("")
        
        # Check if still in monitoring window
        if not is_within_monitoring_window(start_datetime, end_datetime):
            now = datetime.now()
            log_message("")
            log_message(f"⏸️  监控时间窗口已结束（当前时间：{now.strftime('%H:%M')})")
            log_message(f"✅ 定时推送已完成，共执行 {check_count} 次检测")
            return 0
        
        # Wait for next check
        wait_seconds = interval * 60

        now = datetime.now()
        time_to_end = (end_datetime - now).total_seconds()

        if time_to_end < wait_seconds:
            log_message(f"⏰ 距离监控结束不足 {interval} 分钟，退出监控任务")
            break
        else:
            log_message(f"⏳ 等待 {interval} 分钟后进行下一次检测...")
            try:
                time.sleep(wait_seconds)
            except KeyboardInterrupt:
                log_message("❌ 用户中断等待")
                return 1
    
    # Clean up summary pool file
    if summary_pool_path.exists():
        summary_pool_path.unlink()
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="web-info-watcher",
        description="Monitor web pages for changes"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    
    # add
    p_add = sub.add_parser("add", help="Add a URL to watch")
    p_add.add_argument("url", help="URL to monitor")
    p_add.add_argument("--name", "-n", help="Friendly name")
    p_add.add_argument("--selector", "-s", help="CSS selector to monitor (requires beautifulsoup4)")
    p_add.set_defaults(func=cmd_add)
    
    # remove
    p_rm = sub.add_parser("remove", help="remove a URL")
    p_rm.add_argument("url", help="URL or name to remove")
    p_rm.set_defaults(func=cmd_remove)
    
    # list
    p_ls = sub.add_parser("list", help="List watched URLs")
    p_ls.add_argument("--format", "-f", choices=["text", "json"], default="text")
    p_ls.set_defaults(func=cmd_list)
    
    # check
    p_chk = sub.add_parser("check", help="Check for changes")
    p_chk.add_argument("url", nargs="?", help="URL/name to check (all if omitted)")
    p_chk.add_argument("--format", "-f", choices=["text", "json"], default="text")
    p_chk.set_defaults(func=cmd_check)
    
    # diff
    p_diff = sub.add_parser("diff", help="Show last diff for a URL")
    p_diff.add_argument("url", help="URL or name")
    p_diff.set_defaults(func=cmd_diff)
    
    # snapshot
    p_snap = sub.add_parser("snapshot", help="Show current snapshot")
    p_snap.add_argument("url", help="URL or name")
    p_snap.add_argument("--lines", "-l", type=int, help="Limit output lines")
    p_snap.set_defaults(func=cmd_snapshot)

    # scheduled-push
    p_sched = sub.add_parser("scheduled-push", help="Scheduled push: monitor websites and push admissions info to user")
    p_sched.set_defaults(func=lambda args: scheduled_push())
    
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
