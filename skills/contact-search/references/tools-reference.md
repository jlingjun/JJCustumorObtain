# 工具参考文档（Tools Reference）

本文档提供三个核心工具的详细技术说明，包括参数、返回格式、使用示例和注意事项。

## 目录

1. [TavilySearchTool](#tavilysearchtool)
2. [TavilySiteContactCrawlTool](#tavilysitecontactcrawltool)
3. [SpiderSinglePageContactTool](#spidersinglepagecontacttool)
4. [共享数据模型](#共享数据模型)

---

## TavilySearchTool

### 概述

TavilySearchTool是CrewAI框架内置的网络搜索工具，基于Tavily搜索API。它提供快速、准确的网络搜索能力，适合浅搜索阶段使用。

### 基本信息

- **工具类型**: CrewAI内置工具
- **来源**: `crewai_tools` 包
- **API要求**: 需要TAVILY_API_KEY环境变量
- **主要用途**: 网络搜索，获取搜索结果列表

### 导入与实例化

```python
from crewai_tools import TavilySearchTool

# 实例化
search_tool = TavilySearchTool()
```

### 参数说明

#### 必需参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| `query` | str | 搜索查询字符串 |

#### 可选参数

| 参数名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `search_depth` | str | "basic" | 搜索深度："basic"或"advanced" |
| `max_results` | int | 5 | 返回的最大结果数 |
| `include_domains` | List[str] | [] | 限定搜索的域名列表 |
| `exclude_domains` | List[str] | [] | 排除的域名列表 |
| `include_raw_content` | bool | False | 是否包含原始HTML内容 |
| `include_images` | bool | False | 是否包含图片结果 |
| `include_answer` | bool | False | 是否包含AI生成的答案 |

### 参数详解

#### search_depth

- **"basic"**: 基础搜索
  - 速度快，适合初步探索
  - 返回摘要信息
  - API调用成本较低

- **"advanced"**: 高级搜索
  - 结果更全面
  - 包含更多上下文信息
  - API调用成本较高

**建议**:
- 浅搜索阶段使用"basic"
- 需要详细信息时使用"advanced"

#### max_results

控制返回的搜索结果数量。

**建议范围**: 3-10

```python
# 快速搜索
result = search_tool._run(query="example", max_results=3)

# 详细搜索
result = search_tool._run(query="example", max_results=10)
```

#### include_domains / exclude_domains

限定或排除特定域名。

```python
# 只搜索LinkedIn
result = search_tool._run(
    query="company name",
    include_domains=["linkedin.com"]
)

# 排除社交媒体
result = search_tool._run(
    query="company contact",
    exclude_domains=["facebook.com", "twitter.com", "instagram.com"]
)
```

### 返回格式

返回一个字典（或JSON字符串），包含以下字段：

```python
{
    "query": "搜索查询字符串",
    "follow_up_questions": None,
    "answer": "AI生成的答案（如果启用）",
    "images": [],  # 图片结果（如果启用）
    "results": [
        {
            "title": "页面标题",
            "url": "页面URL",
            "content": "页面内容摘要",
            "score": 0.95,  # Tavily相关性分数 (0-1)
            "raw_content": "原始HTML（如果启用）"
        },
        ...
    ],
    "response_time": 1.23  # 响应时间（秒）
}
```

### 使用示例

#### 基础搜索

```python
from crewai_tools import TavilySearchTool

search_tool = TavilySearchTool()

# 执行搜索
result = search_tool._run(
    query="华为 official website contact",
    search_depth="basic",
    max_results=5
)

# 解析结果
if isinstance(result, str):
    result = json.loads(result)

for item in result["results"]:
    print(f"标题: {item['title']}")
    print(f"URL: {item['url']}")
    print(f"内容: {item['content'][:100]}...")
    print(f"相关性: {item['score']}")
    print("-" * 50)
```

#### 高级搜索

```python
# 使用高级搜索深度
result = search_tool._run(
    query="Microsoft contact information",
    search_depth="advanced",
    max_results=10,
    include_raw_content=True
)
```

#### 域名限定搜索

```python
# 只搜索LinkedIn上的公司页面
result = search_tool._run(
    query="Huawei company",
    include_domains=["linkedin.com"],
    max_results=5
)
```

### 最佳实践

1. **查询优化**
```python
# 好的查询：具体且包含关键词
good_query = "华为 official website contact email phone"

# 不好的查询：过于宽泛
bad_query = "华为"
```

2. **结果处理**
```python
def process_search_results(result):
    """处理搜索结果"""
    if isinstance(result, str):
        result = json.loads(result)
    
    # 按相关性排序
    sorted_results = sorted(
        result["results"],
        key=lambda x: x["score"],
        reverse=True
    )
    
    # 过滤低相关性结果
    high_relevance = [
        r for r in sorted_results
        if r["score"] > 0.7
    ]
    
    return high_relevance
```

3. **错误处理**
```python
import time

def search_with_retry(query, max_retries=3):
    """带重试的搜索"""
    for attempt in range(max_retries):
        try:
            result = search_tool._run(query=query)
            return result
        except Exception as e:
            if "rate limit" in str(e).lower():
                wait_time = 2 ** attempt
                print(f"达到速率限制，等待{wait_time}秒...")
                time.sleep(wait_time)
            else:
                raise
    return None
```

### 注意事项

1. **API密钥**: 必须设置`TAVILY_API_KEY`环境变量
2. **速率限制**: Tavily有API调用速率限制，建议在批量搜索时添加延迟
3. **成本**: 每次API调用都有成本，建议合理设置`max_results`
4. **超时**: 网络问题可能导致超时，建议实现重试机制

---

## TavilySiteContactCrawlTool

### 概述

TavilySiteContactCrawlTool是自定义的站点级爬取工具，基于Tavily Crawl API。它能够自动发现网站的多个页面，并提取联系方式和公司信息。

### 基本信息

- **工具类型**: 自定义工具（cobtainflow项目）
- **来源**: `cobtainflow.tools.contact_discovery_tools`
- **API要求**: 需要TAVILY_API_KEY环境变量
- **主要用途**: 站点级爬取，多页面联系方式提取

### 导入与实例化

```python
from cobtainflow.tools.contact_discovery_tools import TavilySiteContactCrawlTool

# 实例化
crawl_tool = TavilySiteContactCrawlTool()
```

### 参数说明

#### 必需参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| `url` | str | 起始URL（网站入口） |

#### 可选参数

| 参数名 | 类型 | 默认值 | 范围 | 描述 |
|--------|------|--------|------|------|
| `company_name` | str | None | - | 公司名称（用于上下文） |
| `instruction_mode` | str | "contacts_and_summary" | - | 爬取指令模式 |
| `custom_instruction` | str | None | - | 自定义指令 |
| `max_depth` | int | 2 | 1-3 | 最大爬取深度 |
| `max_breadth` | int | 20 | 1-50 | 每层最大广度 |
| `limit` | int | 30 | 1-100 | 最大页面数 |
| `select_paths` | List[str] | [] | - | 包含的路径模式 |
| `exclude_paths` | List[str] | [] | - | 排除的路径模式 |
| `select_domains` | List[str] | [] | - | 包含的域名 |
| `exclude_domains` | List[str] | [] | - | 排除的域名 |
| `allow_external` | bool | False | - | 是否允许外部链接 |
| `extract_depth` | str | "basic" | - | 提取深度 |
| `output_format` | str | "markdown" | - | 输出格式 |
| `chunks_per_source` | int | 3 | 1-10 | 每个源的块数 |
| `include_favicon` | bool | False | - | 是否包含favicon |
| `include_usage` | bool | True | - | 是否包含使用信息 |
| `timeout` | float | 60.0 | 10.0-300.0 | 超时时间（秒） |

### 参数详解

#### instruction_mode

控制爬取的目标和策略。

- **"contacts_only"**: 只查找联系方式
  - 专注于contact、about、team页面
  - 速度较快
  - 适合只需要联系方式的场景

- **"contacts_and_summary"**: 查找联系方式和公司简介（推荐）
  - 同时提取联系方式和公司信息
  - 更全面
  - 适合需要了解公司背景的场景

- **"custom"**: 自定义指令
  - 使用`custom_instruction`参数指定具体需求
  - 最灵活

```python
# 只查找联系方式
result = crawl_tool._run(
    url="https://example.com",
    instruction_mode="contacts_only"
)

# 查找联系方式和简介
result = crawl_tool._run(
    url="https://example.com",
    instruction_mode="contacts_and_summary"
)

# 自定义指令
result = crawl_tool._run(
    url="https://example.com",
    instruction_mode="custom",
    custom_instruction="Find WhatsApp numbers and sales team email addresses"
)
```

#### max_depth

控制爬取的深度层级。

- **1**: 只爬取起始页面
- **2**: 爬取起始页面及其直接链接（推荐）
- **3**: 更深层的爬取，耗时更长

```python
# 快速爬取（只爬首页）
result = crawl_tool._run(url="https://example.com", max_depth=1)

# 标准爬取（推荐）
result = crawl_tool._run(url="https://example.com", max_depth=2)

# 深度爬取
result = crawl_tool._run(url="https://example.com", max_depth=3, limit=50)
```

#### limit

控制总共爬取的页面数。

**建议**:
- 快速搜索: 10-20页
- 标准搜索: 20-30页
- 深度搜索: 30-50页

#### select_paths / exclude_paths

限定或排除特定路径模式。

```python
# 只爬取联系相关页面
result = crawl_tool._run(
    url="https://example.com",
    select_paths=["/contact", "/about", "/team", "/support"]
)

# 排除博客和新闻页面
result = crawl_tool._run(
    url="https://example.com",
    exclude_paths=["/blog", "/news", "/article"]
)
```

#### extract_depth

控制内容提取的深度。

- **"basic"**: 基础提取
  - 提取主要文本内容
  - 速度较快

- **"advanced"**: 高级提取（推荐）
  - 支持JavaScript渲染
  - 提取动态加载的内容
  - 耗时较长

### 返回格式

返回`NormalizedContactExtractionResult`的JSON字符串：

```python
{
    "status": "success" | "partial" | "failed",
    "tool_name": "tavily_site_contact_crawl",
    "requested_url": "https://example.com",
    "resolved_url": "https://www.example.com",  # 重定向后的URL
    "contacts": [
        {
            "type": "email" | "phone" | "whatsapp" | "linkedin" | "twitter" | "facebook" | "instagram" | "contact_form" | "other",
            "value": "原始值",
            "normalized": "标准化后的值",
            "source_url": "来源页面URL",
            "source_context": "上下文文本",
            "confidence": 0.9  # 置信度 (0-1)
        }
    ],
    "candidate_links": [
        {
            "url": "链接URL",
            "role": "homepage" | "contact" | "about" | "team" | "footer" | "privacy" | "terms" | "social_profile" | "whatsapp_link" | "mailto_link" | "tel_link" | "other",
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
            "supports_fields": ["email", "phone"],  # 该页面支持的联系方式类型
            "snippet": "相关文本片段",
            "contacts_found": 3,  # 该页面找到的联系方式数量
            "links_found": 15  # 该页面找到的链接数量
        }
    ],
    "missing_hints": [
        "no_email",
        "no_phone",
        "no_whatsapp",
        "no_contact_form_found",
        "no_company_summary_found"
    ],
    "warnings": [
        {
            "code": "warning_code",
            "message": "警告信息",
            "context": {}
        }
    ],
    "raw_debug": {
        "tool": "TavilySiteContactCrawlTool",
        "start_time": 1234567890.123,
        "end_time": 1234567895.456,
        "duration_ms": 5333,
        "request_params": {...},
        "response_time": 1234567895.0,
        "request_id": "req_abc123",
        "usage": {
            "tokens": 1500
        },
        "raw_result_count": 10,
        "total_contacts": 5,
        "total_links": 30,
        "pages_analyzed": 10
    }
}
```

### 使用示例

#### 基础用法

```python
from cobtainflow.tools.contact_discovery_tools import TavilySiteContactCrawlTool
import json

crawl_tool = TavilySiteContactCrawlTool()

# 执行爬取
result_json = crawl_tool._run(
    url="https://example.com",
    company_name="Example Corp",
    instruction_mode="contacts_and_summary",
    max_depth=2,
    limit=30,
    timeout=60.0
)

# 解析结果
result = json.loads(result_json)

print(f"状态: {result['status']}")
print(f"找到的联系方式: {len(result['contacts'])}")
print(f"分析的页面: {len(result['page_evidence'])}")
print(f"缺失信息: {result['missing_hints']}")
```

#### 高级用法：限定路径

```python
# 只爬取联系相关页面
result = crawl_tool._run(
    url="https://example.com",
    instruction_mode="contacts_only",
    select_paths=["/contact", "/about", "/team", "/support", "/reach-us"],
    max_depth=2,
    limit=20,
    timeout=45.0
)
```

#### 高级用法：自定义指令

```python
# 查找特定类型的联系方式
result = crawl_tool._run(
    url="https://example.com",
    instruction_mode="custom",
    custom_instruction="Find WhatsApp contact numbers and business email addresses for sales inquiries",
    max_depth=2,
    limit=25
)
```

### 最佳实践

1. **参数组合**

```python
# 快速爬取（适合初步探索）
quick_params = {
    "max_depth": 1,
    "limit": 10,
    "timeout": 30.0
}

# 标准爬取（推荐）
standard_params = {
    "max_depth": 2,
    "limit": 30,
    "timeout": 60.0
}

# 深度爬取（适合需要完整信息的场景）
deep_params = {
    "max_depth": 3,
    "limit": 50,
    "timeout": 90.0
}
```

2. **结果处理**

```python
def process_crawl_result(result_json):
    """处理爬取结果"""
    result = json.loads(result_json)
    
    # 检查状态
    if result["status"] == "failed":
        print("爬取失败")
        return None
    
    # 提取联系方式
    contacts_by_type = {}
    for contact in result["contacts"]:
        contact_type = contact["type"]
        if contact_type not in contacts_by_type:
            contacts_by_type[contact_type] = []
        contacts_by_type[contact_type].append(contact)
    
    # 显示结果
    for contact_type, contacts in contacts_by_type.items():
        print(f"\n{contact_type.upper()}:")
        for c in contacts:
            print(f"  - {c['normalized']} (置信度: {c['confidence']})")
    
    # 显示缺失信息
    if result["missing_hints"]:
        print(f"\n缺失信息: {', '.join(result['missing_hints'])}")
    
    return contacts_by_type
```

3. **错误处理**

```python
def safe_crawl(url, company_name, max_retries=2):
    """安全的爬取，带重试"""
    for attempt in range(max_retries):
        try:
            result_json = crawl_tool._run(
                url=url,
                company_name=company_name,
                max_depth=2,
                limit=30,
                timeout=60.0
            )
            
            result = json.loads(result_json)
            
            if result["status"] != "failed":
                return result
            
        except Exception as e:
            print(f"爬取失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    return None
```

### 注意事项

1. **超时**: 爬取可能耗时较长，建议设置合理的timeout
2. **速率限制**: Tavily API有速率限制，批量爬取时添加延迟
3. **robots.txt**: 工具会遵守网站的robots.txt规则
4. **动态内容**: 使用`extract_depth="advanced"`提取JavaScript渲染的内容

---

## SpiderSinglePageContactTool

### 概述

SpiderSinglePageContactTool是自定义的单页面抓取工具，基于spider-rs库。它能够强制抓取单个页面，提取所有联系方式和链接。

### 基本信息

- **工具类型**: 自定义工具（cobtainflow项目）
- **来源**: `cobtainflow.tools.contact_discovery_tools`
- **依赖**: spider-rs库
- **主要用途**: 单页面深度抓取，提取隐藏的联系方式

### 导入与实例化

```python
from cobtainflow.tools.contact_discovery_tools import SpiderSinglePageContactTool

# 实例化
spider_tool = SpiderSinglePageContactTool()
```

### 参数说明

#### 必需参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| `url` | str | 要抓取的页面URL |

#### 可选参数

| 参数名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `company_name` | str | None | 公司名称（用于上下文） |
| `include_html` | bool | False | 是否包含原始HTML |
| `include_text` | bool | True | 是否包含提取的文本 |
| `include_links` | bool | True | 是否提取和分类链接 |
| `extract_contacts` | bool | True | 是否提取联系方式 |
| `max_text_chars` | int | 12000 | 最大文本字符数 |
| `max_links` | int | 200 | 最大链接数 |
| `classify_links` | bool | True | 是否分类链接 |

### 参数详解

#### include_html

是否在debug输出中包含原始HTML。

- **True**: 包含HTML（用于调试）
- **False**: 不包含HTML（默认，节省空间）

```python
# 调试模式
result = spider_tool._run(
    url="https://example.com/contact",
    include_html=True
)
```

#### include_links

是否提取页面上的所有链接并分类。

- **True**: 提取并分类链接（推荐）
- **False**: 不提取链接

```python
# 提取链接（可以发现更多候选页面）
result = spider_tool._run(
    url="https://example.com/contact",
    include_links=True
)
```

#### max_text_chars

限制提取的文本长度。

- 默认值: 12000字符
- 建议: 5000-20000之间

```python
# 快速抓取（限制文本长度）
result = spider_tool._run(
    url="https://example.com/contact",
    max_text_chars=5000
)

# 详细抓取（增加文本长度）
result = spider_tool._run(
    url="https://example.com/contact",
    max_text_chars=20000
)
```

### 返回格式

返回`NormalizedContactExtractionResult`的JSON字符串（格式与TavilySiteContactCrawlTool相同）。

### 使用示例

#### 基础用法

```python
from cobtainflow.tools.contact_discovery_tools import SpiderSinglePageContactTool
import json

spider_tool = SpiderSinglePageContactTool()

# 执行抓取
result_json = spider_tool._run(
    url="https://example.com/contact",
    company_name="Example Corp",
    extract_contacts=True,
    include_links=True
)

# 解析结果
result = json.loads(result_json)

print(f"状态: {result['status']}")
print(f"找到的联系方式: {len(result['contacts'])}")
print(f"找到的链接: {len(result['candidate_links'])}")
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

result = json.loads(result_json)

# 查看HTML样本
if "html_sample" in result["raw_debug"]:
    print("HTML样本:")
    print(result["raw_debug"]["html_sample"][:500])
```

#### 高级用法：快速抓取

```python
# 快速抓取（不提取链接）
result = spider_tool._run(
    url="https://example.com/contact",
    extract_contacts=True,
    include_links=False,
    max_text_chars=5000
)
```

### 最佳实践

1. **场景选择**

```python
# 场景1：已知具体联系页面
result = spider_tool._run(
    url="https://example.com/contact-us",
    extract_contacts=True,
    include_links=True
)

# 场景2：怀疑页面有隐藏联系方式
result = spider_tool._run(
    url="https://example.com/about",
    extract_contacts=True,
    include_html=True  # 启用调试
)

# 场景3：快速验证
result = spider_tool._run(
    url="https://example.com",
    extract_contacts=True,
    include_links=False,
    max_text_chars=5000
)
```

2. **结果处理**

```python
def process_spider_result(result_json):
    """处理Spider抓取结果"""
    result = json.loads(result_json)
    
    # 提取联系方式
    contacts = {}
    for contact in result["contacts"]:
        contact_type = contact["type"]
        if contact_type not in contacts:
            contacts[contact_type] = []
        contacts[contact_type].append({
            "value": contact["normalized"],
            "confidence": contact["confidence"],
            "source": contact["source_url"]
        })
    
    # 提取候选链接
    candidate_pages = []
    for link in result["candidate_links"]:
        if link["role"] in ["contact", "about", "team"]:
            candidate_pages.append(link["url"])
    
    return {
        "contacts": contacts,
        "candidate_pages": candidate_pages,
        "missing": result["missing_hints"]
    }
```

3. **链接发现**

```python
def discover_contact_pages(base_url):
    """通过首页发现联系页面"""
    result = spider_tool._run(
        url=base_url,
        extract_contacts=False,  # 不提取联系方式
        include_links=True  # 只提取链接
    )
    
    result = json.loads(result)
    
    # 筛选联系相关链接
    contact_links = [
        link["url"] for link in result["candidate_links"]
        if link["role"] in ["contact", "about", "team"]
    ]
    
    return contact_links
```

### 注意事项

1. **URL格式**: 必须是完整的URL（包含协议）
2. **页面可访问性**: 页面必须公开可访问
3. **JavaScript**: 不支持JavaScript渲染（使用TavilySiteContactCrawlTool处理动态内容）
4. **性能**: 单页面抓取速度较快，适合快速验证

---

## 共享数据模型

三个工具共享以下数据模型：

### ContactType 枚举

```python
class ContactType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    CONTACT_FORM = "contact_form"
    OTHER = "other"
```

### LinkRole 枚举

```python
class LinkRole(str, Enum):
    HOMEPAGE = "homepage"
    CONTACT = "contact"
    ABOUT = "about"
    TEAM = "team"
    FOOTER = "footer"
    PRIVACY = "privacy"
    TERMS = "terms"
    SOCIAL_PROFILE = "social_profile"
    WHATSAPP_LINK = "whatsapp_link"
    MAILTO_LINK = "mailto_link"
    TEL_LINK = "tel_link"
    OTHER = "other"
```

### ContactItem

```python
class ContactItem(BaseModel):
    type: ContactType
    value: str
    normalized: Optional[str]
    source_url: str
    source_context: Optional[str]
    confidence: float  # 0.0-1.0
```

### CandidateLink

```python
class CandidateLink(BaseModel):
    url: str
    role: LinkRole
    anchor_text: Optional[str]
    source_url: str
    is_external: bool
```

### PageEvidence

```python
class PageEvidence(BaseModel):
    page_url: str
    page_title: Optional[str]
    summary: Optional[str]
    supports_fields: List[str]
    snippet: Optional[str]
    contacts_found: int
    links_found: int
```

### NormalizedContactExtractionResult

```python
class NormalizedContactExtractionResult(BaseModel):
    status: Literal["success", "partial", "failed"]
    tool_name: str
    requested_url: str
    resolved_url: Optional[str]
    contacts: List[ContactItem]
    candidate_links: List[CandidateLink]
    page_evidence: List[PageEvidence]
    missing_hints: List[str]
    warnings: List[ToolWarning]
    raw_debug: Dict[str, Any]
```

---

## 工具对比

| 特性 | TavilySearchTool | TavilySiteContactCrawlTool | SpiderSinglePageContactTool |
|------|------------------|---------------------------|----------------------------|
| **用途** | 网络搜索 | 站点级爬取 | 单页面抓取 |
| **输入** | 搜索查询 | 网站URL | 页面URL |
| **输出** | 搜索结果列表 | 联系方式+证据 | 联系方式+证据 |
| **速度** | 快 | 中等 | 快 |
| **深度** | 浅 | 深 | 中 |
| **适用场景** | 浅搜索 | 深搜索（有官网） | 深搜索（有具体页面） |
| **API要求** | TAVILY_API_KEY | TAVILY_API_KEY | 无 |
| **JS渲染** | 否 | 是 | 否 |

---

## 常见问题

### Q1: 如何选择合适的工具？

**A**: 根据已知信息和需求选择：

```python
if not known_url:
    # 不知道任何URL，使用TavilySearchTool
    tool = "TavilySearchTool"
elif known_website_url:
    # 知道官网，使用TavilySiteContactCrawlTool
    tool = "TavilySiteContactCrawlTool"
elif known_page_url:
    # 知道具体页面，使用SpiderSinglePageContactTool
    tool = "SpiderSinglePageContactTool"
```

### Q2: 如何处理工具返回的JSON字符串？

**A**: 使用json.loads解析：

```python
import json

result_dict = json.loads(result_json)

# 访问字段
status = result_dict["status"]
contacts = result_dict["contacts"]
```

### Q3: 如何验证联系方式的有效性？

**A**: 使用confidence字段和正则表达式。**重要：系统默认过滤置信度<0.7的联系方式**。

```python
# 置信度过滤阈值
MIN_CONFIDENCE = 0.7

def validate_contact(contact):
    """验证联系方式"""
    # 检查置信度（必须在0.7以上）
    if contact["confidence"] < MIN_CONFIDENCE:
        return False
    
    # 根据类型验证
    if contact["type"] == "email":
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, contact["normalized"]))
    
    elif contact["type"] == "phone":
        # 检查是否为有效的国际号码格式
        return contact["normalized"].startswith("+")
    
    return True

def filter_contacts_by_confidence(contacts):
    """过滤低置信度的联系方式"""
    return [c for c in contacts if c["confidence"] >= MIN_CONFIDENCE]
```

**置信度说明**：
- **0.9-1.0**: 极高置信度，来自mailto:链接、tel:链接、官方联系页面
- **0.8-0.9**: 高置信度，来自官方网站、LinkedIn等权威来源
- **0.7-0.8**: 中等置信度，来自可靠的第三方网站
- **<0.7**: 低置信度，已被系统自动过滤

### Q4: 如何处理missing_hints？

**A**: 根据缺失信息决定下一步行动：

```python
def handle_missing_info(result):
    """处理缺失信息"""
    missing = result["missing_hints"]
    
    if "no_email" in missing:
        # 尝试查找邮箱
        print("未找到邮箱，尝试其他方法...")
    
    if "no_phone" in missing:
        # 尝试查找电话
        print("未找到电话，尝试其他方法...")
    
    if "no_whatsapp" in missing:
        # WhatsApp不是必需的，可以忽略
        pass
```

---

## 更新日志

- **v1.0** (2026-04-01): 初始版本，包含三个核心工具的完整文档
