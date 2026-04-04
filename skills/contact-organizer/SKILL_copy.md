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
allowed-tools: FileWriterTool, FileReadTool, DirectoryReadTool
---

# Contact Organizer Skill

企业联系方式搜索结果整理与报告生成技能，提供从原始搜索数据到结构化报告的完整解决方案。

## 核心理念

本技能作为contact-search skill的后处理环节，负责：

1. **数据整理** - 将分散的搜索结果整合为统一格式
2. **质量过滤** - 仅保留置信度≥0.7的联系方式
3. **完整性评估** - 评估每个公司的联系方式完整性
4. **跨轮次经验积累** - 通过临时文件在各轮之间传递和积累分析经验
5. **报告生成** - 生成层次清晰的中文报告

## 可用工具

你拥有以下三个文件操作工具，用于实现跨轮次经验文件机制：

| 工具 | 用途 | 核心参数 |
|------|------|---------|
| **FileReadTool** | 读取文件内容 | `file_path` (文件路径) |
| **FileWriterTool** | 写入/创建文件（自动创建目录） | `filename`, `content`, `directory`, `overwrite` |
| **DirectoryReadTool** | 列出目录中的文件 | `path` (目录路径) |

## 工具使用详解

### FileReadTool — 读取文件

**何时使用**：每轮开始时（round_index > 1），读取上一轮或之前轮次写入的 workspace 文件。

**调用方式**：
```
FileReadTool.run(file_path="./temp/ev_battery_nigeria_20260404_143022_workspace.md")
```

**返回值**：文件的完整文本内容（字符串）。如果文件不存在会返回错误信息——此时应视为第一轮，跳过读取直接创建新文件。

### FileWriterTool — 写入文件

**何时使用**：
- 每轮分析结束时：更新/创建 `./temp/` 下的 workspace 文件
- 流程结束时（should_continue=false）：将最终报告写入 `./output/`

**调用方式**：
```
FileWriterTool.run(
    filename="ev_battery_nigeria_20260404_143022_workspace.md",
    content="# Contact Discovery Workspace\n\n...(完整markdown内容)...",
    directory="./temp",
    overwrite="True"
)
```

**关键行为**：
- `directory` 不存在时会**自动创建**
- `overwrite="True"` 会覆盖已有文件（更新场景必须设为 True）
- `overwrite="False"` 时如果文件已存在则报错（适合首次创建保护）
- 返回成功消息如 `"Content successfully written to ./temp/xxx_workspace.md"`

### DirectoryReadTool — 列出目录

**何时使用**：在读取 workspace 文件前，先检查 `./temp/` 目录是否存在以及其中有哪些文件（可选的防御性检查）。

**调用方式**：
```
DirectoryReadTool.run(path="./temp")
```

**返回值**：目录下的文件列表。如果目录不存在会返回错误信息。

## 跨轮次临时经验文件机制

### 设计目的

在多轮搜索流程中，organizer 需要积累每轮的分析经验，避免重复分析、遗漏信息或决策不一致。本机制通过 `./temp/` 目录下的临时 markdown 文件实现跨轮次经验传递。

### 文件命名规则

**临时经验文件**（每轮更新）：
```
./temp/{query_keywords}_{flow_id}_workspace.md
```

- `{query_keywords}`：从 user_query 中提取 2-4 个核心关键词（英文小写，下划线连接）
- `{flow_id}`：Flow 执行时的唯一标识（由 Flow 层传入；若未传入则使用时间戳 `YYYYMMDD_HHMMSS`）
- 示例：`./temp/solar_refrigerator_south_africa_20260404_143022_workspace.md`

**最终报告文件**（仅最后一轮生成）：
```
./output/{query_keywords}_{flow_id}_report.md
./output/{query_keywords}_{flow_id}_result.json
```

### 关键词提取规则

从 user_query 提取文件名关键词：移除停用词(in/for/the/and/or/of/to/with/at/by/from)，保留有实质意义的名词/动词/形容词/地名/行业词，取前2-4个，转小写，下划线连接。

**示例**：
- `"10 EV battery suppliers in Nigeria"` → `ev_battery_suppliers_nigeria`
- `"solar refrigerator manufacturers South Africa"` → `solar_refrigerator_south_africa`

### 8阶段操作流程（含工具调用）

```
阶段0：读取历史经验（round_index > 1 时）
  │
  ├─ Step 0a: 用 FileReadTool 读取 ./temp/{keywords}_{flow_id}_workspace.md
  │   └─ 若成功 → 解析内容，提取历史公司状态/deep search决策/策略经验
  │   └─ 若失败(文件不存在) → 这是第一轮，跳到阶段1
  │
  ↓
阶段1：数据预处理 → 解析searcher输出、置信度过滤(≥0.7)、去重
    ↓
阶段2：与历史经验合并 → 新旧公司匹配合并、更新联系方式、重新评估完整性
    ↓
阶段3：公司信息整理 → 提取基本信息、分类联系方式、记录来源
    ↓
阶段4：完整性评估 → 计算类型数量(≥3种为完整)、识别缺失字段
    ↓
阶段5：轮次决策 → 构建最终输出JSON、确定next_round_targets、决定should_continue
    ↓
阶段6：写入/更新临时文件（每轮都执行，使用 FileWriterTool）
  │
  ├─ Step 6a: 组织完整的 markdown 内容
  │   ├─ 若是第1轮：从头构建完整模板（含元信息 + Round 1 章节 + 全局汇总）
  │   └─ 若是第N轮(N>1)：在现有内容基础上追加 Round N 章节并重写全局汇总
  │
  ├─ Step 6b: 调用 FileWriterTool 写入
  │   └─ FileWriterTool.run(
  │       filename="{keywords}_{flow_id}_workspace.md",
  │       content="(完整markdown)",
  │       directory="./temp",
  │       overwrite="True"
  │     )
  │
  ↓
阶段7：最终报告生成（仅 should_continue=false 时）
  │
  ├─ Step 7a: 基于完整累积数据生成最终中文报告 markdown
  ├─ Step 7b: FileWriterTool 写入报告 → directory="./output", overwrite="True"
  └─ Step 7c: 同时在 report_markdown 字段中返回报告内容（供 Flow 的 _save_outputs 使用）
```

### 临时经验文件内容模板

```markdown
# Contact Discovery Workspace

## 元信息
- 用户查询: {user_query}
- Flow ID: {flow_id}
- 创建时间: {YYYY-MM-DD HH:MM:SS}
- 最后更新: Round {round_index} @ {timestamp}

---

## Round 1 分析结果
### 本轮新发现公司
| 公司名称 | 官网 | 完整性 | 缺失字段 | 备注 |
|---------|------|--------|---------|------|

### 联系方式汇总
#### {company_name}
- 邮箱: {emails} (置信度: high/medium/low)
- 电话: {phones}
- WhatsApp: {whatsapp}
- LinkedIn: {linkedin}
- 联系表单: {contact_forms}

### Deep Search 决策
- 建议下一轮深挖: [公司列表及原因]
- 不建议继续: [公司列表及原因]

### 本轮经验总结
- {有效策略/问题模式/注意事项}

---

## 全局汇总（每次重写）
### 所有已知公司状态
| 公司名称 | 发现轮次 | 最终完整性 | 最佳联系渠道 | 状态 |
|---------|---------|-----------|------------|------|
| ... | ... | ... | ... | complete/partial/searching |

### 搜索策略经验
- {跨轮次积累的策略性发现}

### 待解决问题
- {仍未解决的关键问题}
```

### 工具调用要点总结

| 场景 | 使用哪个工具 | 关键参数 | 注意事项 |
|------|-------------|---------|---------|
| 读取历史workspace | **FileReadTool** | `file_path="./temp/{name}_workspace.md"` | round_index=1时跳过；失败不阻断主流程 |
| 写入/更新workspace | **FileWriterTool** | `directory="./temp"`, `overwrite="True"` | **每轮都必须执行**；自动创建目录 |
| 写入最终报告 | **FileWriterTool** | `directory="./output"`, `overwrite="True"` | 仅 should_continue=false 时执行 |
| 检查temp目录 | **DirectoryReadTool** | `path="./temp"` | 可选，用于防御性检查 |

### 注意事项

1. **临时文件是工作草稿**，非用户可见正式报告；只有 `output/` 才是最终交付物
2. **幂等性**：同轮重复调用不应产生重复 Round 章节写入前先检查内容是否已包含当前Round
3. **容错**：FileReadTool 返回错误时不阻断主流程，从零开始创建新文件
4. **Flow ID 优先级**：Flow层传入了就用它，否则自行生成唯一标识
5. **目录管理**：FileWriterTool 会自动创建 directory，无需手动 mkdir
6. **overwrite=True**：更新已有 workspace 时**必须**设置，否则会因文件已存在而报错
7. **content 参数**：FileWriterTool 的 content 必须是完整的 markdown 字符串，不是路径也不是对象

## 输入数据格式

接收来自 searcher 的原始搜索结果：

```json
{
  "companies": [{
    "name": "公司名称", "domain": "example.com", "introduction": "简介",
    "contacts": [{"type": "email|phone|whatsapp|linkedin|...", "value": "值", "confidence": 0.85, "source_url": "来源"}]
  }],
  "search_metadata": { "total_searches": 10, "successful": 8, "failed": 2 }
}
```

## 输出数据结构

```python
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
    completeness: float           # 0.0~1.0
    missing_fields: List[str] = []

class SearchCrewOutput(BaseModel):
    newly_found_companies: List[CompanyFinding]
    incomplete_companies: List[str]
```

## 核心处理逻辑

### 1. 数据过滤

- **置信度过滤**：仅保留 confidence ≥ 0.7 的联系方式
- **去重**：同一类型联系方式用 set 去重

### 2. 完整性评估

**联系方式类型**（共5类）：邮箱、电话、WhatsApp、官网、社交媒体(LinkedIn/Facebook/Instagram/Twitter 任一)

**判断标准**：
- complete：≥3种不同类型
- partial：1-2种类型
- insufficient：0种或仅有不可靠来源

completeness = 已有类型数 / 5.0，同时列出缺失字段的中文名称。

### 3. 报告生成

当 `incomplete_companies` 为空时生成中文报告。

## 报告模板

```markdown
# 企业联系方式搜索报告

## 搜索摘要
- 搜索公司数量 / 成功 / 部分成功 / 失败 / 总计联系方式

## 详细结果
### {公司名}
- 公司简介 / 官网
- 联系方式：邮箱 电话 WhatsApp LinkedIn Facebook Instagram Twitter
- 数据来源 URL 列表
- 完整性评分（百分比）

## 统计信息
- 完整公司数 / 需补充信息数 / 平均完整性

## 建议
{基于缺失情况的补充建议}
```

## 数据验证与错误处理

**必需字段**：`company_id`（唯一）、`company_name`（非空）、`completeness`（0.0~1.0）

**联系方式格式**：邮箱符合email格式、电话含国家代码、URL符合URL格式

**错误处理**：输入格式错误→返回期望格式说明；缺少字段→警告+默认值；格式错误→跳过该条；所有异常记录到日志不阻断流程

## 最佳实践

1. **始终置信度过滤** ≥0.7，确保输出质量
2. **记录数据来源**，便于追溯验证
3. **完整性评估严格**，至少3种类型才算完整
4. **报告清晰易读**，使用中文、层次分明
5. **每轮都用 FileWriterTool 更新临时文件**，确保跨轮经验不丢失
6. **先用 FileReadTool 读历史，再用 FileWriterTool 写入**，遵循先读后写顺序
7. **关键词提取稳定**，同一 query 始终生成相同关键词保证文件名一致
8. **FileWriterTool 的 overwrite 设为 True**，否则更新已有文件时会报错

---

**重要提示**：
- 本skill专注数据整理和报告生成，不执行实际搜索操作
- 所有输出联系方式均经置信度过滤（≥0.7）
- **你必须主动使用 FileReadTool / FileWriterTool 来操作文件**，不能仅靠描述而不实际调用工具
- **临时经验文件机制**：每轮用 FileWriterTool 在 `./temp/` 生成/更新 workspace 文件；最终报告用 FileWriterTool 写入 `./output/`
- 文件命名：`{query_keywords}_{flow_id}_workspace.md`（临时） / `{query_keywords}_{flow_id}_report.md`（最终）
