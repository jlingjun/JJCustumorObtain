# 浅搜索（Shallow Search）实现指南

## 概述

浅搜索是搜索流程的第二层第一阶段，主要用于广泛收集信息，快速获取初步结果。当不知道公司官网或需要了解行业提供商时，浅搜索是最佳起点。

## 核心工具

### TavilySearchTool

**工具类型**：CrewAI内置工具

**导入方式**：
```python
from crewai_tools import TavilySearchTool
```

**实例化**：
```python
search_tool = TavilySearchTool()
```

## 工具参数详解

### 必需参数

- **query** (str): 搜索查询字符串
  - 这是用户想要搜索的内容
  - 应该是经过需求解析后生成的多样化查询之一

### 可选参数

- **search_depth** (str): 搜索深度
  - `"basic"`: 基础搜索，速度快，适合初步探索
  - `"advanced"`: 高级搜索，结果更全面，但速度较慢
  - 默认值: `"basic"`

- **max_results** (int): 最大结果数
  - 控制返回的搜索结果数量
  - 默认值: 5
  - 建议范围: 3-10

- **include_domains** (List[str]): 包含的域名列表
  - 限定搜索结果只来自特定域名
  - 示例: `["linkedin.com", "crunchbase.com"]`

- **exclude_domains** (List[str]): 排除的域名列表
  - 排除特定域名的搜索结果
  - 示例: `["facebook.com", "twitter.com"]`

- **include_raw_content** (bool): 是否包含原始内容
  - 是否返回页面的原始HTML内容
  - 默认值: False

- **include_images** (bool): 是否包含图片
  - 是否在结果中包含相关图片
  - 默认值: False

## 返回格式

TavilySearchTool返回一个字典（或JSON字符串），包含以下字段：

```python
{
    "query": "搜索查询",
    "results": [
        {
            "title": "页面标题",
            "url": "页面URL",
            "content": "页面内容摘要",
            "score": 0.95,  # 相关性分数
            "raw_content": "原始内容（如果启用）"
        },
        ...
    ]
}
```

## 执行流程

### Step 1: 执行搜索查询

根据需求解析阶段生成的查询列表，逐个执行搜索：

```python
def execute_shallow_search(search_intent, search_tool):
    """
    执行浅搜索
    
    Args:
        search_intent: 需求解析阶段生成的SearchIntent对象
        search_tool: TavilySearchTool实例
    
    Returns:
        浅搜索结果列表
    """
    all_results = []
    
    # 执行前3-5个查询（避免过多API调用）
    for query in search_intent.search_queries[:5]:
        try:
            result = search_tool._run(
                query=query,
                search_depth="basic",
                max_results=5
            )
            
            # 如果返回的是字符串，解析为字典
            if isinstance(result, str):
                result = json.loads(result)
            
            all_results.append(result)
            
        except Exception as e:
            print(f"搜索查询失败: {query}, 错误: {e}")
            continue
    
    return all_results
```

### Step 2: 评估结果相关性

对每个搜索结果进行相关性评估：

```python
def evaluate_relevance(search_result, company_name):
    """
    评估搜索结果的相关性
    
    Args:
        search_result: 单个搜索结果
        company_name: 公司名称
    
    Returns:
        相关性分数 (0.0-1.0)
    """
    url = search_result.get("url", "").lower()
    title = search_result.get("title", "").lower()
    content = search_result.get("content", "").lower()
    
    score = 0.0
    
    # 1. 检查URL是否包含公司名
    company_words = extract_company_words(company_name)
    for word in company_words:
        if len(word) > 3 and word in url:
            score += 0.3
            break
    
    # 2. 检查是否为官方网站
    official_indicators = ['official', 'about', 'contact', 'company']
    if any(ind in url for ind in official_indicators):
        score += 0.2
    
    # 3. 检查是否包含联系方式关键词
    contact_keywords = ['contact', 'email', 'phone', 'whatsapp', 'linkedin']
    if any(kw in content for kw in contact_keywords):
        score += 0.2
    
    # 4. 检查是否来自权威来源
    authoritative_domains = ['linkedin.com', 'crunchbase.com', 'bloomberg.com']
    if any(domain in url for domain in authoritative_domains):
        score += 0.1
    
    # 5. 使用Tavily提供的相关性分数
    tavily_score = search_result.get("score", 0)
    score += tavily_score * 0.2
    
    return min(score, 1.0)
```

### Step 3: 去重与格式化

合并多个查询的结果，去除重复项：

```python
def deduplicate_and_format(all_search_results, company_name):
    """
    去重并格式化搜索结果
    
    Args:
        all_search_results: 所有搜索查询的结果列表
        company_name: 公司名称
    
    Returns:
        ShallowSearchResult对象
    """
    seen_urls = set()
    unique_results = []
    website_url = None
    contacts = []
    
    for search_response in all_search_results:
        results = search_response.get("results", [])
        
        for result in results:
            url = result.get("url", "")
            
            # 去重
            if url.lower() in seen_urls:
                continue
            seen_urls.add(url.lower())
            
            # 评估相关性
            relevance = evaluate_relevance(result, company_name)
            
            # 识别官网
            if not website_url and is_official_website(url, company_name):
                website_url = url
            
            # 提取初步联系方式
            content = result.get("content", "")
            extracted_contacts = extract_contacts_from_text(content, url)
            contacts.extend(extracted_contacts)
            
            unique_results.append({
                "url": url,
                "title": result.get("title"),
                "content": content,
                "relevance": relevance
            })
    
    # 去重联系方式
    contacts = dedupe_contacts(contacts)
    
    # 置信度过滤：只保留置信度>=0.7的联系方式
    MIN_CONFIDENCE = 0.7
    contacts = [c for c in contacts if c.confidence >= MIN_CONFIDENCE]
    
    # 判断是否需要深搜索
    needs_deep_search = (
        not website_url or
        not any(c.type == ContactType.EMAIL for c in contacts) or
        not any(c.type == ContactType.PHONE for c in contacts)
    )
    
    # 识别缺失信息
    missing_info = []
    found_types = {c.type for c in contacts}
    required_types = [ContactType.EMAIL, ContactType.PHONE]
    for req_type in required_types:
        if req_type not in found_types:
            missing_info.append(f"no_{req_type.value}")
    
    return ShallowSearchResult(
        company_name=company_name,
        website_url=website_url,
        confidence_score=calculate_confidence(unique_results, contacts),
        source_urls=[r["url"] for r in unique_results],
        preliminary_contacts=contacts,
        needs_deep_search=needs_deep_search,
        missing_info=missing_info
    )
```

## 辅助函数

### 判断是否为官方网站

```python
def is_official_website(url, company_name):
    """
    判断URL是否为公司的官方网站
    
    Args:
        url: 页面URL
        company_name: 公司名称
    
    Returns:
        bool: 是否为官方网站
    """
    url_lower = url.lower()
    company_lower = company_name.lower()
    
    # 提取公司名中的关键词
    company_words = re.findall(r'[a-z]+', company_lower)
    
    # 检查域名是否包含公司关键词
    for word in company_words:
        if len(word) > 3 and word in url_lower:
            # 排除社交媒体
            social_domains = ['linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com']
            if not any(social in url_lower for social in social_domains):
                return True
    
    # 检查是否为官方页面
    official_paths = ['/about', '/contact', '/company', '/official']
    if any(path in url_lower for path in official_paths):
        return True
    
    return False
```

### 从文本中提取联系方式

```python
def extract_contacts_from_text(text, source_url):
    """
    从文本中提取联系方式
    
    Args:
        text: 文本内容
        source_url: 来源URL
    
    Returns:
        ContactItem列表
    """
    contacts = []
    
    # 提取邮箱
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    for match in email_pattern.finditer(text):
        email = match.group(0)
        if not is_placeholder_email(email):
            contacts.append(ContactItem(
                type=ContactType.EMAIL,
                value=email,
                normalized=email.lower(),
                source_url=source_url,
                confidence=0.8
            ))
    
    # 提取电话
    phone_pattern = re.compile(r'\+?\d{10,15}')
    for match in phone_pattern.finditer(text):
        phone = match.group(0)
        contacts.append(ContactItem(
            type=ContactType.PHONE,
            value=phone,
            normalized=normalize_phone(phone),
            source_url=source_url,
            confidence=0.7
        ))
    
    # 提取WhatsApp
    wa_pattern = re.compile(r'wa\.me/\d+|api\.whatsapp\.com/send\?phone=\d+')
    for match in wa_pattern.finditer(text):
        wa_url = match.group(0)
        contacts.append(ContactItem(
            type=ContactType.WHATSAPP,
            value=wa_url,
            normalized=extract_whatsapp_number(wa_url),
            source_url=source_url,
            confidence=0.9
        ))
    
    return contacts
```

## 最佳实践

### 1. 查询优化

**多角度覆盖**：
```python
# 不要只使用单一查询
bad_queries = ["华为"]

# 应该使用多样化查询
good_queries = [
    "华为 official website contact",
    "华为 联系方式 邮箱 电话",
    "Huawei contact information email phone",
    "site:linkedin.com 华为 Huawei company"
]
```

**地域限定**：
```python
# 对于地区性搜索，包含地域关键词
queries = [
    "尼日利亚太阳能冰箱提供商",
    "Nigeria solar refrigerator suppliers",
    "Lagos solar freezer suppliers"
]
```

### 2. 结果过滤

**优先级排序**：
```python
# 按相关性排序结果
sorted_results = sorted(
    unique_results,
    key=lambda x: x["relevance"],
    reverse=True
)

# 只保留高相关性结果
high_relevance_results = [
    r for r in sorted_results
    if r["relevance"] > 0.5
]
```

### 3. 错误处理

**API限制**：
```python
import time

def execute_with_retry(query, search_tool, max_retries=3):
    """带重试的搜索执行"""
    for attempt in range(max_retries):
        try:
            result = search_tool._run(query=query)
            return result
        except Exception as e:
            if "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)  # 指数退避
            else:
                raise
    return None
```

### 4. 性能优化

**并行搜索**：
```python
import concurrent.futures

def parallel_search(queries, search_tool, max_workers=3):
    """并行执行多个搜索查询"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(search_tool._run, query): query
            for query in queries
        }
        results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"搜索失败: {e}")
        return results
```

## 输出示例

```python
ShallowSearchResult(
    company_name="华为",
    website_url="https://www.huawei.com",
    confidence_score=0.85,
    source_urls=[
        "https://www.huawei.com/contact",
        "https://www.linkedin.com/company/huawei",
        "https://www.huawei.com/about"
    ],
    preliminary_contacts=[
        ContactItem(
            type=ContactType.EMAIL,
            value="contact@huawei.com",
            normalized="contact@huawei.com",
            source_url="https://www.huawei.com/contact",
            confidence=0.9
        ),
        ContactItem(
            type=ContactType.PHONE,
            value="+86-755-12345678",
            normalized="+8675512345678",
            source_url="https://www.huawei.com/contact",
            confidence=0.8
        )
    ],
    needs_deep_search=False,
    missing_info=["no_whatsapp"]
)
```

## 常见问题

### Q1: 搜索结果太多，如何筛选？

**A**: 使用相关性评估和域名过滤：
```python
# 只保留高相关性结果
high_relevance = [r for r in results if r["relevance"] > 0.6]

# 排除低质量域名
exclude_domains = ["pinterest.com", "reddit.com", "quora.com"]
filtered = [r for r in results if not any(d in r["url"] for d in exclude_domains)]
```

### Q2: 如何判断是否需要深搜索？

**A**: 根据以下条件判断：
```python
needs_deep_search = (
    # 没有找到官网
    not website_url or
    # 缺少关键联系方式
    not any(c.type == ContactType.EMAIL for c in contacts) or
    # 用户明确要求完整信息
    search_intent.priority == "completeness"
)
```

### Q3: 如何处理多语言查询？

**A**: 为每种语言生成查询：
```python
def generate_multilingual_queries(company_name, languages=["en", "zh"]):
    queries = []
    for lang in languages:
        if lang == "en":
            queries.append(f"{company_name} contact information")
        elif lang == "zh":
            queries.append(f"{company_name} 联系方式")
    return queries
```

## 下一步

浅搜索完成后，根据结果决定是否需要进行深搜索：

- 如果 `needs_deep_search=True`，请参考 [deep-search.md](deep-search.md)
- 如果已找到完整联系方式，可以直接返回结果
