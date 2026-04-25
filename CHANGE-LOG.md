# Web Monitor 多页抓取功能修改记录

## 修改日期

2026-04-24

## 修改内容

### 修改函数：`fetch_content`

**位置：** `scripts/monitor.py` 第 42-115 行

**修改前：**
- 只抓取单个 URL 的内容
- 不支持多页抓取

**修改后：**
- 自动抓取分页内容（最多5页）
- 从 `?page=0` 开始，依次尝试 `?page=1` 到 `?page=4`
- 智能停止：空页、重复页、错误页自动停止

## 工作原理

### 分页URL构造

```
输入URL: https://cse.sysu.edu.cn/undergraduate/inform

构造为:
- page 0: https://cse.sysu.edu.cn/undergraduate/inform?page=0
- page 1: https://cse.sysu.edu.cn/undergraduate/inform?page=1
- page 2: https://cse.sysu.edu.cn/undergraduate/inform?page=2
- page 3: https://cse.sysu.edu.cn/undergraduate/inform?page=3
- page 4: https://cse.sysu.edu.cn/undergraduate/inform?page=4
```

### 抓取流程

1. 抓取 `?page=0`
2. 尝试抓取 `?page=1`
   - 成功 → 继续抓取 `?page=2`
   - 失败（404/空页）→ 停止
3. 重复直到 `?page=4` 或遇到停止条件

### 停止条件

- 页面返回 404
- 页面内容少于 100 字符
- 页面内容与前一页完全相同
- 已抓取 5 页（page 0-4）

## 测试结果

### 测试1：中山大学软工本科招生

```bash
bash scripts/run.sh check "中山大学软工本科招生"

输出:
Fetching up to 5 pages for https://sse.sysu.edu.cn/development/development02...
Fetched page 1 successfully.
Fetched page 2 successfully.
Fetched page 3 successfully.
Fetched page 4 successfully.
🔔 CHANGED: 中山大学软工本科招生
   +421 lines / -0 lines
```

✅ **成功抓取5页，内容增加421行**

### 测试2：中山大学数科本科通知

```bash
bash scripts/run.sh check "中山大学数科本科通知-第2页"

输出:
Fetching up to 5 pages for https://cse.sysu.edu.cn/undergraduate/inform...
Fetched page 1 successfully.
Fetched page 2 successfully.
Fetched page 3 successfully.
Fetched page 4 successfully.
🔔 CHANGED: 中山大学数科本科通知-第2页
   +1454 lines / -129 lines
```

✅ **成功抓取5页，内容大幅增加**

## 当前监控任务

| 序号 | 任务名称 | URL | 状态 |
|------|---------|-----|------|
| 1 | 中山大学软工研招 | development/development03 | checked 3x, 0 changes |
| 2 | 中山大学软工本科招生 | development/development02 | checked 1x, 1 changes |
| 3 | 中山大学数科本科通知-第2页 | undergraduate/inform?page=2 | checked 1x, 1 changes |

## 优势

1. ✅ **自动多页抓取** - 无需手动指定多页URL
2. ✅ **智能停止** - 自动检测空页和重复页
3. ✅ **性能可控** - 最多5页，不会过度抓取
4. ✅ **礼貌延迟** - 每页之间0.5秒延迟
5. ✅ **向后兼容** - 单页网站仍然正常工作

## 注意事项

1. **URL格式要求** - 适用于使用 `?page=N` 分页的网站
2. **BeautifulSoup4依赖** - 已包含在依赖中
3. **网络延迟** - 抓取5页需要约2-3秒（含延迟）
4. **快照大小** - 多页合并后的快照会更大

## 代码变更统计

| 项目 | 修改前 | 修改后 |
|------|-------|--------|
| 函数行数 | 36 行 | 约 75 行 |
| 功能 | 单页抓取 | 多页抓取（最多5页） |
| 复杂度 | 简单 | 中等（添加循环和停止逻辑） |

## 后续建议

1. **添加第一页监控任务** - 对于数科通知，建议也添加 `?page=0` 的监控
2. **设置定时任务** - 使用 cron 定期自动检查更新
3. **关键词筛选** - 添加"博士"、"推免"等关键词筛选功能

## 回滚方案

如需回滚到单页抓取版本：

```bash
# 1. 备份当前版本
cp scripts/monitor.py scripts/monitor_multi_page.py

# 2. 恢复原始版本（从git或其他备份）
git checkout scripts/monitor.py
```
