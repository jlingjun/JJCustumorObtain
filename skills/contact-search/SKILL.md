---
name: contact-search
description: |
  企业联系方式搜索与发现技能。提供搜索公司信息、提取联系方式的能力集合。
  
  当agent需要以下操作时可使用此skill：
  - 搜索公司或企业的联系信息
  - 查找特定公司的邮箱、电话、WhatsApp等联系方式
  - 从网站提取联系人信息
  - 执行浅层或深度的信息收集
  
  注意：此skill提供能力和工具，具体输出格式由Task定义。
allowed-tools: TavilySearchTool, SpiderSinglePageContactTool, TavilySiteContactCrawlTool
---

# Contact Search Skill

企业联系方式搜索与发现技能，提供从需求解析到深度爬取的能力集合。

## ⚠️ 重要说明

**此skill只提供能力和工具，不定义输出格式。**

- ✅ 提供搜索工具和方法
- ✅ 提供最佳实践指导
- ✅ 提供辅助脚本
- ❌ **不定义输出格式**（由Task的expected_output定义）
- ❌ **不定义完整工作流程**（由Task的description定义）

**输出格式必须严格遵循Task的expected_output定义（NormalSearchTaskOutput）。**

## 核心能力

### 1. 需求解析能力

**自主决策**：
- 识别搜索对象（特定公司 vs 行业提供商）
- 确定需要的联系方式类型
- 决定搜索策略（速度优先 vs 完整性优先）
- 生成多样化的搜索查询

### 2. 浅搜索能力

使用TavilySearchTool执行网络搜索。

**查询生成原则**：
- 根据用户需求灵活调整查询数量
- 使用多角度覆盖：官网、联系方式、社交媒体、行业目录
- 尝试语言变体：中英文查询
- 包含地域关键词（如果用户指定了地区）
- 使用 `site:` 操作符限定特定域名

**示例查询**：
```
# 特定公司
["{company} official website contact", 
 "{company} 联系方式",
 "site:linkedin.com {company} company"]

# 行业提供商
["{region} {industry} suppliers",
 "{region} {industry} contact email",
 "site:linkedin.com {region} {industry}"]
```

**关键原则**：
- **必须累积所有查询的结果**，不能只保留最后一个！
- 根据结果质量动态调整策略

### 3. 深搜索能力

**决策树**：
```
是否知道具体页面URL？
├─ 是 → SpiderSinglePageContactTool
└─ 否 → 是否知道公司官网？
    ├─ 是 → TavilySiteContactCrawlTool
    └─ 否 → 先浅搜索，再根据结果决定
```

## 可用工具

### TavilySearchTool

**用途**：网络搜索

**关键参数**：
- `query`: 搜索查询
- `search_depth`: "basic"（快）或 "advanced"（全面）
- `max_results`: 返回结果数（默认5）

**详细文档**：[references/tools-reference.md](references/tools-reference.md)

### TavilySiteContactCrawlTool

**用途**：站点级爬取

**关键参数**：
- `url`: 起始URL
- `max_depth`: 爬取深度（1-3）
- `limit`: 最大页面数（1-100）

### SpiderSinglePageContactTool

**用途**：单页面抓取（仅提取联系方式）

**关键参数**：
- `url`: 页面URL
- `extract_contacts`: 是否提取联系方式（默认True）

## 辅助脚本

本skill提供了辅助脚本 `scripts/search_executor.py`：

### 核心函数

- `execute_shallow_search(intents, search_tool)` - 执行浅搜索（包含累积和去重）
- `aggregate_shallow_results(company_name, search_items, required_types)` - 聚合和去重结果
- `extract_contacts_from_text(text, source_url)` - 从文本提取联系方式
- `execute_deep_search(shallow_results, crawl_tool, spider_tool)` - 执行深搜索
- `crawl_single_site(company_name, website_url, crawl_tool)` - 爬取单个站点
- `spider_single_page(company_name, page_url, spider_tool)` - 抓取单个页面

### 使用建议

**推荐使用脚本**，因为：
1. 已经实现了累积和去重逻辑
2. 经过测试和优化
3. 可以节省时间和token

**但你有完全的自主权**：
- 如果脚本不符合你的需求，可以自己实现
- 可以修改脚本的参数（查询数量、搜索深度等）
- 可以组合使用脚本函数和自己的逻辑

## 最佳实践

### 1. 自主决策

**不要**：
- 机械地执行固定数量的查询
- 忽略搜索结果的质量
- 盲目执行深搜索

**应该**：
- 根据结果质量动态调整策略
- 如果前几个查询已经找到足够信息，可以停止
- 如果结果质量差，尝试不同的查询策略

### 2. 结果累积

**必须**：
- 累积所有查询的结果
- 在聚合过程中实时去重
- 保留置信度最高的联系方式

### 3. 错误处理

```python
# 建议的错误处理
for query in queries:
    try:
        result = search_tool._run(query=query)
        all_results.extend(result.get("results", []))
    except Exception as e:
        # 记录错误但继续执行其他查询
        print(f"查询失败: {query}, 错误: {e}")
        continue
```

### 4. 置信度过滤

**重要**：所有输出的联系方式置信度必须 ≥ 0.7

- **0.9-1.0**: mailto链接、tel链接、官方联系页面
- **0.8-0.9**: 官方网站、LinkedIn等权威来源
- **0.7-0.8**: 可靠的第三方网站
- **<0.7**: 必须过滤掉

### 5. 证据保留

**每条联系方式都必须包含**：
- `source_url`: 来源URL
- `evidence`: 简短证据描述
- `confidence`: 置信度评分

## 参考文档

- [references/shallow-search.md](references/shallow-search.md) - 浅搜索详细指南
- [references/deep-search.md](references/deep-search.md) - 深搜索详细指南
- [references/tools-reference.md](references/tools-reference.md) - 工具详细说明

---

## ⚠️ 核心原则

1. **输出格式由Task定义**，不是由skill定义
2. 你有完全的自主权决定搜索策略
3. 使用现成脚本可以节省时间和token
4. 必须累积所有查询的结果
5. 所有联系方式置信度必须 ≥ 0.7
6. 每条联系方式都必须有source_url和evidence
