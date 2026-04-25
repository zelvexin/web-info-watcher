# Web Monitor Skill 目录结构

## 完整目录结构

```
workspace/skills/web-monitor/
│
├── data/                      # 【数据目录】监控数据存储
│   ├── watches.json          # 监控配置
│   └── snapshots/            # 页面快照
│       └── ab8ef0e94f02.txt  # 快照文件（哈希命名）
│
├── scripts/                   # 【脚本目录】核心功能
│   └── monitor.py            # 监控脚本（Python）
│
├── .gitignore                # Git 忽略文件
├── _meta.json                # Skill 元数据
├── SKILL.md                  # Skill 使用说明
└── README.md                 # 项目说明
```

## 数据说明

### data/watches.json
存储所有监控任务的配置：
- 任务名称
- 监控 URL
- CSS 选择器（可选）
- 添加时间
- 最后检查时间
- 最后变化时间
- 检查次数
- 变化次数

### data/snapshots/
存储页面快照：
- 文件名使用 URL 的哈希值
- 包含页面的文本内容
- 用于对比检测变化

## 环境变量

```bash
WEB_MONITOR_DIR="/workspace/projects/workspace/skills/web-monitor/data"
```

这个环境变量告诉监控脚本数据存储在哪里。

## 使用方式

```bash
# 设置环境变量
export WEB_MONITOR_DIR="/workspace/projects/workspace/skills/web-monitor/data"
export PATH="$HOME/.local/bin:$PATH"

# 运行监控
cd /workspace/projects/workspace
uv run --with beautifulsoup4 python skills/web-monitor/scripts/monitor.py check
```

或者使用便捷脚本：
```bash
bash /workspace/projects/workspace/skills/web-monitor/scripts/run.sh check
```

## 打包分享

要分享给其他人时，只需要：

1. **复制整个 skill 目录：**
   ```bash
   cp -r workspace/skills/web-monitor/ /path/to/destination/
   ```

2. **包含的内容：**
   - ✅ scripts/monitor.py（核心脚本）
   - ✅ scripts/run.sh（便捷脚本）
   - ✅ SKILL.md（使用说明）
   - ✅ README.md（项目说明）
   - ⚠️ data/（数据目录，可选）

3. **排除的内容：**
   - ❌ data/snapshots/（历史快照，不必要）
   - ❌ data/watches.json（用户配置，需要重新配置）

## 首次使用配置

分享给行政老师后，他们需要：

1. 安装依赖：
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. 添加监控任务：
   ```bash
   export WEB_MONITOR_DIR="技能所在目录/data"
   export PATH="$HOME/.local/bin:$PATH"

   uv run --with beautifulsoup4 python scripts/monitor.py add \
     "https://example.com" --name "监控名称"
   ```

3. 设置定时任务（可选）
