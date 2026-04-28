---
name: web-monitor
description: Monitor web pages for content changes and get alerts. Track URLs, detect updates, view diffs. Use when asked to watch a website, track changes on a page, monitor for new posts/content, set up page change alerts, or check if a site has been updated. Supports CSS selectors for targeted monitoring.
---

# Web Monitor

Track web pages for changes. Stores snapshots, computes diffs, supports CSS selectors.

## Quick Start

### 方法 1：使用便捷脚本（推荐）

```bash
# 在 skill 目录下运行便捷脚本
cd /path/to/web-monitor
bash scripts/run.sh add "https://example.com" --name "Example"

# 检查更新
bash scripts/run.sh check

# 查看监控列表
bash scripts/run.sh list
```

### 方法 2：直接运行 Python 脚本

```bash
# 设置环境变量
export WEB_MONITOR_DIR="/path/to/web-monitor/data"
export PATH="$HOME/.local/bin:$PATH"

# 添加监控
uv run --with beautifulsoup4 python scripts/monitor.py add "https://example.com" --name "Example"

# 检查更新
uv run --with beautifulsoup4 python scripts/monitor.py check

# 其他命令
uv run --with beautifulsoup4 python scripts/monitor.py list
uv run --with beautifulsoup4 python scripts/monitor.py diff "Example"
uv run --with beautifulsoup4 python scripts/monitor.py snapshot "Example" --lines 50
uv run --with beautifulsoup4 python scripts/monitor.py remove "Example"
uv run --with beautifulsoup4 python scripts/monitor.py scheduled-push
```

## Commands

| Command | Args | Description |
|---------|------|-------------|
| `add` | `<url> [-n name] [-s selector]` | Add URL to watch, take initial snapshot |
| `remove` | `<url-or-name>` | Stop watching a URL |
| `list` | `[-f json]` | List all watched URLs with stats |
| `check` | `[url-or-name] [-f json]` | Check for changes (all or one) |
| `diff` | `<url-or-name>` | Show last recorded diff |
| `snapshot` | `<url-or-name> [-l lines]` | Show current snapshot |
| `scheduled-push` | *(no args)* | Monitor websites and automatically push topic-relevant updates via email |

## Scheduled Push

Periodically monitor websites and automatically push updates related to target topics via email.

**Configuration:**
All settings loaded from `config/config.json`:

- `monitoring.start_time` / `end_time` / `interval` — Time window (HH:MM) and check frequency (minutes)
- `email.target` / `smtp.*` — Email delivery (SMTP password field: authorization code, not login password)
- `llm.api_key` / `api_base` / `model` / `*_temperature` — DeepSeek API settings for content analysis

Website monitoring information is recorded in `/data/watches.json`.

**Usage:**
```bash
bash scripts/run.sh scheduled-push
```

**Workflow:**
1. Runs within configured time window
2. Checks all monitored URLs for content changes
3. Analyzes diff content with LLM to detect topic-relevant updates
4. Extracts key information from relevant updates
5. Generates summary and sends via email

**Target Topics:**
Admissions notifications, summer camps, exam announcements, graduate/undergraduate recruitment, etc.

**Output:**
- Log: `data/periodic_check.log`
- Diffs: `data/snapshots/*_diff_*.txt`
- Details: `data/snapshots/*_detail_*.txt`
- Summaries: `data/snapshots/*_summarize_*.txt`

**Note:** Does not accept CLI arguments — all parameters must be configured in `config.json`.

## Output Symbols

- 🔔 CHANGED — page content changed (shows diff preview)
- ✅ No changes
- 📸 Initial snapshot taken
- ❌ Error fetching

## Data

**默认存储位置：** `skill/data/`（skill 目录下的 `data` 文件夹）

数据结构：
- `data/watches.json` — 监控任务配置
- `data/snapshots/` — 页面快照

**自定义存储位置：**
可通过 `WEB_MONITOR_DIR` 环境变量修改存储位置：

```bash
export WEB_MONITOR_DIR="/custom/path/data"
```

## Tips

- Use `--selector` to monitor specific elements (prices, article lists, etc.)
- Use `--format json` for programmatic checking (heartbeat integration)
- CSS selectors require beautifulsoup4 (included via `--with` flag)
- Text is normalized to reduce noise from timestamps, whitespace, ads
