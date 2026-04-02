---
name: contact-organizer
description: |
  企业联系方式搜索结果整理与报告生成技能。用于整理从searcher来的搜索结果，生成结构化的公司联系方式报告。
  
  当用户需要以下操作时触发此技能：
  - 整理搜索结果并生成报告
  - 对搜索到的公司联系方式进行汇总
  - 评估联系方式完整性
  - 生成中文格式的联系方式报告
  - 处理从contact-search skill输出的结果
  
  即使是简单的"整理搜索结果"或"生成报告"等请求，也应使用此技能。
---

# Contact Organizer Skill

企业联系方式搜索结果整理与报告生成技能，提供从原始搜索数据到结构化报告的完整解决方案。

## 核心理念

本技能作为contact-search skill的后处理环节，负责：

1. **数据整理** - 将分散的搜索结果整合为统一格式
2. **质量过滤** - 仅保留置信度≥0.7的联系方式
3. **完整性评估** - 评估每个公司的联系方式完整性
4. **报告生成** - 生成层次清晰的中文报告

## 输入数据格式

本skill接收来自searcher的原始搜索结果，通常包含：

```python
{
  "companies": [
    {
      "name": "公司名称",
      "domain": "example.com",
      "introduction": "公司简介",
      "contacts": [
        {
          "type": "email|phone|whatsapp|linkedin|facebook|instagram|twitter",
          "value": "联系方式值",
          "confidence": 0.85,
          "source_url": "来源页面"
        }
      ]
    }
  ],
  "search_metadata": {
    "total_searches": 10,
    "successful": 8,
    "failed": 2
  }
}
```

## 输出数据结构

### CompanyFinding 结构

每个公司的详细信息：

```python
from pydantic import BaseModel
from typing import List, Optional

class CompanyFinding(BaseModel):
    company_id: str
    company_name: str
    company_introduction: str
    official_domain: Optional[str] = None
    emails: List[str] = []
    phones: List[str] = []
    whatsapp_numbers: List[str] = []
    linkedin_urls: List[str] = []
    facebook_urls: List[str] = []
    instagram_urls: List[str] = []
    twitter_urls: List[str] = []
    source_urls: List[str] = []
    completeness: float
    missing_fields: List[str] = []
```

### SearchCrewOutput 结构

汇总输出：

```python
class SearchCrewOutput(BaseModel):
    newly_found_companies: List[CompanyFinding]
    incomplete_companies: List[str]
```

## 核心处理逻辑

### 1. 数据过滤

**置信度过滤**：仅保留置信度≥0.7的联系方式

```python
def filter_by_confidence(contacts: List[dict]) -> List[dict]:
    return [c for c in contacts if c.get('confidence', 0) >= 0.7]
```

**去重处理**：同一类型的联系方式去重

```python
def deduplicate_contacts(contacts: List[str]) -> List[str]:
    return list(set(contacts))
```

### 2. 完整性评估

**联系方式类型定义**：
- 邮箱 (emails)
- 电话 (phones)
- WhatsApp (whatsapp_numbers)
- 官网 (official_domain)
- 社交媒体：
  - LinkedIn (linkedin_urls)
  - Facebook (facebook_urls)
  - Instagram (instagram_urls)
  - Twitter/X (twitter_urls)

**完整性判断标准**：
- 完整：至少有3种不同类型的联系方式
- 不完整：少于3种类型的联系方式

```python
def calculate_completeness(company: CompanyFinding) -> tuple[float, List[str]]:
    contact_types = 0
    missing = []
    
    if company.emails:
        contact_types += 1
    else:
        missing.append("邮箱")
    
    if company.phones:
        contact_types += 1
    else:
        missing.append("电话")
    
    if company.whatsapp_numbers:
        contact_types += 1
    else:
        missing.append("WhatsApp")
    
    if company.official_domain:
        contact_types += 1
    else:
        missing.append("官网")
    
    social_media = (
        company.linkedin_urls or 
        company.facebook_urls or 
        company.instagram_urls or 
        company.twitter_urls
    )
    if social_media:
        contact_types += 1
    else:
        missing.append("社交媒体")
    
    completeness = contact_types / 5.0
    return completeness, missing
```

### 3. 报告生成

当`incomplete_companies`为空时，生成完整的中文报告。

## 报告模板

```markdown
# 企业联系方式搜索报告

## 搜索摘要

- **搜索公司数量**：{total_companies}
- **成功搜索**：{successful}
- **部分成功**：{partial}
- **失败搜索**：{failed}
- **总计联系方式**：{total_contacts}

## 详细结果

### {company_name}

**公司简介**：{introduction}

**官网**：{domain}

**联系方式**：
- 📧 邮箱：{emails}
- 📞 电话：{phones}
- 💬 WhatsApp：{whatsapp_numbers}
- 💼 LinkedIn：{linkedin_urls}
- 📘 Facebook：{facebook_urls}
- 📷 Instagram：{instagram_urls}
- 🐦 Twitter/X：{twitter_urls}

**数据来源**：
- {source_url_1}
- {source_url_2}

**完整性评分**：{completeness:.0%}

---

## 统计信息

- **完整公司**：{complete_count} 家
- **需补充信息**：{incomplete_count} 家
- **平均完整性**：{avg_completeness:.0%}

## 建议

{recommendations}
```

## 标准操作流程

```
原始搜索结果
    ↓
【数据预处理】
    ├─ 解析输入数据
    ├─ 置信度过滤（≥0.7）
    └─ 去重处理
    ↓
【公司信息整理】
    ├─ 提取公司基本信息
    ├─ 分类整理联系方式
    ├─ 记录数据来源
    └─ 生成company_id
    ↓
【完整性评估】
    ├─ 计算联系方式类型数量
    ├─ 识别缺失字段
    ├─ 计算完整性评分
    └─ 判断是否完整（≥3种类型）
    ↓
【生成输出】
    ├─ 构建CompanyFinding列表
    ├─ 构建incomplete_companies列表
    └─ 生成SearchCrewOutput
    ↓
【报告生成】（如果incomplete_companies为空）
    ├─ 生成搜索摘要
    ├─ 生成详细结果
    ├─ 生成统计信息
    └─ 生成建议
    ↓
最终输出
```

## 使用示例

### 示例1：完整数据处理

```python
输入：从searcher获取的原始数据（包含10家公司）

处理流程：
1. 过滤置信度<0.7的联系方式
2. 为每家公司创建CompanyFinding
3. 评估每家公司的完整性
4. 将不完整的公司加入incomplete_companies

输出：
SearchCrewOutput(
    newly_found_companies=[...],  # 10个CompanyFinding
    incomplete_companies=["公司A", "公司B"]  # 2家不完整
)
```

### 示例2：生成完整报告

```python
输入：SearchCrewOutput(incomplete_companies=[])

处理流程：
1. 确认所有公司都完整
2. 生成中文格式的报告
3. 包含搜索摘要、详细结果、统计信息

输出：
# 企业联系方式搜索报告

## 搜索摘要
- 搜索公司数量：5
- 成功搜索：5
...
```

## 数据验证规则

### 必需字段验证

- `company_id`: 必需，唯一标识
- `company_name`: 必需，不能为空
- `completeness`: 必需，0.0-1.0之间

### 联系方式格式验证

- **邮箱**：符合email格式
- **电话**：包含国家代码
- **WhatsApp**：符合电话格式
- **URL**：符合URL格式

### 置信度验证

- 所有输出的联系方式置信度必须≥0.7
- 自动过滤低置信度结果

## 错误处理

### 常见错误

1. **输入数据格式错误**
   - 返回错误信息，说明期望的格式

2. **缺少必需字段**
   - 记录警告，使用默认值

3. **联系方式格式错误**
   - 记录警告，跳过该联系方式

### 错误日志格式

```python
{
    "timestamp": "2026-04-01T10:30:00Z",
    "level": "WARNING",
    "message": "Invalid email format",
    "company": "公司A",
    "value": "invalid-email"
}
```

## 性能优化

### 批量处理

- 支持批量处理多家公司
- 并行处理独立的公司数据

### 内存优化

- 流式处理大型数据集
- 及时释放已处理的数据

## 与其他Skill的协作

### 上游：contact-search

- 接收contact-search skill的输出
- 处理原始搜索结果

### 下游：可能的扩展

- 可将结果传递给其他分析工具
- 支持导出为多种格式（JSON、CSV、PDF）

## 环境要求

```bash
# Python版本
Python >= 3.10

# 必需的包
pip install pydantic
pip install typing-extensions
```

## 导入说明

```python
from pydantic import BaseModel
from typing import List, Optional
import json
from datetime import datetime
```

## 最佳实践

1. **始终进行置信度过滤**：确保输出质量
2. **记录数据来源**：便于追溯和验证
3. **完整性评估要严格**：至少3种类型才算完整
4. **报告要清晰易读**：使用中文，层次分明
5. **错误处理要完善**：记录所有异常情况

## 输出示例

### CompanyFinding 示例

```json
{
  "company_id": "comp_001",
  "company_name": "微软",
  "company_introduction": "全球领先的科技公司",
  "official_domain": "microsoft.com",
  "emails": ["contact@microsoft.com", "support@microsoft.com"],
  "phones": ["+1-425-882-8080"],
  "whatsapp_numbers": [],
  "linkedin_urls": ["https://linkedin.com/company/microsoft"],
  "facebook_urls": ["https://facebook.com/Microsoft"],
  "instagram_urls": ["https://instagram.com/microsoft"],
  "twitter_urls": ["https://twitter.com/Microsoft"],
  "source_urls": [
    "https://microsoft.com/contact",
    "https://linkedin.com/company/microsoft"
  ],
  "completeness": 0.8,
  "missing_fields": ["WhatsApp"]
}
```

### SearchCrewOutput 示例

```json
{
  "newly_found_companies": [
    { "company_id": "comp_001", ... },
    { "company_id": "comp_002", ... }
  ],
  "incomplete_companies": ["公司C"]
}
```

---

**重要提示**：
- 本skill专注于数据整理和报告生成，不执行实际的搜索操作
- 所有输出的联系方式均经过置信度过滤（≥0.7）
- 报告使用中文撰写，层次清晰
- 完整性评估严格遵循"至少3种类型"的标准
