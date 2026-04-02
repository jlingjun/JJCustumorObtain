"""
Contact Search Executor - 执行联系方式搜索的核心脚本

这个脚本实现了三阶段搜索流程：
1. 解析需求 - 理解用户意图，生成搜索查询
2. 浅层搜索 - 使用Tavily快速搜索
3. 深度搜索 - 对信息缺失的公司进行深度爬取
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set

from pydantic import BaseModel, Field


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


class SearchIntent(BaseModel):
    company_name: str
    industry: Optional[str] = None
    region: Optional[str] = None
    search_queries: List[str] = Field(default_factory=list)
    required_contact_types: List[ContactType] = Field(default_factory=lambda: [ContactType.EMAIL, ContactType.PHONE])
    priority: Literal["speed", "completeness"] = "completeness"


class ContactItem(BaseModel):
    type: ContactType
    value: str
    normalized: Optional[str] = None
    source_url: str
    source_context: Optional[str] = None
    confidence: float = 1.0


class ShallowSearchResult(BaseModel):
    company_name: str
    website_url: Optional[str] = None
    confidence_score: float = 0.0
    source_urls: List[str] = Field(default_factory=list)
    preliminary_contacts: List[ContactItem] = Field(default_factory=list)
    needs_deep_search: bool = True
    missing_info: List[str] = Field(default_factory=list)


class DeepSearchResult(BaseModel):
    company_name: str
    website_url: str
    contacts: List[ContactItem] = Field(default_factory=list)
    candidate_links: List[Dict[str, Any]] = Field(default_factory=list)
    page_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    missing_hints: List[str] = Field(default_factory=list)
    search_status: Literal["success", "partial", "failed"] = "partial"


class SearchSummary(BaseModel):
    total_companies: int
    successful: int
    partial: int
    failed: int
    total_contacts: int
    results: List[DeepSearchResult]


def parse_search_intent(
    user_input: str,
    companies: Optional[List[str]] = None,
    required_types: Optional[List[ContactType]] = None
) -> List[SearchIntent]:
    """
    Phase 1: 解析用户搜索意图
    
    Args:
        user_input: 用户的原始输入
        companies: 明确指定的公司列表（可选）
        required_types: 需要的联系方式类型（可选）
    
    Returns:
        SearchIntent列表，每个公司一个
    """
    intents = []
    
    if companies:
        company_list = companies
    else:
        company_list = extract_companies_from_input(user_input)
    
    for company in company_list:
        queries = generate_search_queries(company, user_input)
        
        intent = SearchIntent(
            company_name=company,
            search_queries=queries,
            required_contact_types=required_types or [ContactType.EMAIL, ContactType.PHONE],
            priority="completeness"
        )
        intents.append(intent)
    
    return intents


def extract_companies_from_input(user_input: str) -> List[str]:
    """
    从用户输入中提取公司名称
    
    简单实现：查找引号中的内容或特定模式
    """
    companies = []
    
    quoted = re.findall(r'["""]([^"""]+)["""]', user_input)
    companies.extend(quoted)
    
    patterns = [
        r'找(.+?)的联系方式',
        r'搜索(.+?)的',
        r'查询(.+?)公司',
        r'(.+?)公司',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, user_input)
        for match in matches:
            if match and len(match) < 50:
                companies.append(match.strip())
    
    if not companies:
        words = user_input.split()
        for word in words:
            if len(word) > 2 and not word in ['帮我', '搜索', '查找', '联系', '方式', '公司']:
                companies.append(word)
    
    return list(set(companies))[:5]


def generate_search_queries(company_name: str, context: str = "") -> List[str]:
    """
    为公司生成多样化的搜索查询
    """
    queries = []
    
    queries.append(f"{company_name} official website contact")
    queries.append(f"{company_name} 联系方式 邮箱 电话")
    queries.append(f"{company_name} contact information email phone")
    queries.append(f"site:linkedin.com {company_name} company")
    
    if "whatsapp" in context.lower() or "微信" in context:
        queries.append(f"{company_name} whatsapp contact")
    
    return queries


def execute_shallow_search(
    intents: List[SearchIntent],
    search_tool
) -> List[ShallowSearchResult]:
    """
    Phase 2: 执行浅层搜索
    
    Args:
        intents: 搜索意图列表
        search_tool: TavilySearchTool实例
    
    Returns:
        浅层搜索结果列表
    """
    results = []
    
    for intent in intents:
        company_results = []
        
        for query in intent.search_queries[:3]:
            try:
                search_result = search_tool._run(
                    query=query,
                    search_depth="basic",
                    max_results=5
                )
                
                if isinstance(search_result, str):
                    search_result = json.loads(search_result)
                
                company_results.append(search_result)
            except Exception as e:
                print(f"搜索查询失败: {query}, 错误: {e}")
        
        shallow_result = aggregate_shallow_results(
            intent.company_name,
            company_results,
            intent.required_contact_types
        )
        results.append(shallow_result)
    
    return results


def aggregate_shallow_results(
    company_name: str,
    search_results: List[Dict],
    required_types: List[ContactType]
) -> ShallowSearchResult:
    """
    聚合多个搜索查询的结果
    """
    website_url = None
    source_urls = []
    contacts = []
    confidence_score = 0.0
    
    for result in search_results:
        if isinstance(result, dict):
            results_list = result.get("results", [])
            
            for item in results_list:
                url = item.get("url", "")
                if url:
                    source_urls.append(url)
                    
                    if not website_url and is_official_website(url, company_name):
                        website_url = url
                        confidence_score = 0.8
                
                content = item.get("content", "")
                extracted = extract_contacts_from_text(content, url)
                contacts.extend(extracted)
    
    contacts = dedupe_contacts(contacts)
    
    missing_info = []
    found_types = {c.type for c in contacts}
    for req_type in required_types:
        if req_type not in found_types:
            missing_info.append(f"no_{req_type.value}")
    
    needs_deep_search = len(missing_info) > 0 or not website_url
    
    return ShallowSearchResult(
        company_name=company_name,
        website_url=website_url,
        confidence_score=confidence_score,
        source_urls=list(set(source_urls)),
        preliminary_contacts=contacts,
        needs_deep_search=needs_deep_search,
        missing_info=missing_info
    )


def is_official_website(url: str, company_name: str) -> bool:
    """
    判断URL是否为官方网站
    """
    url_lower = url.lower()
    company_lower = company_name.lower()
    
    company_words = re.findall(r'[a-z]+', company_lower)
    
    for word in company_words:
        if len(word) > 3 and word in url_lower:
            return True
    
    official_indicators = ['official', 'about', 'contact', 'company']
    if any(ind in url_lower for ind in official_indicators):
        return True
    
    return False


def extract_contacts_from_text(text: str, source_url: str) -> List[ContactItem]:
    """
    从文本中提取联系方式
    """
    contacts = []
    
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


def is_placeholder_email(email: str) -> bool:
    """
    判断是否为占位符邮箱
    """
    placeholders = ['example', 'test', 'your', 'email', 'domain.com', 'sentry.io']
    email_lower = email.lower()
    return any(p in email_lower for p in placeholders)


def normalize_phone(phone: str) -> str:
    """
    标准化电话号码
    """
    digits = re.sub(r'[^\d]', '', phone)
    if len(digits) >= 10:
        return f"+{digits}"
    return phone


def extract_whatsapp_number(wa_url: str) -> str:
    """
    从WhatsApp URL中提取号码
    """
    match = re.search(r'(\d{10,15})', wa_url)
    if match:
        return f"+{match.group(1)}"
    return wa_url


def dedupe_contacts(contacts: List[ContactItem]) -> List[ContactItem]:
    """
    去重联系方式
    """
    seen: Dict[tuple, ContactItem] = {}
    for contact in contacts:
        key = (contact.type, contact.normalized or contact.value)
        if key not in seen or contact.confidence > seen[key].confidence:
            seen[key] = contact
    return list(seen.values())


def execute_deep_search(
    shallow_results: List[ShallowSearchResult],
    crawl_tool,
    spider_tool=None
) -> List[DeepSearchResult]:
    """
    Phase 3: 执行深度搜索
    
    Args:
        shallow_results: 浅层搜索结果
        crawl_tool: TavilySiteContactCrawlTool实例
        spider_tool: SpiderSinglePageContactTool实例（可选）
    
    Returns:
        深度搜索结果列表
    """
    results = []
    
    for shallow in shallow_results:
        if not shallow.needs_deep_search:
            results.append(DeepSearchResult(
                company_name=shallow.company_name,
                website_url=shallow.website_url or "",
                contacts=shallow.preliminary_contacts,
                search_status="success" if shallow.preliminary_contacts else "partial"
            ))
            continue
        
        if shallow.website_url:
            result = crawl_single_site(shallow.company_name, shallow.website_url, crawl_tool)
        elif spider_tool and shallow.source_urls:
            result = spider_single_page(shallow.company_name, shallow.source_urls[0], spider_tool)
        else:
            result = DeepSearchResult(
                company_name=shallow.company_name,
                website_url="",
                search_status="failed",
                missing_hints=["no_website_found"]
            )
        
        results.append(result)
    
    return results


def crawl_single_site(
    company_name: str,
    website_url: str,
    crawl_tool
) -> DeepSearchResult:
    """
    使用TavilySiteContactCrawlTool爬取单个站点
    """
    try:
        result_json = crawl_tool._run(
            url=website_url,
            company_name=company_name,
            instruction_mode="contacts_and_summary",
            max_depth=2,
            limit=30,
            timeout=60.0
        )
        
        result = json.loads(result_json)
        
        contacts = []
        for c in result.get("contacts", []):
            contacts.append(ContactItem(
                type=ContactType(c.get("type", "other")),
                value=c.get("value", ""),
                normalized=c.get("normalized"),
                source_url=c.get("source_url", website_url),
                confidence=c.get("confidence", 0.8)
            ))
        
        return DeepSearchResult(
            company_name=company_name,
            website_url=website_url,
            contacts=contacts,
            candidate_links=result.get("candidate_links", []),
            page_evidence=result.get("page_evidence", []),
            missing_hints=result.get("missing_hints", []),
            search_status=result.get("status", "partial")
        )
    except Exception as e:
        return DeepSearchResult(
            company_name=company_name,
            website_url=website_url,
            search_status="failed",
            missing_hints=[f"crawl_error: {str(e)}"]
        )


def spider_single_page(
    company_name: str,
    page_url: str,
    spider_tool
) -> DeepSearchResult:
    """
    使用SpiderSinglePageContactTool抓取单个页面
    """
    try:
        result_json = spider_tool._run(
            url=page_url,
            company_name=company_name,
            extract_contacts=True,
            include_links=True
        )
        
        result = json.loads(result_json)
        
        contacts = []
        for c in result.get("contacts", []):
            contacts.append(ContactItem(
                type=ContactType(c.get("type", "other")),
                value=c.get("value", ""),
                normalized=c.get("normalized"),
                source_url=c.get("source_url", page_url),
                confidence=c.get("confidence", 0.8)
            ))
        
        return DeepSearchResult(
            company_name=company_name,
            website_url=page_url,
            contacts=contacts,
            candidate_links=result.get("candidate_links", []),
            page_evidence=result.get("page_evidence", []),
            missing_hints=result.get("missing_hints", []),
            search_status=result.get("status", "partial")
        )
    except Exception as e:
        return DeepSearchResult(
            company_name=company_name,
            website_url=page_url,
            search_status="failed",
            missing_hints=[f"spider_error: {str(e)}"]
        )


def generate_summary(results: List[DeepSearchResult]) -> SearchSummary:
    """
    生成搜索摘要
    """
    successful = sum(1 for r in results if r.search_status == "success")
    partial = sum(1 for r in results if r.search_status == "partial")
    failed = sum(1 for r in results if r.search_status == "failed")
    total_contacts = sum(len(r.contacts) for r in results)
    
    return SearchSummary(
        total_companies=len(results),
        successful=successful,
        partial=partial,
        failed=failed,
        total_contacts=total_contacts,
        results=results
    )


def run_full_search(
    user_input: str,
    search_tool,
    crawl_tool,
    spider_tool=None,
    companies: Optional[List[str]] = None
) -> SearchSummary:
    """
    执行完整的搜索流程
    
    Args:
        user_input: 用户输入
        search_tool: TavilySearchTool实例
        crawl_tool: TavilySiteContactCrawlTool实例
        spider_tool: SpiderSinglePageContactTool实例（可选）
        companies: 明确指定的公司列表（可选）
    
    Returns:
        搜索摘要
    """
    intents = parse_search_intent(user_input, companies)
    
    shallow_results = execute_shallow_search(intents, search_tool)
    
    deep_results = execute_deep_search(shallow_results, crawl_tool, spider_tool)
    
    summary = generate_summary(deep_results)
    
    return summary


if __name__ == "__main__":
    print("Contact Search Executor - 联系方式搜索执行器")
    print("请通过导入方式使用此模块")
