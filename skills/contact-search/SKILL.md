---
name: contact-search
description: |
  企业联系方式搜索与发现技能。用于搜索公司信息、提取联系方式（邮箱、电话、WhatsApp、LinkedIn等）。
  
  当用户需要以下操作时触发此技能：
  - 搜索公司或企业的联系信息
  - 查找特定公司的邮箱、电话、WhatsApp等联系方式
  - 对公司进行浅层或深度的信息收集
  - 从网站提取联系人信息
  - 批量搜索多家公司的联系方式
  
  即使是简单的"帮我找某公司的联系方式"或"搜索XX公司的信息"等请求，也应使用此技能。
allowed-tools: TavilySearchTool, SpiderSinglePageContactTool, TavilySiteContactCrawlTool
---

# Contact Search Skill

企业联系方式搜索与发现技能，提供从需求解析到深度爬取的完整解决方案。

## 核心工作流程

```
用户输入
    ↓
【Phase 1: 需求解析】
    ├─ 理解用户意图
    ├─ 识别搜索对象（公司/行业/地区）
    └─ 生成多样化搜索查询
    ↓
【Phase 2: 浅搜索】（可选）
    ├─ 执行搜索查询
    ├─ 累积所有结果
    ├─ 去重和过滤
    └─ 评估是否需要深搜索
    ↓
【Phase 3: 深搜索】（如需要）
    ├─ 站点爬取（TavilySiteContactCrawlTool）
    └─ 或单页面抓取（SpiderSinglePageContactTool）
    ↓
【输出】
    └─ 结构化JSON结果
```

## Phase 1: 需求解析

### 理解用户意图

**你需要自主决定**：
- 识别搜索对象（特定公司 vs 行业提供商）
- 确定需要的联系方式类型
- 决定搜索策略（速度优先 vs 完整性优先）
- 生成多样化的搜索查询

### 查询生成原则

**你应该**：
- 根据用户需求灵活调整查询数量（不必局限于固定数量）
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

## Phase 2: 浅搜索

### 使用现成脚本

**重要**：你有一个现成的脚本可以直接使用！

```python
from scripts.search_executor import execute_shallow_search, aggregate_shallow_results

# 方式1: 使用完整流程
results = execute_shallow_search(intents, search_tool)

# 方式2: 自己控制流程
all_items = []
for query in your_queries:  # 你决定执行多少个查询
    result = search_tool._run(query=query, search_depth="basic", max_results=5)
    items = result.get("results", [])
    all_items.extend(items)

# 使用聚合函数去重和提取
aggregated = aggregate_shallow_results(company_name, all_items, required_types)
```

### 关键原则

**必须累积所有查询的结果**，不能只保留最后一个！

```python
# ❌ 错误：只保留最后一个
for query in queries:
    result = search_tool._run(query=query)
    final_result = result  # 覆盖了之前的结果！

# ✅ 正确：累积所有结果
all_results = []
for query in queries:
    result = search_tool._run(query=query)
    items = result.get("results", [])
    all_results.extend(items)  # 累积
```

### 自主决策

**你应该根据情况决定**：
- 执行多少个查询？（根据结果质量动态调整）
- 使用什么搜索深度？（basic vs advanced）
- 每个查询返回多少结果？（3-10个）
- 是否需要深搜索？（根据浅搜索结果判断）

## Phase 3: 深搜索

### 决策树

```
是否知道具体页面URL？
├─ 是 → SpiderSinglePageContactTool
└─ 否 → 是否知道公司官网？
    ├─ 是 → TavilySiteContactCrawlTool
    └─ 否 → 先浅搜索，再根据结果决定
```

### 使用现成脚本

```python
from scripts.search_executor import execute_deep_search, crawl_single_site, spider_single_page

# 方式1: 使用完整流程
deep_results = execute_deep_search(shallow_results, crawl_tool, spider_tool)

# 方式2: 单独调用
result = crawl_single_site(company_name, website_url, crawl_tool)
result = spider_single_page(company_name, page_url, spider_tool)
```

## 输出格式

**必须输出结构化的 JSON 格式**：

```json
{
  "search_summary": {
    "total_companies": 1,
    "successful": 0,
    "partial": 1,
    "failed": 0,
    "total_contacts": 5
  },
  "companies": [
    {
      "company_name": "公司名称",
      "website_url": "https://example.com",
      "search_status": "partial",
      "contacts": [
        {
          "type": "email",
          "value": "contact@example.com",
          "normalized": "contact@example.com",
          "source_url": "https://example.com/contact",
          "confidence": 0.9
        }
      ],
      "source_urls": ["https://example.com/contact"],
      "missing_info": ["no_whatsapp"]
    }
  ],
  "suggestions": ["可以尝试搜索 WhatsApp 官方账号"]
}
```

## 可用脚本

本 skill 提供了完整的辅助脚本 `scripts/search_executor.py`：

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
3. 可以节省你的时间和token

**但你有完全的自主权**：
- 如果脚本不符合你的需求，可以自己实现
- 可以修改脚本的参数（查询数量、搜索深度等）
- 可以组合使用脚本函数和自己的逻辑

## 工具说明

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

## 置信度过滤

**重要**：所有输出的联系方式置信度必须 ≥ 0.7

- **0.9-1.0**: mailto链接、tel链接、官方联系页面
- **0.8-0.9**: 官方网站、LinkedIn等权威来源
- **0.7-0.8**: 可靠的第三方网站
- **<0.7**: 必须过滤掉

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

## 参考文档

- [references/shallow-search.md](references/shallow-search.md) - 浅搜索详细指南
- [references/deep-search.md](references/deep-search.md) - 深搜索详细指南
- [references/tools-reference.md](references/tools-reference.md) - 工具详细说明

---

**核心原则**：
- 你有完全的自主权决定搜索策略
- 使用现成脚本可以节省时间和token
- 必须累积所有查询的结果
- 必须输出结构化的JSON格式
- 所有联系方式置信度必须 ≥ 0.7
