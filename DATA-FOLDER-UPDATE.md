# 文件夹名称更新说明

## 更改内容

**隐藏文件夹改为可见文件夹**

- ❌ 旧：`.data/`（隐藏文件夹）
- ✅ 新：`data/`（可见文件夹）

## 更新时间

2026-04-24 11:27

## 更新原因

用户要求将数据文件夹改为显式可见，方便查看和管理。

## 更新的文件

### 1. 目录结构

```
workspace/skills/web-monitor/
├── data/                      # ✅ 新：可见文件夹
│   ├── watches.json          # 监控配置
│   └── snapshots/            # 页面快照
├── scripts/
│   ├── monitor.py
│   └── run.sh                # ✅ 更新路径引用
├── SKILL.md                   # ✅ 更新说明文档
├── STRUCTURE.md              # ✅ 更新目录结构说明
└── .gitignore                # ✅ 更新忽略规则
```

### 2. 具体修改

#### scripts/run.sh
```bash
# 修改前
export WEB_MONITOR_DIR="/workspace/projects/workspace/skills/web-monitor/.data"

# 修改后
export WEB_MONITOR_DIR="/workspace/projects/workspace/skills/web-monitor/data"
```

#### .gitignore
```
# 修改前
.data/

# 修改后
data/
```

#### SKILL.md
- 所有 `.data/` 引用改为 `data/`
- 环境变量示例更新

#### STRUCTURE.md
- 目录结构图更新
- 所有路径引用更新

## 验证

✅ 监控功能正常：
```bash
bash scripts/run.sh check "中山大学软工研招"
# 输出：✅ 中山大学软工研招: no changes
```

✅ 数据完整性：
- `data/watches.json` - 存在
- `data/snapshots/` - 存在

✅ 文档一致性：
- SKILL.md - 已更新
- STRUCTURE.md - 已更新
- .gitignore - 已更新

## 使用说明

### 原有用户（已配置监控）

无需任何操作，现有监控任务会自动继续工作。

### 新用户（首次使用）

```bash
# 添加监控任务
cd /path/to/web-monitor
bash scripts/run.sh add "https://example.com" --name "监控名称"
```

## 打包分享

打包时，`data/` 文件夹会可见：

```bash
# 打包
zip -r web-monitor-skill.zip web-monitor/

# 解压后，data 文件夹可见
unzip web-monitor-skill.zip
ls -la web-monitor/
# 可以看到 data/ 文件夹（不需要按 Ctrl+H）
```

## 影响范围

- ✅ 监控功能：无影响
- ✅ 数据完整性：无影响
- ✅ 用户使用：无影响
- ⚠️ 文档路径：已全部更新
- ⚠️ 环境变量：已全部更新

## 回滚方案

如需回滚到隐藏文件夹，执行：

```bash
# 1. 重命名文件夹
mv /workspace/projects/workspace/skills/web-monitor/data /workspace/projects/workspace/skills/web-monitor/.data

# 2. 更新 scripts/run.sh 中的路径
# 3. 更新 SKILL.md 中的说明
# 4. 更新 STRUCTURE.md 中的说明
# 5. 更新 .gitignore
```

## 注意事项

- ✅ 现在可以直接在文件管理器中看到 `data/` 文件夹
- ✅ 不需要按 `Ctrl+H` 显示隐藏文件
- ✅ 所有文档已同步更新
- ⚠️ Git 会忽略 `data/` 文件夹（已在 .gitignore 中配置）
