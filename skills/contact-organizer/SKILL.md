---

name: contact-organizer
description: |
  企业联系方式搜索结果整理与报告生成技能。

  当agent需要执行以下操作时可使用此skill：
  - 整合搜索结果（去重、合并同公司不同别名）
  - 评估联系方式完整性（complete/partial/insufficient）
  - 生成用户可读的 markdown 报告
  - 决定下一轮深搜目标
  - 向 Flow 提供跨轮次决策信号（should_continue）

  注意：此skill提供整理能力和工具，输出格式由Task（organize_task）的expected_output定义。
allowed-tools: FileReadTool
---

# Contact Organizer Skill

企业联系方式搜索结果整理与报告生成技能，负责整合、去重、评估和报告输出。

## ⚠️ 重要说明

**此skill只提供能力和工具，不定义输出格式。**

- ✅ 提供整理和报告工具
- ✅ 提供最佳实践指导
- ❌ **不定义输出格式**（由Task的expected_output定义）
- ❌ **不定义完整工作流程**（由Task的description定义）

**输入格式**：NormalSearchTaskOutput（来自 normal_search_task）
**输出格式**：OrganizeTaskOutput（由 Task的expected_output 定义）

## 输入数据结构

**接收 normal_search_task 的输出**（NormalSearchTaskOutput格式）：

```python
{
  "round_index": int,
  "search_mode": "broad" or "deep",
  "user_query": str,
  "researched_companies": [
    {
      "company_name": str,
      "canonical_company_name": str,
      "country": str or None,
      "website": str or None,
      "company_profile_summary": str,
      "contacts": {
        "emails": [{"value": str, "source_url": str, "evidence": str, "confidence": "high|medium|low"}],
        "phones": [...],
        "whatsapp": [...],
        "linkedin": [...],
        "contact_forms": [...],
        "other_channels": [...]
      },
      "evidence_urls": [str],
      "completeness_status": "complete|partial|insufficient",
      "missing_fields": [str],
      "search_notes": str
    }
  ],
  "new_company_names_discovered": [str],
  "companies_skipped_as_already_covered": [str],
  "dedup_notes": [str]
}
```

## 核心能力

### 1. 数据整理能力

**去重与合并**：
- 同一公司的不同别名合并
- 重复联系方式去重（保留置信度最高的）
- 保留最可靠的联系方式来源

**置信度过滤（≥0.7）**：
- 过滤低置信度的联系方式
- 保留高置信度的联系方式

### 2. 完整性评估能力

**评估维度**：邮箱、电话、WhatsApp、LinkedIn、官网、企业目录

**完整性标准**：
- **complete**：≥3种联系方式类型
- **partial**：1-2种联系方式类型
- **insufficient**：0种联系方式类型

### 3. 深搜目标决策能力

**决定哪些公司需要进入下一轮 deep search**：

考虑因素：
- 该公司是否已经在 `already_seen_companies` 中出现过多次？
- 该公司的缺失字段是否可能找到？（whatsapp、linkedin 可能没有公开信息）
- 该公司是否已经"充分搜索"？（搜索了官网、LinkedIn、企业目录等多个来源）
- 如果连续两次搜索都没有新发现，建议不再放入下一轮

**决策规则**：
- `next_round_deep_search_companies` 非空 → `should_continue` 必须为 true
- `next_round_deep_search_companies` 为空 → `should_continue` 必须为 false

### 4. 报告生成能力

**report_markdown 要求**：
- 中文格式，层次分明
- 包含公司、官网、联系方式、缺失项
- 可直接作为最终报告正文

**报告内容结构**：
- 搜索概要（轮次、公司数）
- 公司清单（每家公司的联系方式和完整性状态）
- 缺失字段说明

## 可用工具

### FileReadTool — 读取文件

**使用场景**：读取 organizer_memory_context 中的历史信息（作为参考，但不作为主要数据源）。

**参数说明**：

| 参数       | 类型     | 必需 | 说明      |
| -------- | ------ | -- | ------- |
| `file_path` | string | ✅  | 完整文件路径 |

## 关于文件操作的说明

**不必写 temp 文件**：
- Flow 通过 `ContactDiscoveryState` 管理跨轮次状态
- `report_markdown` 被 Flow 的 `round_reports` 累积
- `final_company_records` 在 Flow 层面合并
- 因此每轮写 temp 文件不是必须的，organizer 也不应该尝试写 temp 文件

**不要扫描或探索工作目录中的其他文件**：
- 不要读取或写入 `temp/` 目录
- 只使用 FileReadTool 读取 organizer_memory_context 中引用的文件（如果需要）

## 最佳实践

### 1. 数据处理

- 置信度过滤 ≥0.7
- 完整性严格：≥3种类型才算 complete
- 同一公司的不同别名必须合并

### 2. 深搜决策

- 不是所有 partial 公司都需要深挖
- 优先关注：缺失关键字段（如 email + phone 都没有）+ 有可能找到的公司
- 已搜索多次且无进展的公司不再放入下一轮

### 3. 报告生成

- 报告中文、层次分明
- 包含完整的公司信息
- 明确标注缺失字段

---

## ⚠️ 核心规则（必须遵守）

1. **不执行搜索操作**，只整理和报告
2. **所有输出联系方式经置信度过滤（≥0.7）**
3. **输出格式为 OrganizeTaskOutput**（由Task定义）
4. **只在 output/ 中操作文件**，不要写入 temp/ 或其他路径
5. **不要写 temp 文件**，只在最后一轮（如需要）使用 FileWriterTool 写最终报告到 output 目录
6. **参考 organizer_memory_context**，但主要数据来自 normal_search_task 的输出