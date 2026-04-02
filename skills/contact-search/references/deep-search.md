# 深搜索（Deep Search）实现指南

## 概述

深搜索是搜索流程的第二层第二阶段，主要用于针对特定实体进行深度挖掘，提取完整联系方式。当已知官网入口或浅搜索未找到完整信息时，深搜索是必要的步骤。

## 核心工具

深搜索使用两个工具，根据不同场景选择：

### Tool 1: TavilySiteContactCrawlTool

**适用场景**：
- 已知官网或可信入口
- 需要站点级抽取（/contact, /about, /team等多页信息聚合）
- 需要公司简介 + 联系方式一起找

### Tool 2: SpiderSinglePageContactTool

**适用场景**：
- 已经知道一个具体页面URL
- 需要尽量拿全该页所有链接
- 怀疑页面里有Tavily没提取出的WhatsApp/邮箱/电话
- 需要保留页面级文本证据

## 工具选择决策

```
需要深搜索？
│
├─ 是否知道官网入口？
│   ├─ 是 → 使用 TavilySiteContactCrawlTool
│   │        （站点级爬取，自动发现多个页面）
│   │
│   └─ 否 → 是否知道具体页面URL？
│       ├─ 是 → 使用 SpiderSinglePageContactTool
│       │        （单页面深度抓取）
│       │
│       └─ 否 → 返回浅搜索结果
│                （无法进行深搜索）
```

## Tool 1: TavilySiteContactCrawlTool

### 导入与实例化

```python
from cobtainflow.tools.contact_discovery_tools import TavilySiteContactCrawlTool

crawl_tool = TavilySiteContactCrawlTool()
```

### 参数详解

#### 必需参数

- **url** (str): 起始URL
  - 网站的入口URL
  - 通常是官网首页或联系页面

#### 可选参数

- **company_name** (str): 公司名称
  - 用于上下文和结果标注
  - 可选但建议提供

- **instruction_mode** (str): 爬取指令模式
  - `"contacts_only"`: 只查找联系方式
  - `"contacts_and_summary"`: 查找联系方式和公司简介（推荐）
  - `"custom"`: 自定义指令
  - 默认值: `"contacts_and_summary"`

- **custom_instruction** (str): 自定义指令
  - 当instruction_mode为"custom"时使用
  - 示例: "Find all email addresses and phone numbers on contact pages"

- **max_depth** (int): 最大爬取深度
  - 控制爬取的深度层级
  - 范围: 1-3
  - 默认值: 2
  - 建议: 
    - 1: 只爬取起始页面
    - 2: 爬取起始页面及其直接链接（推荐）
    - 3: 更深层的爬取，耗时更长

- **max_breadth** (int): 每层最大广度
  - 每个层级最多爬取的页面数
  - 范围: 1-50
  - 默认值: 20

- **limit** (int): 最大页面数
  - 总共最多爬取的页面数
  - 范围: 1-100
  - 默认值: 30
  - 建议: 10-30之间平衡速度和完整性

- **select_paths** (List[str]): 包含的路径模式
  - 只爬取匹配这些模式的路径
  - 示例: `["/contact", "/about", "/team"]`

- **exclude_paths** (List[str]): 排除的路径模式
  - 排除匹配这些模式的路径
  - 示例: `["/blog", "/news", "/product"]`

- **select_domains** (List[str]): 包含的域名
  - 只爬取这些域名下的页面
  - 示例: `["example.com", "www.example.com"]`

- **exclude_domains** (List[str]): 排除的域名
  - 排除这些域名
  - 示例: `["facebook.com", "twitter.com"]`

- **allow_external** (bool): 是否允许外部链接
  - 是否爬取外部域名的页面
  - 默认值: False
  - 建议: 保持False以专注于目标站点

- **extract_depth** (str): 提取深度
  - `"basic"`: 基础提取
  - `"advanced"`: 高级提取（推荐）
  - 默认值: `"basic"`

- **output_format** (str): 输出格式
  - `"markdown"`: Markdown格式（推荐）
  - `"text"`: 纯文本格式
  - 默认值: `"markdown"`

- **chunks_per_source** (int): 每个源的块数
  - 范围: 1-10
  - 默认值: 3

- **timeout** (float): 超时时间（秒）
  - 范围: 10.0-300.0
  - 默认值: 60.0
  - 建议: 30-90秒之间

### 返回格式

返回`NormalizedContactExtractionResult`的JSON字符串：

```python
{
    "status": "success" | "partial" | "failed",
    "tool_name": "tavily_site_contact_crawl",
    "requested_url": "https://example.com",
    "resolved_url": "https://www.example.com",
    "contacts": [
        {
            "type": "email" | "phone" | "whatsapp" | "linkedin" | ...,
            "value": "原始值",
            "normalized": "标准化后的值",
            "source_url": "来源页面URL",
            "source_context": "上下文文本",
            "confidence": 0.9
        }
    ],
    "candidate_links": [
        {
            "url": "链接URL",
            "role": "contact" | "about" | "team" | ...,
            "anchor_text": "链接文本",
            "source_url": "来源页面",
            "is_external": false
        }
    ],
    "page_evidence": [
        {
            "page_url": "页面URL",
            "page_title": "页面标题",
            "summary": "页面摘要",
            "supports_fields": ["email", "phone"],
            "snippet": "相关文本片段",
            "contacts_found": 3,
            "links_found": 15
        }
    ],
    "missing_hints": ["no_whatsapp", "no_linkedin"],
    "warnings": [],
    "raw_debug": {}
}
```

### 使用示例

#### 基础用法

```python
def crawl_website(website_url, company_name):
    """
    使用TavilySiteContactCrawlTool爬取网站
    
    Args:
        website_url: 网站URL
        company_name: 公司名称
    
    Returns:
        DeepSearchResult对象
    """
    try:
        # 执行爬取
        result_json = crawl_tool._run(
            url=website_url,
            company_name=company_name,
            instruction_mode="contacts_and_summary",
            max_depth=2,
            limit=30,
            timeout=60.0
        )
        
        # 解析结果
        result = json.loads(result_json)
        
        # 转换为DeepSearchResult
        return DeepSearchResult(
            company_name=company_name,
            website_url=website_url,
            contacts=parse_contacts(result["contacts"]),
            candidate_links=result["candidate_links"],
            page_evidence=result["page_evidence"],
            missing_hints=result["missing_hints"],
            search_status=result["status"]
        )
        
    except Exception as e:
        return DeepSearchResult(
            company_name=company_name,
            website_url=website_url,
            search_status="failed",
            missing_hints=[f"crawl_error: {str(e)}"]
        )
```

#### 高级用法：限定路径

```python
# 只爬取联系相关页面
result = crawl_tool._run(
    url="https://example.com",
    instruction_mode="contacts_only",
    select_paths=["/contact", "/about", "/team", "/support"],
    max_depth=2,
    limit=20
)
```

#### 高级用法：自定义指令

```python
# 使用自定义指令查找特定信息
result = crawl_tool._run(
    url="https://example.com",
    instruction_mode="custom",
    custom_instruction="Find WhatsApp contact numbers and business email addresses",
    max_depth=2,
    limit=25
)
```

## Tool 2: SpiderSinglePageContactTool

### 导入与实例化

```python
from cobtainflow.tools.contact_discovery_tools import SpiderSinglePageContactTool

spider_tool = SpiderSinglePageContactTool()
```

### 参数详解

#### 必需参数

- **url** (str): 要抓取的页面URL
  - 必须是完整的URL（包含协议）

#### 可选参数

- **company_name** (str): 公司名称
  - 用于上下文和结果标注

- **include_html** (bool): 是否包含原始HTML
  - 默认值: False
  - 调试时可设为True

- **include_text** (bool): 是否包含提取的文本
  - 默认值: True

- **include_links** (bool): 是否提取和分类链接
  - 默认值: True
  - 建议保持True以发现更多候选页面

- **extract_contacts** (bool): 是否提取联系方式
  - 默认值: True
  - 建议保持True

- **max_text_chars** (int): 最大文本字符数
  - 默认值: 12000
  - 限制提取的文本长度

- **max_links** (int): 最大链接数
  - 默认值: 200
  - 限制返回的链接数量

- **classify_links** (bool): 是否分类链接
  - 默认值: True
  - 自动识别contact、about、team等页面

### 返回格式

返回`NormalizedContactExtractionResult`的JSON字符串（格式同TavilySiteContactCrawlTool）。

### 使用示例

#### 基础用法

```python
def spider_page(page_url, company_name):
    """
    使用SpiderSinglePageContactTool抓取单个页面
    
    Args:
        page_url: 页面URL
        company_name: 公司名称
    
    Returns:
        DeepSearchResult对象
    """
    try:
        # 执行抓取
        result_json = spider_tool._run(
            url=page_url,
            company_name=company_name,
            extract_contacts=True,
            include_links=True
        )
        
        # 解析结果
        result = json.loads(result_json)
        
        # 转换为DeepSearchResult
        return DeepSearchResult(
            company_name=company_name,
            website_url=page_url,
            contacts=parse_contacts(result["contacts"]),
            candidate_links=result["candidate_links"],
            page_evidence=result["page_evidence"],
            missing_hints=result["missing_hints"],
            search_status=result["status"]
        )
        
    except Exception as e:
        return DeepSearchResult(
            company_name=company_name,
            website_url=page_url,
            search_status="failed",
            missing_hints=[f"spider_error: {str(e)}"]
        )
```

#### 高级用法：调试模式

```python
# 启用调试信息
result = spider_tool._run(
    url="https://example.com/contact",
    include_html=True,
    include_text=True,
    max_text_chars=20000
)
```

## 执行流程

### Step 1: 确定工具

根据已知信息选择合适的工具：

```python
def select_deep_search_tool(shallow_result):
    """
    根据浅搜索结果选择深搜索工具
    
    Args:
        shallow_result: ShallowSearchResult对象
    
    Returns:
        (tool_type, url) 元组
    """
    if shallow_result.website_url:
        # 有官网入口，使用TavilySiteContactCrawlTool
        return ("crawl", shallow_result.website_url)
    
    elif shallow_result.source_urls:
        # 有具体页面URL，使用SpiderSinglePageContactTool
        # 选择最相关的页面
        best_url = select_best_page(shallow_result.source_urls)
        return ("spider", best_url)
    
    else:
        # 无法进行深搜索
        return (None, None)
```

### Step 2: 执行深搜索

```python
def execute_deep_search(shallow_result, crawl_tool, spider_tool):
    """
    执行深搜索
    
    Args:
        shallow_result: 浅搜索结果
        crawl_tool: TavilySiteContactCrawlTool实例
        spider_tool: SpiderSinglePageContactTool实例
    
    Returns:
        DeepSearchResult对象
    """
    # 选择工具
    tool_type, url = select_deep_search_tool(shallow_result)
    
    if tool_type is None:
        # 无法深搜索，返回浅搜索结果
        return DeepSearchResult(
            company_name=shallow_result.company_name,
            website_url="",
            contacts=shallow_result.preliminary_contacts,
            search_status="partial",
            missing_hints=["no_website_found"]
        )
    
    # 执行深搜索
    if tool_type == "crawl":
        return crawl_website(url, shallow_result.company_name, crawl_tool)
    else:  # spider
        return spider_page(url, shallow_result.company_name, spider_tool)
```

### Step 3: 聚合结果

```python
def aggregate_deep_search_results(deep_results):
    """
    聚合多个深搜索结果
    
    Args:
        deep_results: DeepSearchResult列表
    
    Returns:
        最终的搜索摘要
    """
    all_contacts = []
    all_evidence = []
    
    for result in deep_results:
        all_contacts.extend(result.contacts)
        all_evidence.extend(result.page_evidence)
    
    # 去重联系方式
    unique_contacts = dedupe_contacts(all_contacts)
    
    # 置信度过滤：只保留置信度>=0.7的联系方式
    MIN_CONFIDENCE = 0.7
    unique_contacts = [c for c in unique_contacts if c.confidence >= MIN_CONFIDENCE]
    
    # 统计
    successful = sum(1 for r in deep_results if r.search_status == "success")
    partial = sum(1 for r in deep_results if r.search_status == "partial")
    failed = sum(1 for r in deep_results if r.search_status == "failed")
    
    return {
        "total_companies": len(deep_results),
        "successful": successful,
        "partial": partial,
        "failed": failed,
        "total_contacts": len(unique_contacts),
        "contacts": unique_contacts,
        "evidence": all_evidence
    }
```

## 最佳实践

### 1. 工具选择策略

```python
# 场景1：有官网，需要完整信息
if website_url and priority == "completeness":
    use_tool = "TavilySiteContactCrawlTool"
    params = {
        "max_depth": 2,
        "limit": 30,
        "instruction_mode": "contacts_and_summary"
    }

# 场景2：有具体联系页面
elif contact_page_url:
    use_tool = "SpiderSinglePageContactTool"
    params = {
        "extract_contacts": True,
        "include_links": True
    }

# 场景3：只需要快速验证
elif priority == "speed":
    use_tool = "SpiderSinglePageContactTool"
    params = {
        "extract_contacts": True,
        "include_links": False,
        "max_text_chars": 5000
    }
```

### 2. 超时控制

```python
import signal
from contextlib import contextmanager

@contextmanager
def timeout_handler(seconds):
    """超时处理器"""
    def timeout_signal(signum, frame):
        raise TimeoutError(f"操作超时（{seconds}秒）")
    
    signal.signal(signal.SIGALRM, timeout_signal)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

# 使用
try:
    with timeout_handler(90):
        result = crawl_tool._run(url=website_url, timeout=60.0)
except TimeoutError:
    print("深搜索超时，使用浅搜索结果")
    result = fallback_to_shallow()
```

### 3. 错误恢复

```python
def deep_search_with_fallback(shallow_result, crawl_tool, spider_tool):
    """带降级的深搜索"""
    
    # 尝试TavilySiteContactCrawlTool
    if shallow_result.website_url:
        try:
            result = crawl_website(
                shallow_result.website_url,
                shallow_result.company_name,
                crawl_tool
            )
            if result.search_status != "failed":
                return result
        except Exception as e:
            print(f"TavilySiteContactCrawlTool失败: {e}")
    
    # 降级到SpiderSinglePageContactTool
    if shallow_result.source_urls:
        for url in shallow_result.source_urls[:3]:  # 尝试前3个URL
            try:
                result = spider_page(url, shallow_result.company_name, spider_tool)
                if result.search_status != "failed":
                    return result
            except Exception as e:
                print(f"SpiderSinglePageContactTool失败: {e}")
                continue
    
    # 完全失败，返回浅搜索结果
    return DeepSearchResult(
        company_name=shallow_result.company_name,
        website_url=shallow_result.website_url or "",
        contacts=shallow_result.preliminary_contacts,
        search_status="partial"
    )
```

### 4. 结果验证

```python
def validate_deep_search_result(result):
    """验证深搜索结果"""
    
    # 检查状态
    if result.search_status == "failed":
        return False, "搜索失败"
    
    # 检查联系方式
    if not result.contacts:
        return False, "未找到任何联系方式"
    
    # 检查关键联系方式
    has_email = any(c.type == ContactType.EMAIL for c in result.contacts)
    has_phone = any(c.type == ContactType.PHONE for c in result.contacts)
    
    if not has_email and not has_phone:
        return False, "未找到邮箱或电话"
    
    # 检查置信度
    avg_confidence = sum(c.confidence for c in result.contacts) / len(result.contacts)
    if avg_confidence < 0.5:
        return False, "联系方式置信度过低"
    
    return True, "验证通过"
```

## 输出示例

### 成功案例

```python
DeepSearchResult(
    company_name="华为",
    website_url="https://www.huawei.com",
    contacts=[
        ContactItem(
            type=ContactType.EMAIL,
            value="contact@huawei.com",
            normalized="contact@huawei.com",
            source_url="https://www.huawei.com/contact",
            source_context="Contact us at contact@huawei.com for inquiries",
            confidence=0.95
        ),
        ContactItem(
            type=ContactType.PHONE,
            value="+86-755-12345678",
            normalized="+8675512345678",
            source_url="https://www.huawei.com/contact",
            confidence=0.9
        ),
        ContactItem(
            type=ContactType.LINKEDIN,
            value="https://www.linkedin.com/company/huawei",
            normalized="https://www.linkedin.com/company/huawei",
            source_url="https://www.huawei.com/about",
            confidence=0.85
        )
    ],
    candidate_links=[
        CandidateLink(
            url="https://www.huawei.com/support",
            role=LinkRole.OTHER,
            anchor_text="Support",
            source_url="https://www.huawei.com",
            is_external=False
        )
    ],
    page_evidence=[
        PageEvidence(
            page_url="https://www.huawei.com/contact",
            page_title="Contact Huawei",
            summary="Contact page with email and phone information",
            supports_fields=["email", "phone"],
            snippet="Contact us for more information...",
            contacts_found=2,
            links_found=15
        )
    ],
    missing_hints=["no_whatsapp"],
    search_status="success"
)
```

### 部分成功案例

```python
DeepSearchResult(
    company_name="Example Corp",
    website_url="https://example.com",
    contacts=[
        ContactItem(
            type=ContactType.EMAIL,
            value="info@example.com",
            normalized="info@example.com",
            source_url="https://example.com/contact",
            confidence=0.8
        )
    ],
    candidate_links=[],
    page_evidence=[],
    missing_hints=["no_phone", "no_whatsapp"],
    search_status="partial"
)
```

## 常见问题

### Q1: TavilySiteContactCrawlTool超时怎么办？

**A**: 减少爬取范围或使用SpiderSinglePageContactTool：
```python
# 方案1：减少爬取范围
result = crawl_tool._run(
    url=website_url,
    max_depth=1,  # 减少深度
    limit=10,     # 减少页面数
    timeout=30.0  # 减少超时时间
)

# 方案2：改用SpiderSinglePageContactTool
result = spider_tool._run(
    url=f"{website_url}/contact",
    extract_contacts=True
)
```

### Q2: 如何处理反爬虫机制？

**A**: 使用以下策略：
```python
# 1. 降低爬取速度
time.sleep(2)  # 在请求之间添加延迟

# 2. 使用SpiderSinglePageContactTool（更轻量）
result = spider_tool._run(url=page_url)

# 3. 尝试不同的入口页面
entry_pages = ["/contact", "/about", "/reach-us"]
for page in entry_pages:
    try:
        result = spider_tool._run(url=f"{website_url}{page}")
        if result.contacts:
            break
    except:
        continue
```

### Q3: 如何提取动态加载的内容？

**A**: TavilySiteContactCrawlTool支持JavaScript渲染：
```python
result = crawl_tool._run(
    url=website_url,
    extract_depth="advanced",  # 启用高级提取
    timeout=90.0  # 增加超时时间
)
```

### Q4: 如何处理多语言网站？

**A**: 指定语言偏好：
```python
# 尝试不同语言版本
language_paths = ["/en/contact", "/zh/contact", "/contact"]

for path in language_paths:
    result = spider_tool._run(url=f"{website_url}{path}")
    if result.contacts:
        break
```

## 下一步

深搜索完成后：

1. **验证结果**：检查联系方式的有效性
2. **补充搜索**：根据missing_hints决定是否需要额外搜索
3. **格式化输出**：生成用户友好的报告
4. **保存证据**：记录数据来源和置信度

详细的数据模型和工具参考请查看 [tools-reference.md](tools-reference.md)。
