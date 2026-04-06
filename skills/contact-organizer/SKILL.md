---
name: contact-organizer
description: |
  企业联系方式搜索结果整理与报告生成技能。提供整理搜索结果、生成报告的能力集合。
  
  当agent需要以下操作时可使用此skill：
  - 整理搜索结果并生成报告
  - 对搜索到的公司联系方式进行汇总
  - 评估联系方式完整性
  - 生成中文格式的联系方式报告
  - 管理跨轮次的临时经验文件
  
  注意：此skill提供能力和工具，具体输出格式由Task定义。
allowed-tools: FileWriterTool, FileReadTool
---

# Contact Organizer Skill

企业联系方式搜索结果整理与报告生成技能，提供数据整理、质量过滤、完整性评估、跨轮次经验积累、报告生成的能力集合。

## ⚠️ 重要说明

**此skill只提供能力和工具，不定义输出格式。**

- ✅ 提供整理和报告工具
- ✅ 提供最佳实践指导
- ✅ 提供文件操作能力
- ❌ **不定义输出格式**（由Task的expected_output定义）
- ❌ **不定义完整工作流程**（由Task的description定义）

**输入格式**：NormalSearchTaskOutput（由normal_search_task输出）
**输出格式**：OrganizeTaskOutput（由Task的expected_output定义）

## 输入数据结构

**接收normal_search_task的输出**（NormalSearchTaskOutput格式）：

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

**置信度过滤**（≥0.7）：
- 过滤低置信度的联系方式
- 保留高置信度的联系方式
- 记录过滤原因

**去重**：
- 同一公司的不同别名合并
- 重复联系方式去重
- 保留最可靠的联系方式

**合并**：
- 新旧公司匹配
- 更新联系方式
- 重评完整性

### 2. 完整性评估能力

**评估维度**：
- 邮箱
- 电话
- WhatsApp
- 官网
- 社交媒体（LinkedIn等）

**完整性标准**：
- **complete**: ≥3种联系方式类型
- **partial**: 1-2种联系方式类型
- **insufficient**: 0种联系方式类型

### 3. 文件管理能力

**临时文件管理**：
- 读取历史workspace文件（round_index > 1时）
- 写入当前workspace文件（每轮必须执行）
- 写入最终报告（should_continue=false时）

**文件命名**：
- 临时文件：`temp/{query_keywords}_{flow_id}_workspace.md`
- 最终报告：`output/{query_keywords}_{flow_id}_report.md`

**文件内容**：
每一轮的输出结构中的report_markdown字段应当与历史临时文档整合并更新临时文档。最后一轮输出最终报告。

## ⚠️ 工作目录基准（必须遵守）

**所有路径相对于 `cobtainflow/` 目录（项目根目录）：**

```
cobtainflow/
├── temp/           ← workspace 文件存放于此
├── output/         ← 最终报告存放于此
└── skills/
    └── contact-organizer/
        └── SKILL.md  ← 你正在阅读的文件
```

**路径约束：**
- `temp/` — 读写临时 workspace 文件（每轮更新）
- `output/` — 写入最终报告（仅最后一轮）

**禁止行为：**
- ❌ 不要读取 `temp/` 和 `output/` 以外的任何文件
- ❌ 不要写入 `temp/` 和 `output/` 以外的任何路径
- ❌ 不要扫描、列出或探索工作目录中的其他文件或子目录

## 可用工具

### FileWriterTool — 写入文件

**参数说明：**
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `filename` | string | ✅ | 文件名（不含路径） |
| `content` | string | ✅ | 文件内容（完整字符串） |
| `directory` | string | ❌ | 目录路径（`temp` 或 `output`，默认值 `"./"`） |
| `overwrite` | string \| boolean | ❌ | 是否覆盖已存在文件（默认值 `false`） |

**调用格式（必须严格遵循）：**
```json
{
  "filename": "ev_battery_suppliers_nigeria_abc123_workspace.md",
  "content": "# Contact Discovery Workspace\n\n## 元信息\n...",
  "directory": "temp",
  "overwrite": true
}
```

**重要提示：**
- `directory` 参数直接写 `temp` 或 `output`，**不要加 `./` 前缀**
- FileWriterTool 会**自动创建目录**，无需手动创建（仅当提供了 `directory` 参数时）
- `overwrite` 可以是布尔值 `true` 或字符串 `"True"`，推荐使用布尔值
- **必须确保在项目根目录（`cobtainflow/`）下运行**，否则文件会创建在错误位置

### FileReadTool — 读取文件

**参数说明：**
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `file_path` | string | ✅ | 完整文件路径 |

**调用格式：**
```json
{
  "file_path": "temp/ev_battery_suppliers_nigeria_abc123_workspace.md"
}
```

## 工具调用示例

### 示例1：写入 workspace 文件（每轮必须执行）

```json
{
  "filename": "solar_fridge_suppliers_xyz789_workspace.md",
  "content": "# Contact Discovery Workspace\n\n## 元信息\n- 用户查询: solar refrigerator suppliers in South Africa\n- Flow ID: xyz789\n- 创建时间: 2025-04-05 10:30:00\n- 最后更新: Round 1 @ 2025-04-05 10:35:00\n\n## Round 1 分析结果\n### 本轮新发现公司\n| 名称 | 官网 | 完整性 | 缺失字段 |\n|------|------|--------|----------|\n| ABC Solar | abc.com | partial | whatsapp, linkedin |\n\n### 联系方式汇总\n- 邮箱: info@abc.com (置信度: high)\n- 电话: +27-123-4567 (置信度: high)\n\n### Deep Search 决策\n- 建议深挖: ABC Solar (缺 whatsapp, linkedin)\n\n### 本轮经验总结\n- 南非太阳能冰箱供应商主要集中在约翰内斯堡地区\n\n## 全局汇总\n### 所有已知公司状态表\n| 名称 | 发现轮次 | 完整性 | 最佳渠道 | 状态 |\n|------|----------|--------|----------|------|\n| ABC Solar | Round 1 | partial | email, phone | 待深挖 |",
  "directory": "temp",
  "overwrite": "True"
}
```

### 示例2：读取历史 workspace（round_index > 1 时）

```json
{
  "file_path": "temp/solar_fridge_suppliers_xyz789_workspace.md"
}
```

### 示例3：写入最终报告（should_continue=false 时）

```json
{
  "filename": "solar_fridge_suppliers_xyz789_report.md",
  "content": "# 联系方式搜索报告\n\n## 搜索概要\n- 用户查询: solar refrigerator suppliers in South Africa\n- 执行轮次: 3\n- 累计发现公司: 5\n\n## 公司清单\n\n### ABC Solar\n- 国家: 南非\n- 官网: https://abc.com\n- 邮箱: info@abc.com\n- 电话: +27-123-4567\n- 完整度: complete",
  "directory": "output",
  "overwrite": true
}
```

## 跨轮次临时经验文件机制

### 设计目的

多轮流程中，通过 `temp/` 下的 markdown 文件积累分析经验，避免重复分析、遗漏信息。

### 文件命名

- **临时文件**：`temp/{query_keywords}_{flow_id}_workspace.md`
- **最终报告**：`output/{query_keywords}_{flow_id}_report.md`
- **关键词提取**：去停用词(in/for/the/and/or/of/to/with/at/by/from)，取2-4个实质词，小写下划线连接
  - 例：`"10 EV battery suppliers in Nigeria"` → `ev_battery_suppliers_nigeria`
- **flow_id**：优先用 Flow 传入值，否则用时间戳 `YYYYMMDD_HHMMSS`

## Workspace 文件结构模板

```markdown
# Contact Discovery Workspace

## 元信息
- 用户查询: {user_query}
- Flow ID: {flow_id}
- 创建时间: {timestamp}
- 最后更新: Round {N} @ {timestamp}

## Round N 分析结果
### 本轮新发现公司
| 名称 | 官网 | 完整性 | 缺失字段 |
|------|------|--------|----------|
| ... | ... | ... | ... |

### 联系方式汇总
- 邮箱: ... (置信度: high/medium/low)
- 电话: ... (置信度: high/medium/low)
- WhatsApp: ... (置信度: high/medium/low)
- LinkedIn: ... (置信度: high/medium/low)

### Deep Search 决策
- 建议深挖: {公司名} (原因: 缺少 xxx)
- 不继续: {公司名} (原因: 已完整/无更多信息)

### 本轮经验总结
- ...

## 全局汇总（每次重写）
### 所有已知公司状态表
| 名称 | 发现轮次 | 完整性 | 最佳渠道 | 状态 |
|------|----------|--------|----------|------|
| ... | ... | ... | ... | ... |

### 搜索策略经验
- ...

### 待解决问题
- ...
```

## 最佳实践

### 1. 数据处理

- 置信度过滤 ≥0.7，记录来源 URL
- 完整性严格：≥3种类型才算 complete
- 同一公司的不同别名必须合并

### 2. 文件操作

- **每轮都必须调用 FileWriterTool 更新 workspace**（这是强制动作，不是可选）。你的输出结构中的report_markdown字段应当与历史文档整合并更新文档。
- 先调用 FileReadTool 读历史，再调用 FileWriterTool 写入
- 同一 query 关键词始终一致
- FileWriterTool 的 `overwrite` 参数必须设为字符串 `"True"`

### 3. 报告生成

- 报告中文、层次分明
- 包含完整的公司信息
- 明确标注缺失字段

### 4. 跨轮次经验

- 每轮结束前总结经验
- 记录搜索策略效果
- 标注待解决问题

---

## ⚠️ 核心规则（必须遵守）

1. **不执行搜索操作**，只整理和报告
2. **所有输出联系方式经置信度过滤（≥0.7）**
3. **必须主动调用工具操作文件**，不能只描述不执行
4. **只在 temp/ 和 output/ 中操作文件**，绝不触碰其他路径
5. **每轮结束前必须调用 FileWriterTool 写入 workspace**
6. **输入格式为NormalSearchTaskOutput**，不是其他格式
7. **输出格式为OrganizeTaskOutput**，由Task定义
