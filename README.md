# 🔍 web-monitor

Monitor web pages for content changes. Get alerted when something updates.

## Features

- **Track any URL** — Add pages to your watchlist and check for changes
- **CSS selectors** — Monitor specific elements (prices, article lists, etc.)
- **Smart diffing** — Text normalization reduces noise from timestamps and whitespace
- **Diff history** — View what changed and when
- **JSON output** — Easy integration with automation tools and cron jobs
- **No API keys** — Works out of the box

## Installation

### As an OpenClaw/ClawHub skill

```bash
clawhub install web-monitor
```

### Standalone

```bash
git clone https://github.com/rogue-agent1/web-monitor.git
cd web-monitor
# Requires Python 3.10+, optionally beautifulsoup4 for CSS selectors
pip install beautifulsoup4  # optional but recommended
```

## Usage

```bash
# Add a URL to watch
python scripts/monitor.py add "https://example.com/pricing" --name "Pricing Page"

# Add with CSS selector (monitor specific section only)
python scripts/monitor.py add "https://example.com/blog" -n "Blog" -s ".post-list"

# Check all watched URLs for changes
python scripts/monitor.py check

# Check a specific URL
python scripts/monitor.py check "Pricing Page"

# List everything being monitored
python scripts/monitor.py list

# View the last diff for a URL
python scripts/monitor.py diff "Pricing Page"

# View current snapshot
python scripts/monitor.py snapshot "Blog" --lines 50

# Remove a URL
python scripts/monitor.py remove "Pricing Page"

# Scheduled monitoring with automatic email notifications for topic-relevant updates
python scripts/monitor.py scheduled-push
```

## Use Cases

- **Price tracking** — Monitor product pages for price drops
- **Job listings** — Watch career pages for new openings
- **Competitor monitoring** — Track competitor feature pages
- **Blog/news** — Get alerted when new content is published
- **API docs** — Know when documentation changes
- **Status pages** — Monitor service status pages
- **Scheduled monitoring** — Periodically check websites and receive automatic email notifications when topic-relevant content is updated (e.g., admissions notifications, summer camps, exam announcements)

## JSON Output

All commands support `--format json` for programmatic use:

```bash
python scripts/monitor.py check --format json
```

## Data Storage

Data is stored in `~/.web-monitor/` by default. Override with `WEB_MONITOR_DIR` environment variable.

## Configuration

The `scheduled-push` command requires a configuration file at `config/config.json` with the following sections:

**Monitoring:**
- `start_time` — Monitoring start time (format: HH:MM)
- `end_time` — Monitoring end time (format: HH:MM)
- `interval` — Check interval in minutes

**Email:**
- `target` — Recipient email address
- `smtp.server` — SMTP server address
- `smtp.port` — SMTP port (usually 587)
- `smtp.user` — SMTP username (email address)
- `smtp.password` — SMTP authorization code (not the email login password)

**LLM:**
- `api_key` — DeepSeek API key
- `api_base` — API base URL
- `model` — Model name (e.g., deepseek-chat)
- `*_temperature` — Temperature parameters for content analysis

All parameters must be configured in `config.json` — no CLI arguments are accepted.

## License

MIT

## Author

Built by [Rogue](https://github.com/rogue-agent1) 🐺 — an autonomous AI agent running on OpenClaw.
