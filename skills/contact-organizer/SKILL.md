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
allowed-tools: FileWriterTool, FileReadTool
---

# Contact Organizer Skill

企业联系方式搜索结果整理与报告生成技能。作为 contact-search 的后处理环节，负责数据整理、质量过滤(≥0.7)、完整性评估、跨轮次经验积累、中文报告生成。

## ⚠️ 路径约束（必须遵守）

**你只允许在以下两个目录中操作文件，绝对不要访问其他任何路径：**
- `./temp/` — 读写临时 workspace 文件（每轮更新）
- `./output/` — 写入最终报告（仅最后一轮）

**禁止行为：**
- ❌ 不要用 FileReadTool 读取 `./temp/` 以外的任何文件
- ❌ 不要用 FileWriterTool 写入 `./temp/` 和 `./output/` 以外的任何路径
- ❌ 不要扫描、列出或探索工作目录中的其他文件或子目录

## 可用工具

| 工具 | 用途 | 核心参数 |
|------|------|---------|
| **FileReadTool** | 读取 workspace 文件 | `file_path` — 必须以 `./temp/` 开头 |
| **FileWriterTool** | 写入 workspace 或报告 | `filename`, `content`, `directory`(=`./temp/`或`./output/`), `overwrite="True"` |

### 工具调用速查

**读取历史经验**（round_index > 1 时）：
```
FileReadTool → file_path: "./temp/{keywords}_{flow_id}_workspace.md"
→ 返回文件文本内容；若文件不存在则视为第一轮，跳过即可
```

**写入/更新 workspace**（每轮结束都必须执行）：
```
FileWriterTool → filename: "{keywords}_{flow_id}_workspace.md", directory: "./temp", overwrite: "True", content: "(完整markdown)"
→ 自动创建目录；覆盖已有文件
```

**写入最终报告**（should_continue=false 时）：
```
FileWriterTool → filename: "{keywords}_{flow_id}_report.md", directory: "./output", overwrite: "True", content: "(完整markdown)"
```

## 跨轮次临时经验文件机制

### 设计目的

多轮流程中，通过 `./temp/` 下的 markdown 文件积累分析经验，避免重复分析、遗漏信息。

### 文件命名

- **临时文件**：`./temp/{query_keywords}_{flow_id}_workspace.md`
- **最终报告**：`./output/{query_keywords}_{flow_id}_report.md`
- **关键词提取**：去停用词(in/for/the/and/or/of/to/with/at/by/from)，取2-4个实质词，小写下划线连接
  - 例：`"10 EV battery suppliers in Nigeria"` → `ev_battery_suppliers_nigeria`
- **flow_id**：优先用 Flow 传入值，否则用时间戳 `YYYYMMDD_HHMMSS`

### 操作流程

```
阶段0 [round>1]: FileReadTool 读 ./temp/{name}_workspace.md → 解析历史公司状态/决策/策略
    ↓ (失败=第一轮, 跳过)
阶段1: 预处理 searcher 输出 → 置信度过滤(≥0.7) → 去重
    ↓
阶段2: 与历史经验合并 → 新旧公司匹配 → 更新联系方式 → 重评完整性
    ↓
阶段3: 整理公司信息 → 分类联系方式 → 记录来源
    ↓
阶段4: 完整性评估 → 5类(邮箱/电话/WhatsApp/官网/社交) → ≥3种为complete
    ↓
阶段5: 构建输出JSON → 决定 should_continue / next_round_deep_search_targets
    ↓
阶段6 [每轮必做]: FileWriterTool 写入/更新 ./temp/{name}_workspace.md
  ├─ 第1轮: 从头构建模板(元信息+Round N+全局汇总)
  └─ 第N轮(N>1): 在现有内容上追加 Round N + 重写全局汇总
    ↓
阶段7 [should_continue=false]: FileWriterTool 写最终报告到 ./output/
```

### Workspace 文件结构

```markdown
# Contact Discovery Workspace

## 元信息
- 用户查询 / Flow ID / 创建时间 / 最后更新(Round N @ timestamp)

## Round N 分析结果
### 本轮新发现公司 | 名称 | 官网 | 完整性 | 缺失字段 |
### 联系方式汇总 (邮箱/电话/WhatsApp/LinkedIn + 置信度)
### Deep Search 决策 (建议深挖 vs 不继续 + 原因)
### 本轮经验总结

## 全局汇总（每次重写）
### 所有已知公司状态表 | 名称 | 发现轮次 | 完整性 | 最佳渠道 | 状态 |
### 搜索策略经验 / 待解决问题
```

## 输入/输出数据结构

**输入**：searcher 的 JSON 输出（companies[].contacts[] 含 confidence/source_url）

**输出** (`OrganizeTaskOutput`)：
```python
class OrganizeTaskOutput(BaseModel):
    round_index: int
    should_continue: bool
    searched_companies_this_round: List[str]
    all_known_companies_after_merge: List[str]
    next_round_deep_search_companies: List[DeepSearchTarget]  # company_name, missing_fields, reason, priority
    final_company_records: List[FinalCompanyRecord]       # company_name, best_contact_channels, completeness_status
    report_markdown: str                                  # 最终中文报告
    memory_update_notes: MemoryUpdateNotes               # organizer_should_remember_companies, round_summary
```

## 最佳实践

1. 置信度过滤 ≥0.7，记录来源 URL
2. 完整性严格：≥3种类型才算 complete
3. 报告中文、层次分明
4. **每轮都用 FileWriterTool 更新 workspace**（这是强制动作，不是可选）
5. 先 FileReadTool 读历史，再 FileWriterTool 写入
6. 同一 query 关键词始终一致
7. FileWriterTool 的 overwrite **必须设为 True**

---

**核心规则**：
- 不执行搜索操作，只整理和报告
- 所有输出联系方式经置信度过滤（≥0.7）
- **必须主动调用工具操作文件**，不能只描述不执行
- **只在 ./temp/ 和 ./output/ 中操作文件**，绝不触碰其他路径
