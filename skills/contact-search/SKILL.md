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
---

# Contact Search Skill

企业联系方式搜索与发现技能，提供从需求解析到深度爬取的完整解决方案。

## 核心理念

本技能采用**两层架构**设计：

1. **首层：需求解析** - Agent利用自身思考能力理解用户意图，生成多样化搜索查询
2. **第二层：搜索执行** - 根据解析结果执行浅搜索或深搜索，提取联系方式

## 首层：需求解析（Agent核心任务）

需求解析是整个搜索流程的起点，需要Agent调用大模型能力深入理解用户意图。

### 解析目标

将用户的自然语言输入转化为结构化的搜索意图，包括：
- 识别搜索对象（公司、行业、地区）
- 确定需要的联系方式类型
- 生成多样化的搜索查询

### 解析步骤

#### 1. 提取关键信息

从用户输入中识别：

**必需信息**：
- 公司名称/品牌名
- 行业领域（如"太阳能冰箱"、"医疗器械"）
- 地区/国家（如"尼日利亚"、"东南亚"）

**可选信息**：
- 特定联系方式需求（如"只需要WhatsApp"）
- 搜索优先级（速度 vs 完整性）
- 语言偏好

#### 2. 理解搜索场景

**场景A：特定公司搜索**
```
用户输入: "帮我找华为的联系方式"
解析结果:
  - 搜索对象: 华为（单一明确公司）
  - 需要类型: 邮箱、电话、LinkedIn等
  - 搜索策略: 官网优先，社交媒体补充
```

**场景B：行业提供商搜索**
```
用户输入: "帮我寻找尼日利亚太阳能冰箱提供商的联系方式"
解析结果:
  - 搜索对象: 尼日利亚太阳能冰箱行业（多个潜在公司）
  - 需要类型: 邮箱、电话、WhatsApp等
  - 搜索策略: 行业目录、本地搜索、供应商列表
```

**场景C：特定页面抓取**
```
用户输入: "这个页面可能有联系方式，帮我提取：https://example.com/contact"
解析结果:
  - 搜索对象: 单一页面
  - 需要类型: 页面上所有联系方式
  - 搜索策略: 直接页面抓取
```

#### 3. 生成多样化查询

**查询生成原则**：
- **多角度覆盖**：官网、联系方式、社交媒体、行业目录
- **语言变体**：中英文查询都尝试
- **地域限定**：包含国家/地区关键词
- **特定操作符**：使用`site:`限定域名

**示例：尼日利亚太阳能冰箱提供商**

```
查询组1 - 行业搜索:
  - "尼日利亚太阳能冰箱提供商"
  - "Nigeria solar refrigerator suppliers"
  - "solar fridge freezer Nigeria"

查询组2 - 地域细分:
  - "尼日利亚东部 太阳能冰箱"
  - "尼日利亚北部 solar refrigerator"
  - "Lagos solar freezer suppliers"

查询组3 - 产品变体:
  - "太阳能冰柜 尼日利亚 contact"
  - "solar mobile refrigerator Nigeria"
  - "solar powered freezer Nigeria suppliers"

查询组4 - 联系方式导向:
  - "Nigeria solar refrigerator suppliers contact email"
  - "solar fridge Nigeria whatsapp phone"
  - "site:linkedin.com Nigeria solar refrigerator"
```

**示例：特定公司（Limetech）**

```
查询组1 - 官网搜索:
  - "Limetech official website"
  - "Limetech company contact"

查询组2 - 联系方式:
  - "Limetech contact email phone"
  - "Limetech 联系方式"

查询组3 - 社交媒体:
  - "site:linkedin.com Limetech company"
  - "site:facebook.com Limetech"
  - "site:instagram.com Limetech"

查询组4 - 文档搜索:
  - "Limetech PDF contact information"
  - "Limetech brochure email"
```

### 输出格式

解析完成后，生成结构化的搜索意图：

```python
class SearchIntent:
    company_name: str              # 公司名称（如为行业搜索则为None）
    industry: str                  # 行业领域
    region: str                    # 地区/国家
    search_queries: List[str]      # 生成的搜索查询列表
    required_contact_types: List   # 需要的联系方式类型
    priority: str                  # "speed" 或 "completeness"
```

## 第二层：搜索执行

搜索执行分为两个阶段，详细实现请参考对应的reference文档：

### 浅搜索（Shallow Search）

**用途**：广泛收集信息，快速获取初步结果

**工具**：TavilySearchTool

**详细指南**：请阅读 [references/shallow-search.md](references/shallow-search.md)

**何时使用**：
- 不知道公司官网
- 需要快速了解行业提供商
- 需要收集多个候选公司

### 深搜索（Deep Search）

**用途**：针对特定实体深度挖掘，提取完整联系方式

**工具**：
- TavilySiteContactCrawlTool（站点级爬取）
- SpiderSinglePageContactTool（单页面抓取）

**详细指南**：请阅读 [references/deep-search.md](references/deep-search.md)

**何时使用**：
- 明确提到要使用本skill的深度搜索功能的时候
- 已知官网入口
- 浅搜索未找到完整联系方式
- 需要深度提取页面信息

## 工具概览

### Tool 1: TavilySearchTool

**类型**：CrewAI内置工具

**用途**：网络搜索引擎，用于快速获取搜索结果

**关键参数**：
- `query`: 搜索查询字符串
- `search_depth`: "basic" 或 "advanced"
- `max_results`: 最大结果数（默认5）

**详细说明**：[references/tools-reference.md](references/tools-reference.md#tavilysearchtool)

### Tool 2: TavilySiteContactCrawlTool

**类型**：自定义工具（cobtainflow项目）

**用途**：站点级爬取，自动发现多个页面并提取联系人信息

**关键参数**：
- `url`: 起始URL
- `instruction_mode`: "contacts_only" | "contacts_and_summary"
- `max_depth`: 最大爬取深度（1-3）
- `limit`: 最大页面数（1-100）

**详细说明**：[references/tools-reference.md](references/tools-reference.md#tavilysitecontactcrawltool)

### Tool 3: SpiderSinglePageContactTool

**类型**：自定义工具（cobtainflow项目）

**用途**：单页面强制抓取与规则抽取

**关键参数**：
- `url`: 要抓取的页面URL
- `extract_contacts`: 是否提取联系方式
- `include_links`: 是否提取链接

**详细说明**：[references/tools-reference.md](references/tools-reference.md#spidersinglepagecontacttool)

## 标准操作流程

```
用户输入
    ↓
【首层：需求解析】
    ├─ 提取关键信息
    ├─ 理解搜索场景
    └─ 生成多样化查询
    ↓
【第二层：搜索执行】
    ├─ 浅搜索（TavilySearchTool）
    │   ├─ 执行搜索查询
    │   ├─ 评估结果相关性
    │   └─ 去重与格式化
    │
    └─ 深搜索（如需要）
        ├─ 有官网？→ TavilySiteContactCrawlTool
        ├─ 有具体页面？→ SpiderSinglePageContactTool
        └─ 聚合与验证结果
    ↓
输出结果
```

## 决策树

```
用户请求
│
├─ 是否知道具体页面URL？
│   ├─ 是 → 直接深搜索
│   │        └─ SpiderSinglePageContactTool
│   │
│   └─ 否 → 是否知道公司官网？
│       ├─ 是 → 直接深搜索
│       │        └─ TavilySiteContactCrawlTool
│       │
│       └─ 否 → 先浅搜索
│                ├─ TavilySearchTool
│                └─ 根据结果决定是否深搜索
```

## 使用示例

### 示例1：特定公司搜索

```
用户: "帮我找微软的联系方式"

执行流程:
1. 【需求解析】
   - 识别: 微软（单一公司）
   - 生成查询: ["Microsoft official website contact", "Microsoft contact email phone", ...]

2. 【浅搜索】
   - 使用TavilySearchTool搜索
   - 发现官网: https://microsoft.com

3. 【深搜索】
   - 使用TavilySiteContactCrawlTool爬取
   - 提取: 邮箱、电话、LinkedIn等

4. 【输出结果】
   - 返回完整的联系方式列表
```

### 示例2：行业提供商搜索

```
用户: "帮我寻找尼日利亚太阳能冰箱提供商的联系方式"

执行流程:
1. 【需求解析】
   - 识别: 尼日利亚 + 太阳能冰箱行业
   - 生成查询: ["Nigeria solar refrigerator suppliers", "solar fridge Nigeria contact", ...]

2. 【浅搜索】
   - 使用TavilySearchTool执行多个查询
   - 收集多个潜在提供商
   - 去重与评估

3. 【深搜索】
   - 对每个提供商进行深度爬取
   - 提取完整联系方式

4. 【输出结果】
   - 返回所有提供商的联系方式汇总
```

### 示例3：特定页面抓取

```
用户: "这个页面可能有联系方式，帮我提取：https://example.com/contact-us"

执行流程:
1. 【需求解析】
   - 识别: 单一页面URL
   - 跳过浅搜索

2. 【深搜索】
   - 直接使用SpiderSinglePageContactTool
   - 提取页面所有联系方式

3. 【输出结果】
   - 返回页面上的联系方式
```

## 环境要求

```bash
# 必需的环境变量
TAVILY_API_KEY=your_api_key_here

# 可选的环境变量
OPENAI_API_KEY=your_api_key_here

# 安装依赖
pip install crewai[tools]
pip install spider-rs
pip install tavily-python
pip install beautifulsoup4 lxml
```

## 导入说明

```python
# CrewAI内置工具
from crewai_tools import TavilySearchTool

# 自定义工具（cobtainflow项目）
from cobtainflow.tools.contact_discovery_tools import (
    SpiderSinglePageContactTool,
    TavilySiteContactCrawlTool
)
```

## 输出格式

最终输出应包含：

1. **搜索摘要**
   - 搜索的公司/提供商数量
   - 成功/失败/部分成功的数量
   - 总计找到的联系方式数量

2. **详细结果**（每个公司）
   - 公司名称和官网
   - 找到的联系方式列表（**已过滤：仅保留置信度≥0.7的结果**）
   - 数据来源和证据
   - 缺失信息提示

3. **建议下一步**
   - 如果有缺失信息，建议补充搜索策略
   - 如果找到候选链接，建议进一步探索

## 置信度过滤机制

**重要**：系统自动过滤置信度低于0.7的联系方式，确保结果质量。

### 置信度等级

- **0.9-1.0** (极高): mailto:链接、tel:链接、官方联系页面直接提取
- **0.8-0.9** (高): 官方网站、LinkedIn等权威来源
- **0.7-0.8** (中): 可靠的第三方网站
- **<0.7** (低): 不可靠来源（已被过滤）

### 过滤时机

1. **浅搜索后**: 过滤提取的初步联系方式
2. **深搜索后**: 过滤深度提取的联系方式
3. **最终输出前**: 确保所有结果置信度≥0.7

---

**重要提示**：
- 首层需求解析是Agent的核心任务，需要充分利用大模型的思考能力
- 第二层的详细实现请务必阅读reference文件夹中的文档
- 工具的详细参数和返回格式请参考 [references/tools-reference.md](references/tools-reference.md)
- **所有输出的联系方式均经过置信度过滤（≥0.7），无需手动验证**
