"""
Contact Discovery Tools for CrewAI-based Lead Search System.

This module provides two custom tools for contact discovery:
1. SpiderSinglePageContactTool - Single page scraping with spider-rs
2. TavilySiteContactCrawlTool - Site-wide crawling with Tavily

Both tools return NormalizedContactExtractionResult as JSON string.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Dict, List, Literal, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

from pydantic import BaseModel, Field
from crewai.tools import BaseTool, EnvVar

try:
    from spider_rs import Page
    SPIDER_RS_AVAILABLE = True
except ImportError:
    SPIDER_RS_AVAILABLE = False

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
## delete this after test
from dotenv import load_dotenv

import os

load_dotenv()

# ==============================================================================
# SHARED DATA MODELS
# ==============================================================================

class ContactType(str, Enum):
    """Types of contact information."""
    EMAIL = "email"
    PHONE = "phone"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    CONTACT_FORM = "contact_form"
    OTHER = "other"


class LinkRole(str, Enum):
    """Classification of URL roles."""
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


class ToolWarning(BaseModel):
    """Warning message from tool execution."""
    code: str = Field(..., description="Warning code for programmatic handling")
    message: str = Field(..., description="Human-readable warning message")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


class ContactItem(BaseModel):
    """A single contact information item."""
    type: ContactType = Field(..., description="Type of contact")
    value: str = Field(..., description="Raw contact value")
    normalized: Optional[str] = Field(default=None, description="Normalized/cleaned value")
    source_url: str = Field(..., description="URL where contact was found")
    source_context: Optional[str] = Field(default=None, description="Surrounding text context")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")


class CandidateLink(BaseModel):
    """A candidate link discovered during crawling."""
    url: str = Field(..., description="Absolute URL")
    role: LinkRole = Field(default=LinkRole.OTHER, description="Classified role of the link")
    anchor_text: Optional[str] = Field(default=None, description="Link anchor text")
    source_url: str = Field(..., description="URL where link was found")
    is_external: bool = Field(default=False, description="Whether link is external")


class PageEvidence(BaseModel):
    """Evidence collected from a single page."""
    page_url: str = Field(..., description="URL of the page")
    page_title: Optional[str] = Field(default=None, description="Page title")
    summary: Optional[str] = Field(default=None, description="Brief page summary")
    supports_fields: List[str] = Field(default_factory=list, description="Fields found on page")
    snippet: Optional[str] = Field(default=None, description="Relevant text snippet")
    contacts_found: int = Field(default=0, description="Number of contacts found on page")
    links_found: int = Field(default=0, description="Number of links found on page")


class NormalizedContactExtractionResult(BaseModel):
    """Unified result format for contact discovery tools."""
    status: Literal["success", "partial", "failed"] = Field(..., description="Execution status")
    tool_name: str = Field(..., description="Name of the tool that produced this result")
    requested_url: str = Field(..., description="Original URL requested")
    resolved_url: Optional[str] = Field(default=None, description="Final URL after redirects")
    contacts: List[ContactItem] = Field(default_factory=list, description="Extracted contacts")
    candidate_links: List[CandidateLink] = Field(default_factory=list, description="Discovered links")
    page_evidence: List[PageEvidence] = Field(default_factory=list, description="Per-page evidence")
    missing_hints: List[str] = Field(default_factory=list, description="Hints about missing data")
    warnings: List[ToolWarning] = Field(default_factory=list, description="Warning messages")
    raw_debug: Dict[str, Any] = Field(default_factory=dict, description="Debug information")


# ==============================================================================
# HELPER FUNCTIONS - Normalization
# ==============================================================================

def normalize_email(email: str) -> Optional[str]:
    """
    Normalize an email address.
    
    - Lowercase
    - Remove trailing dots
    - Remove mailto: prefix if present
    - Validate basic format
    """
    if not email:
        return None
    
    email = email.strip().lower()
    email = re.sub(r'^mailto:', '', email, flags=re.IGNORECASE)
    email = email.rstrip('.')
    
    if not re.match(r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$', email):
        return None
    
    return email


def normalize_phone(phone: str) -> Optional[str]:
    """
    Normalize a phone number to E.164-like format.
    
    - Remove tel: prefix
    - Keep only digits and leading +
    - Handle common formats
    """
    if not phone:
        return None
    
    phone = phone.strip()
    phone = re.sub(r'^tel:', '', phone, flags=re.IGNORECASE)
    phone = re.sub(r'^tel://', '', phone, flags=re.IGNORECASE)
    
    has_plus = phone.startswith('+')
    digits = re.sub(r'[^\d]', '', phone)
    
    if not digits:
        return None
    
    if len(digits) < 7 or len(digits) > 15:
        return None
    
    if has_plus or len(digits) > 10:
        return f"+{digits}"
    
    return digits


def normalize_whatsapp(value: str) -> Optional[str]:
    """
    Normalize a WhatsApp contact.
    
    Accepts:
    - wa.me/1234567890
    - api.whatsapp.com/send?phone=1234567890
    - Raw phone numbers
    """
    if not value:
        return None
    
    value = value.strip()
    
    wa_me_match = re.search(r'wa\.me/(\d+)', value, re.IGNORECASE)
    if wa_me_match:
        return f"+{wa_me_match.group(1)}"
    
    api_match = re.search(r'api\.whatsapp\.com/send\?phone=(\d+)', value, re.IGNORECASE)
    if api_match:
        return f"+{api_match.group(1)}"
    
    phone_match = re.search(r'phone=(\d+)', value, re.IGNORECASE)
    if phone_match:
        return f"+{phone_match.group(1)}"
    
    digits = re.sub(r'[^\d]', '', value)
    if digits and 7 <= len(digits) <= 15:
        return f"+{digits}"
    
    return None


# ==============================================================================
# HELPER FUNCTIONS - Extraction
# ==============================================================================

EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE
)

PHONE_PATTERNS = [
    re.compile(r'\+?\d{1,3}[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}'),
    re.compile(r'\+?\d{10,15}'),
    re.compile(r'\b\d{3}[\s.-]\d{3}[\s.-]\d{4}\b'),
]

WHATSAPP_PATTERNS = [
    re.compile(r'https?://wa\.me/\d+', re.IGNORECASE),
    re.compile(r'https?://api\.whatsapp\.com/send\?phone=\d+', re.IGNORECASE),
    re.compile(r'whatsapp://send\?phone=\d+', re.IGNORECASE),
]

LINKEDIN_PATTERNS = [
    re.compile(r'https?://(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9_-]+', re.IGNORECASE),
]

SOCIAL_PATTERNS = {
    'twitter': re.compile(r'https?://(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9_]+', re.IGNORECASE),
    'facebook': re.compile(r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9.]+', re.IGNORECASE),
    'instagram': re.compile(r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+', re.IGNORECASE),
}

CONTACT_FORM_INDICATORS = [
    re.compile(r'<form[^>]*(?:contact|inquiry|submit)[^>]*>', re.IGNORECASE),
    re.compile(r'<form[^>]*action=["\'][^"\']*contact', re.IGNORECASE),
    re.compile(r'<input[^>]*type=["\']submit["\'][^>]*>', re.IGNORECASE),
]

COMMON_EMAIL_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com',
    'aol.com', 'mail.com', 'protonmail.com', 'icloud.com',
}


def extract_emails_from_text(text: str, source_url: str = "") -> List[ContactItem]:
    """
    Extract email addresses from text content.
    
    Filters out common false positives like:
    - Image file extensions (.png, .jpg, etc.)
    - Common placeholder emails
    """
    if not text:
        return []
    
    contacts = []
    seen: Set[str] = set()
    
    for match in EMAIL_PATTERN.finditer(text):
        email = match.group(0)
        normalized = normalize_email(email)
        
        if not normalized:
            continue
        
        if normalized in seen:
            continue
        
        local, domain = normalized.rsplit('@', 1)
        
        if local.lower() in {'example', 'test', 'email', 'your-email', 'youremail', 'your'}:
            continue
        
        if domain.lower() in {'example.com', 'test.com', 'domain.com', 'sentry.io', 'wixpress.com'}:
            continue
        
        if any(local.lower().startswith(prefix) for prefix in ['your-', 'my-', 'enter-']):
            continue
        
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        context = text[start:end].strip()
        
        contacts.append(ContactItem(
            type=ContactType.EMAIL,
            value=email,
            normalized=normalized,
            source_url=source_url,
            source_context=context,
            confidence=0.9 if domain.lower() not in COMMON_EMAIL_DOMAINS else 0.7
        ))
        seen.add(normalized)
    
    return contacts


def extract_phones_from_text(text: str, source_url: str = "") -> List[ContactItem]:
    """
    Extract phone numbers from text content.
    """
    if not text:
        return []
    
    contacts = []
    seen: Set[str] = set()
    
    for pattern in PHONE_PATTERNS:
        for match in pattern.finditer(text):
            phone = match.group(0)
            normalized = normalize_phone(phone)
            
            if not normalized:
                continue
            
            if normalized in seen:
                continue
            
            if re.match(r'^\+?1{7,}$', normalized):
                continue
            
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()
            
            contacts.append(ContactItem(
                type=ContactType.PHONE,
                value=phone,
                normalized=normalized,
                source_url=source_url,
                source_context=context,
                confidence=0.8
            ))
            seen.add(normalized)
    
    return contacts


def extract_contact_links_from_html(html: str, source_url: str = "") -> Tuple[List[ContactItem], List[CandidateLink]]:
    """
    Extract contact-related links from HTML content.
    
    Returns tuple of (contacts, candidate_links).
    """
    if not html:
        return [], []
    
    contacts = []
    candidate_links = []
    seen_contacts: Set[Tuple[ContactType, str]] = set()
    seen_links: Set[str] = set()
    
    mailto_pattern = re.compile(r'href=["\']mailto:([^"\']+)["\']', re.IGNORECASE)
    for match in mailto_pattern.finditer(html):
        email = match.group(1)
        normalized = normalize_email(email)
        if normalized and (ContactType.EMAIL, normalized) not in seen_contacts:
            contacts.append(ContactItem(
                type=ContactType.EMAIL,
                value=email,
                normalized=normalized,
                source_url=source_url,
                confidence=0.95
            ))
            seen_contacts.add((ContactType.EMAIL, normalized))
    
    tel_pattern = re.compile(r'href=["\']tel:([^"\']+)["\']', re.IGNORECASE)
    for match in tel_pattern.finditer(html):
        phone = match.group(1)
        normalized = normalize_phone(phone)
        if normalized and (ContactType.PHONE, normalized) not in seen_contacts:
            contacts.append(ContactItem(
                type=ContactType.PHONE,
                value=phone,
                normalized=normalized,
                source_url=source_url,
                confidence=0.95
            ))
            seen_contacts.add((ContactType.PHONE, normalized))
    
    for pattern in WHATSAPP_PATTERNS:
        for match in pattern.finditer(html):
            wa_url = match.group(0)
            normalized = normalize_whatsapp(wa_url)
            if normalized and (ContactType.WHATSAPP, normalized) not in seen_contacts:
                contacts.append(ContactItem(
                    type=ContactType.WHATSAPP,
                    value=wa_url,
                    normalized=normalized,
                    source_url=source_url,
                    confidence=0.95
                ))
                seen_contacts.add((ContactType.WHATSAPP, normalized))
    
    for pattern in LINKEDIN_PATTERNS:
        for match in pattern.finditer(html):
            linkedin_url = match.group(0)
            if (ContactType.LINKEDIN, linkedin_url.lower()) not in seen_contacts:
                contacts.append(ContactItem(
                    type=ContactType.LINKEDIN,
                    value=linkedin_url,
                    normalized=linkedin_url,
                    source_url=source_url,
                    confidence=0.9
                ))
                seen_contacts.add((ContactType.LINKEDIN, linkedin_url.lower()))
    
    for social_type, pattern in SOCIAL_PATTERNS.items():
        for match in pattern.finditer(html):
            social_url = match.group(0)
            contact_type = ContactType(social_type)
            if (contact_type, social_url.lower()) not in seen_contacts:
                contacts.append(ContactItem(
                    type=contact_type,
                    value=social_url,
                    normalized=social_url,
                    source_url=source_url,
                    confidence=0.85
                ))
                seen_contacts.add((contact_type, social_url.lower()))
    
    href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    anchor_pattern = re.compile(r'>([^<]*)</a>', re.IGNORECASE)
    
    for i, match in enumerate(href_pattern.finditer(html)):
        href = match.group(1)
        
        if href.startswith(('mailto:', 'tel:', 'javascript:', '#', 'data:')):
            continue
        
        absolute_url = urljoin(source_url, href)
        
        if absolute_url.lower() in seen_links:
            continue
        seen_links.add(absolute_url.lower())
        
        anchor_text = None
        remaining = html[match.end():]
        anchor_match = anchor_pattern.search(remaining[:200])
        if anchor_match:
            anchor_text = anchor_match.group(1).strip()[:100]
        
        is_external = urlparse(absolute_url).netloc != urlparse(source_url).netloc
        role = classify_url_role(absolute_url, anchor_text)
        
        candidate_links.append(CandidateLink(
            url=absolute_url,
            role=role,
            anchor_text=anchor_text,
            source_url=source_url,
            is_external=is_external
        ))
    
    return contacts, candidate_links


def classify_url_role(url: str, anchor_text: Optional[str] = None) -> LinkRole:
    """
    Classify the role of a URL based on its path and anchor text.
    """
    url_lower = url.lower()
    path = urlparse(url_lower).path.rstrip('/')
    
    anchor_lower = (anchor_text or '').lower()
    
    if 'wa.me' in url_lower or 'whatsapp' in url_lower:
        return LinkRole.WHATSAPP_LINK
    
    if url_lower.startswith('mailto:'):
        return LinkRole.MAILTO_LINK
    
    if url_lower.startswith('tel:'):
        return LinkRole.TEL_LINK
    
    if path in ('', '/', '/index', '/index.html', '/home'):
        return LinkRole.HOMEPAGE
    
    if any(kw in path for kw in ['contact', 'get-in-touch', 'reach-us']):
        return LinkRole.CONTACT
    
    if any(kw in path for kw in ['about', 'about-us', 'who-we-are', 'our-story']):
        return LinkRole.ABOUT
    
    if any(kw in path for kw in ['team', 'our-team', 'people', 'staff']):
        return LinkRole.TEAM
    
    if any(kw in path for kw in ['privacy', 'privacy-policy']):
        return LinkRole.PRIVACY
    
    if any(kw in path for kw in ['terms', 'terms-of-service', 'legal']):
        return LinkRole.TERMS
    
    social_domains = ['linkedin.com', 'twitter.com', 'x.com', 'facebook.com', 'instagram.com', 
                      'youtube.com', 'tiktok.com', 'github.com']
    if any(domain in url_lower for domain in social_domains):
        return LinkRole.SOCIAL_PROFILE
    
    if any(kw in anchor_lower for kw in ['contact', 'get in touch', 'reach us']):
        return LinkRole.CONTACT
    
    if any(kw in anchor_lower for kw in ['about', 'who we are']):
        return LinkRole.ABOUT
    
    return LinkRole.OTHER


def summarize_text_briefly(text: str, max_length: int = 200) -> Optional[str]:
    """
    Create a brief summary of text without using LLM.
    
    Uses rule-based approach:
    1. Extract first meaningful paragraph
    2. Truncate to max_length
    """
    if not text:
        return None
    
    text = re.sub(r'\s+', ' ', text).strip()
    
    sentences = re.split(r'[.!?]+', text)
    
    meaningful = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 20 and not sentence.lower().startswith(('cookie', 'privacy', 'subscribe', 'sign up')):
            meaningful.append(sentence)
    
    if not meaningful:
        return text[:max_length] + '...' if len(text) > max_length else text
    
    summary = '. '.join(meaningful[:2])
    if len(summary) > max_length:
        summary = summary[:max_length].rsplit(' ', 1)[0] + '...'
    
    return summary


def dedupe_contacts(contacts: List[ContactItem]) -> List[ContactItem]:
    """
    Deduplicate contacts by type and normalized value.
    Keeps the one with highest confidence.
    """
    if not contacts:
        return []
    
    seen: Dict[Tuple[ContactType, str], ContactItem] = {}
    
    for contact in contacts:
        key = (contact.type, contact.normalized or contact.value)
        if key not in seen or contact.confidence > seen[key].confidence:
            seen[key] = contact
    
    return list(seen.values())


def dedupe_links(links: List[CandidateLink]) -> List[CandidateLink]:
    """
    Deduplicate links by URL.
    """
    if not links:
        return []
    
    seen: Dict[str, CandidateLink] = {}
    
    for link in links:
        url_key = link.url.lower().rstrip('/')
        if url_key not in seen:
            seen[url_key] = link
    
    return list(seen.values())


def generate_missing_hints(
    contacts: List[ContactItem],
    page_evidence: List[PageEvidence]
) -> List[str]:
    """
    Generate hints about missing contact information.
    """
    hints = []
    
    contact_types = {c.type for c in contacts}
    
    if ContactType.EMAIL not in contact_types:
        hints.append("no_email_found")
    
    if ContactType.PHONE not in contact_types:
        hints.append("no_phone_found")
    
    if ContactType.WHATSAPP not in contact_types:
        hints.append("no_whatsapp_found")
    
    if ContactType.CONTACT_FORM not in contact_types:
        hints.append("no_contact_form_found")
    
    has_summary = any(pe.summary for pe in page_evidence)
    if not has_summary:
        hints.append("no_company_summary_found")
    
    return hints


def check_contact_form_in_html(html: str, source_url: str) -> Optional[ContactItem]:
    """
    Check if HTML contains a contact form.
    """
    if not html:
        return None
    
    for pattern in CONTACT_FORM_INDICATORS:
        if pattern.search(html):
            return ContactItem(
                type=ContactType.CONTACT_FORM,
                value=source_url,
                normalized=source_url,
                source_url=source_url,
                confidence=0.7
            )
    
    return None


def extract_page_title(html: str) -> Optional[str]:
    """
    Extract page title from HTML.
    """
    if not html:
        return None
    
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    if title_match:
        return title_match.group(1).strip()[:200]
    
    return None


def extract_text_from_html(html: str) -> str:
    """
    Extract plain text from HTML.
    Uses BeautifulSoup if available, otherwise regex-based extraction.
    """
    if not html:
        return ""
    
    if BS4_AVAILABLE:
        try:
            soup = BeautifulSoup(html, 'lxml')
            for script in soup(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()
            return soup.get_text(separator=' ', strip=True)
        except Exception:
            pass
    
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


# ==============================================================================
# INPUT SCHEMAS
# ==============================================================================

class SpiderSinglePageContactInput(BaseModel):
    """Input schema for SpiderSinglePageContactTool."""
    url: str = Field(..., description="URL to fetch and analyze")
    company_name: Optional[str] = Field(default=None, description="Company name for context")
    include_html: bool = Field(default=False, description="Include raw HTML in debug output")
    include_text: bool = Field(default=True, description="Include extracted text in debug output")
    include_links: bool = Field(default=True, description="Extract and classify links")
    extract_contacts: bool = Field(default=True, description="Extract contact information")
    max_text_chars: int = Field(default=12000, description="Maximum characters for text extraction")
    max_links: int = Field(default=200, description="Maximum number of links to return")
    classify_links: bool = Field(default=True, description="Classify link roles")


class TavilySiteContactCrawlInput(BaseModel):
    """Input schema for TavilySiteContactCrawlTool."""
    url: str = Field(..., description="Starting URL for site crawl")
    company_name: Optional[str] = Field(default=None, description="Company name for context")
    instruction_mode: Literal["contacts_only", "contacts_and_summary", "custom"] = Field(
        default="contacts_and_summary",
        description="Crawl instruction mode"
    )
    custom_instruction: Optional[str] = Field(
        default=None,
        description="Custom instruction when mode is 'custom'"
    )
    max_depth: int = Field(default=2, ge=1, le=3, description="Maximum crawl depth")
    max_breadth: int = Field(default=20, ge=1, le=50, description="Maximum breadth per level")
    limit: int = Field(default=30, ge=1, le=100, description="Maximum pages to crawl")
    select_paths: List[str] = Field(default_factory=list, description="Path patterns to include")
    exclude_paths: List[str] = Field(default_factory=list, description="Path patterns to exclude")
    select_domains: List[str] = Field(default_factory=list, description="Domains to include")
    exclude_domains: List[str] = Field(default_factory=list, description="Domains to exclude")
    allow_external: bool = Field(default=False, description="Allow external links")
    extract_depth: Literal["basic", "advanced"] = Field(default="basic", description="Extraction depth")
    output_format: Literal["markdown", "text"] = Field(default="markdown", description="Output format")
    chunks_per_source: int = Field(default=3, ge=1, le=10, description="Chunks per source")
    include_favicon: bool = Field(default=False, description="Include favicon")
    include_usage: bool = Field(default=True, description="Include usage information")
    timeout: float = Field(default=60.0, ge=10.0, le=300.0, description="Timeout in seconds")


# ==============================================================================
# TOOL 1: SpiderSinglePageContactTool
# ==============================================================================

class SpiderSinglePageContactTool(BaseTool):
    """
    Tool for single-page contact discovery using spider-rs.
    
    Fetches a single URL and extracts:
    - Contact information (email, phone, WhatsApp, LinkedIn, etc.)
    - Links with role classification
    - Page evidence and metadata
    
    Use this tool when you have a specific URL to analyze and need
    comprehensive contact extraction from that single page.
    """
    
    name: str = "spider_single_page_contact"
    description: str = (
        "Fetches and analyzes a single webpage to extract contact information. "
        "Use this tool when you have a specific URL and need to find emails, "
        "phone numbers, WhatsApp links, LinkedIn profiles, social media links, "
        "and contact forms. Also discovers and classifies all links on the page "
        "by their role (contact, about, team, social, etc.). Returns structured "
        "JSON with contacts, candidate links, page evidence, and missing hints. "
        "Prefer this tool over TavilySiteContactCrawlTool when you only need to "
        "analyze one specific page."
    )
    args_schema: type[BaseModel] = SpiderSinglePageContactInput
    
    def _run(
        self,
        url: str,
        company_name: Optional[str] = None,
        include_html: bool = False,
        include_text: bool = True,
        include_links: bool = True,
        extract_contacts: bool = True,
        max_text_chars: int = 12000,
        max_links: int = 200,
        classify_links: bool = True
    ) -> str:
        """
        Execute single page contact discovery.
        
        Returns JSON string of NormalizedContactExtractionResult.
        """
        warnings: List[ToolWarning] = []
        raw_debug: Dict[str, Any] = {
            "tool": "SpiderSinglePageContactTool",
            "start_time": time.time(),
            "link_count": 0,
        }
        
        try:
            if not SPIDER_RS_AVAILABLE:
                return self._create_error_result(
                    url, "spider-rs library not available. Install with: pip install spider-rs"
                )
            
            page = Page(url)
            page.fetch()
            
            html = page.get_html()
            resolved_url = url
            
            if not html:
                return self._create_error_result(url, "Failed to fetch page content")
            
            raw_debug["link_count"] = html.count('<a ')
            
            text = extract_text_from_html(html)
            if len(text) > max_text_chars:
                text = text[:max_text_chars]
            
            contacts: List[ContactItem] = []
            candidate_links: List[CandidateLink] = []
            
            if extract_contacts:
                link_contacts, candidate_links = extract_contact_links_from_html(html, url)
                contacts.extend(link_contacts)
                
                text_contacts = extract_emails_from_text(text, url)
                contacts.extend(text_contacts)
                
                phone_contacts = extract_phones_from_text(text, url)
                contacts.extend(phone_contacts)
                
                form_contact = check_contact_form_in_html(html, url)
                if form_contact:
                    contacts.append(form_contact)
            
            if include_links and candidate_links:
                candidate_links = candidate_links[:max_links]
            
            contacts = dedupe_contacts(contacts)
            candidate_links = dedupe_links(candidate_links)
            
            page_title = extract_page_title(html)
            summary = summarize_text_briefly(text)
            
            supports_fields = []
            if any(c.type == ContactType.EMAIL for c in contacts):
                supports_fields.append("email")
            if any(c.type == ContactType.PHONE for c in contacts):
                supports_fields.append("phone")
            if any(c.type == ContactType.WHATSAPP for c in contacts):
                supports_fields.append("whatsapp")
            if any(c.type == ContactType.CONTACT_FORM for c in contacts):
                supports_fields.append("contact_form")
            
            page_evidence = [PageEvidence(
                page_url=url,
                page_title=page_title,
                summary=summary,
                supports_fields=supports_fields,
                snippet=text[:500] if text else None,
                contacts_found=len(contacts),
                links_found=len(candidate_links)
            )]
            
            missing_hints = generate_missing_hints(contacts, page_evidence)
            
            raw_debug["end_time"] = time.time()
            raw_debug["duration_ms"] = int((raw_debug["end_time"] - raw_debug["start_time"]) * 1000)
            
            if include_html:
                raw_debug["html_sample"] = html[:2000]
            if include_text:
                raw_debug["text_sample"] = text[:1000]
            raw_debug["raw_links_sample"] = [l.url for l in candidate_links[:10]]
            
            result = NormalizedContactExtractionResult(
                status="success",
                tool_name=self.name,
                requested_url=url,
                resolved_url=resolved_url,
                contacts=contacts,
                candidate_links=candidate_links,
                page_evidence=page_evidence,
                missing_hints=missing_hints,
                warnings=warnings,
                raw_debug=raw_debug
            )
            
            return result.model_dump_json()
            
        except Exception as e:
            return self._create_error_result(url, f"Error during page fetch: {str(e)}")
    
    def _create_error_result(self, url: str, error_message: str) -> str:
        """Create an error result JSON string."""
        result = NormalizedContactExtractionResult(
            status="failed",
            tool_name=self.name,
            requested_url=url,
            warnings=[ToolWarning(
                code="execution_error",
                message=error_message
            )],
            raw_debug={"error": error_message}
        )
        return result.model_dump_json()


# ==============================================================================
# TOOL 2: TavilySiteContactCrawlTool
# ==============================================================================

class TavilySiteContactCrawlTool(BaseTool):
    """
    Tool for site-wide contact discovery using Tavily Crawl.
    
    Crawls multiple pages of a website and aggregates:
    - Contact information from all pages
    - Page evidence and summaries
    - Candidate links for further exploration
    
    Use this tool when you need to discover contacts across an entire site
    or when you don't know exactly which page contains contact info.
    """
    
    name: str = "tavily_site_contact_crawl"
    description: str = (
        "Crawls an entire website to discover contact information across multiple pages. "
        "Use this tool when you need comprehensive site-wide contact discovery and don't "
        "know exactly which page contains the contact info. Automatically discovers and "
        "analyzes contact pages, about pages, team pages, and more. Extracts emails, "
        "phone numbers, WhatsApp links, LinkedIn profiles, and contact forms from all "
        "discovered pages. Returns structured JSON with aggregated contacts, per-page "
        "evidence, candidate links, and hints about missing information. Requires "
        "TAVILY_API_KEY environment variable. Prefer this tool over SpiderSinglePageContactTool "
        "when you need to search across multiple pages of a website."
    )
    args_schema: type[BaseModel] = TavilySiteContactCrawlInput
    env_vars: list[EnvVar] = [
        EnvVar(
            name="TAVILY_API_KEY",
            description="API key for Tavily crawl service. Get your key at https://tavily.com",
            required=True,
        ),
    ]
    
    INSTRUCTION_TEMPLATES: ClassVar[Dict[str, str]] = {
        "contacts_only": (
            "Find all contact information including emails, phone numbers, "
            "WhatsApp links, LinkedIn profiles, and contact forms. "
            "Focus on contact, about, and team pages."
        ),
        "contacts_and_summary": (
            "Find all contact information including emails, phone numbers, "
            "WhatsApp links, LinkedIn profiles, and contact forms. "
            "Also extract company summary and key information about the business. "
            "Focus on contact, about, team, and home pages."
        ),
    }
    
    def _run(
        self,
        url: str,
        company_name: Optional[str] = None,
        instruction_mode: Literal["contacts_only", "contacts_and_summary", "custom"] = "contacts_and_summary",
        custom_instruction: Optional[str] = None,
        max_depth: int = 2,
        max_breadth: int = 20,
        limit: int = 30,
        select_paths: List[str] = None,
        exclude_paths: List[str] = None,
        select_domains: List[str] = None,
        exclude_domains: List[str] = None,
        allow_external: bool = False,
        extract_depth: Literal["basic", "advanced"] = "basic",
        output_format: Literal["markdown", "text"] = "markdown",
        chunks_per_source: int = 3,
        include_favicon: bool = False,
        include_usage: bool = True,
        timeout: float = 60.0
    ) -> str:
        """
        Execute site-wide contact discovery crawl.
        
        Returns JSON string of NormalizedContactExtractionResult.
        """
        select_paths = select_paths or []
        exclude_paths = exclude_paths or []
        select_domains = select_domains or []
        exclude_domains = exclude_domains or []
        
        warnings: List[ToolWarning] = []
        raw_debug: Dict[str, Any] = {
            "tool": "TavilySiteContactCrawlTool",
            "start_time": time.time(),
            "request_params": {
                "url": url,
                "instruction_mode": instruction_mode,
                "max_depth": max_depth,
                "max_breadth": max_breadth,
                "limit": limit,
            }
        }
        
        try:
            if not TAVILY_AVAILABLE:
                return self._create_error_result(
                    url, "tavily-python library not available. Install with: pip install tavily-python"
                )
            
            instruction = self._get_instruction(instruction_mode, custom_instruction)
            
            client = TavilyClient()
            
            crawl_params = {
                "url": url,
                "instruction": instruction,
                "max_depth": max_depth,
                "max_breadth": max_breadth,
                "limit": limit,
                "extract_depth": extract_depth,
                "output_format": output_format,
                "chunks_per_source": chunks_per_source,
                "include_favicon": include_favicon,
                "timeout": int(timeout),
            }
            
            if select_paths:
                crawl_params["select_paths"] = select_paths
            if exclude_paths:
                crawl_params["exclude_paths"] = exclude_paths
            if select_domains:
                crawl_params["select_domains"] = select_domains
            if exclude_domains:
                crawl_params["exclude_domains"] = exclude_domains
            
            crawl_params["allow_external"] = allow_external
            
            response = client.crawl(**crawl_params)
            
            raw_debug["response_time"] = time.time()
            raw_debug["request_id"] = response.get("request_id", "unknown")
            
            if include_usage and "usage" in response:
                raw_debug["usage"] = response["usage"]
            
            results = response.get("results", [])
            raw_debug["raw_result_count"] = len(results)
            
            all_contacts: List[ContactItem] = []
            all_links: List[CandidateLink] = []
            page_evidence: List[PageEvidence] = []
            
            for page_result in results:
                page_url = page_result.get("url", "")
                raw_content = page_result.get("raw_content", "")
                
                if not raw_content:
                    continue
                
                page_contacts = self._extract_contacts_from_tavily_result(
                    raw_content, page_url, output_format
                )
                all_contacts.extend(page_contacts)
                
                page_links = self._extract_links_from_tavily_result(
                    raw_content, page_url, output_format
                )
                all_links.extend(page_links)
                
                summary = summarize_text_briefly(raw_content[:2000])
                
                supports_fields = []
                page_contact_types = {c.type for c in page_contacts}
                if ContactType.EMAIL in page_contact_types:
                    supports_fields.append("email")
                if ContactType.PHONE in page_contact_types:
                    supports_fields.append("phone")
                if ContactType.WHATSAPP in page_contact_types:
                    supports_fields.append("whatsapp")
                if ContactType.CONTACT_FORM in page_contact_types:
                    supports_fields.append("contact_form")
                
                page_evidence.append(PageEvidence(
                    page_url=page_url,
                    page_title=page_result.get("title"),
                    summary=summary,
                    supports_fields=supports_fields,
                    snippet=raw_content[:500] if raw_content else None,
                    contacts_found=len(page_contacts),
                    links_found=len(page_links)
                ))
            
            all_contacts = dedupe_contacts(all_contacts)
            all_links = dedupe_links(all_links)
            
            missing_hints = generate_missing_hints(all_contacts, page_evidence)
            
            raw_debug["end_time"] = time.time()
            raw_debug["duration_ms"] = int((raw_debug["end_time"] - raw_debug["start_time"]) * 1000)
            raw_debug["total_contacts"] = len(all_contacts)
            raw_debug["total_links"] = len(all_links)
            raw_debug["pages_analyzed"] = len(page_evidence)
            
            result = NormalizedContactExtractionResult(
                status="success",
                tool_name=self.name,
                requested_url=url,
                resolved_url=url,
                contacts=all_contacts,
                candidate_links=all_links,
                page_evidence=page_evidence,
                missing_hints=missing_hints,
                warnings=warnings,
                raw_debug=raw_debug
            )
            
            return result.model_dump_json()
            
        except Exception as e:
            return self._create_error_result(url, f"Error during site crawl: {str(e)}")
    
    def _get_instruction(
        self,
        mode: str,
        custom_instruction: Optional[str]
    ) -> str:
        """Get crawl instruction based on mode."""
        if mode == "custom" and custom_instruction:
            return custom_instruction
        return self.INSTRUCTION_TEMPLATES.get(mode, self.INSTRUCTION_TEMPLATES["contacts_and_summary"])
    
    def _extract_contacts_from_tavily_result(
        self,
        content: str,
        source_url: str,
        output_format: str
    ) -> List[ContactItem]:
        """Extract contacts from Tavily crawl result content."""
        contacts: List[ContactItem] = []
        
        email_contacts = extract_emails_from_text(content, source_url)
        contacts.extend(email_contacts)
        
        phone_contacts = extract_phones_from_text(content, source_url)
        contacts.extend(phone_contacts)
        
        for pattern in WHATSAPP_PATTERNS:
            for match in pattern.finditer(content):
                wa_url = match.group(0)
                normalized = normalize_whatsapp(wa_url)
                if normalized:
                    contacts.append(ContactItem(
                        type=ContactType.WHATSAPP,
                        value=wa_url,
                        normalized=normalized,
                        source_url=source_url,
                        confidence=0.9
                    ))
        
        for pattern in LINKEDIN_PATTERNS:
            for match in pattern.finditer(content):
                linkedin_url = match.group(0)
                contacts.append(ContactItem(
                    type=ContactType.LINKEDIN,
                    value=linkedin_url,
                    normalized=linkedin_url,
                    source_url=source_url,
                    confidence=0.85
                ))
        
        contact_form_indicators = ['contact form', 'contact us', 'get in touch', 'send message']
        content_lower = content.lower()
        if any(indicator in content_lower for indicator in contact_form_indicators):
            contacts.append(ContactItem(
                type=ContactType.CONTACT_FORM,
                value=source_url,
                normalized=source_url,
                source_url=source_url,
                confidence=0.6
            ))
        
        return contacts
    
    def _extract_links_from_tavily_result(
        self,
        content: str,
        source_url: str,
        output_format: str
    ) -> List[CandidateLink]:
        """Extract links from Tavily crawl result content."""
        links: List[CandidateLink] = []
        seen: Set[str] = set()
        
        url_pattern = re.compile(r'https?://[^\s<>"\)]+', re.IGNORECASE)
        
        for match in url_pattern.finditer(content):
            found_url = match.group(0)
            
            if found_url.lower() in seen:
                continue
            seen.add(found_url.lower())
            
            if any(ext in found_url.lower() for ext in ['.jpg', '.png', '.gif', '.svg', '.css', '.js']):
                continue
            
            is_external = urlparse(found_url).netloc != urlparse(source_url).netloc
            role = classify_url_role(found_url)
            
            links.append(CandidateLink(
                url=found_url,
                role=role,
                source_url=source_url,
                is_external=is_external
            ))
        
        return links
    
    def _create_error_result(self, url: str, error_message: str) -> str:
        """Create an error result JSON string."""
        result = NormalizedContactExtractionResult(
            status="failed",
            tool_name=self.name,
            requested_url=url,
            warnings=[ToolWarning(
                code="execution_error",
                message=error_message
            )],
            raw_debug={"error": error_message}
        )
        return result.model_dump_json()


# ==============================================================================
# MINIMAL USAGE EXAMPLE
# ==============================================================================

def example_usage():
    """
    Minimal example showing how to instantiate and use both tools.
    """
    print("=" * 60)
    print("Contact Discovery Tools - Usage Example")
    print("=" * 60)
    
    spider_tool = SpiderSinglePageContactTool()
    tavily_tool = TavilySiteContactCrawlTool()
    
    print("\n1. SpiderSinglePageContactTool Example:")
    print("-" * 40)
    
    spider_result_json = spider_tool._run(
        url="https://smksolar.com.ng/product-category/solar-fridge-freezer/",
        company_name="Example Corp",
        include_html=False,
        include_text=True,
        include_links=True,
        extract_contacts=True,
        max_text_chars=5000,
        max_links=50
    )
    
    spider_result = json.loads(spider_result_json)
    print(f"Status: {spider_result['status']}")
    print(f"Contacts found: {len(spider_result['contacts'])}")
    print(f"Links found: {len(spider_result['candidate_links'])}")
    print(f"Missing hints: {spider_result['missing_hints']}")
    
    print("\n2. TavilySiteContactCrawlTool Example:")
    print("-" * 40)
    
    tavily_result_json = tavily_tool._run(
        url="https://smksolar.com.ng/product-category/solar-fridge-freezer/",
        company_name="Example Corp",
        instruction_mode="contacts_and_summary",
        max_depth=2,
        limit=10,
        timeout=30.0
    )
    
    tavily_result = json.loads(tavily_result_json)
    print(f"Status: {tavily_result['status']}")
    print(f"Pages analyzed: {len(tavily_result['page_evidence'])}")
    print(f"Contacts found: {len(tavily_result['contacts'])}")
    print(f"Missing hints: {tavily_result['missing_hints']}")
    
    print("\n" + "=" * 60)
    print("Both tools return NormalizedContactExtractionResult as JSON")
    print("=" * 60)
    
    return spider_result, tavily_result


if __name__ == "__main__":
    example_usage()
