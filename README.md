# CObtainFlow

**AI 驱动的 B2B 企业联系方式发现工具** — 只需描述你想找什么样的供应商，CObtainFlow 自动帮你完成搜索、整理和报告生成。

支持从全球网站中发现目标公司的邮箱、电话、WhatsApp、LinkedIn 等多维度联系方式，输出结构化的搜索报告。

## 5 分钟快速上手

### 1. 安装依赖

```bash
# 安装 UV（如未安装）
pip install uv

# 进入项目目录并安装
cd cobtainflow
uv sync
```

### 2. 配置 API Key

在项目根目录创建 `.env` 文件：

```env
OPENAI_API_KEY=your-openai-or-deepseek-key
TAVILY_API_KEY=your-tavily-key
EMBEDDING_API_KEY=your-embedding-key
EMBEDDING_BASE_URL=https://your-embedding-endpoint
```

### 3. 运行

```bash
# 交互式命令行
uv run python -m cobtainflow.main

# 或指定搜索需求
uv run python -c "from cobtainflow.main import kickoff; kickoff({'user_query': '10 EV battery suppliers in Nigeria'})"
```

### 4. 查看结果

运行完成后，打开 `output/` 目录查看：
- `*_contact_discovery_report.md` — 可读的报告
- `*_contact_discovery_result.json` — 完整的结构化数据

---

## 它能做什么？

**输入**：用自然语言描述你的需求

```
"帮我找10个以上南美洲的太阳能冰箱供应商的联系方式"
"深圳的工业机器人制造商，要有邮箱和电话"
"非洲光伏板供应商，不要中介"
```

**输出**：结构化的联系人报告

| 公司名称 | 国家 | 邮箱 | 电话 | WhatsApp | LinkedIn | 可信度 |
|----------|------|------|------|----------|----------|--------|
| CIME COMERCIAL S.A. | 秘鲁 | cime@cime.com.pe | +5113260601 | — | — | 高 |
| Esol | 智利 | contactos@esol.cl | +56 2 2556 4871 | — | — | 高 |
| insumosolar.cl | 智利 | ventas@insumosolar.cl | +56 2 2631 4101 | — | — | 高 |

报告还包含每家公司的官网、社交媒体、联系表单等完整信息。

---

## 核心特性

### 智能多轮搜索

系统会自动判断信息完整度，对不完整的公司进行深度搜索，最多支持 4 轮迭代：

- **Broad 模式**：广泛发现新公司
- **Deep 模式**：针对特定公司补全联系方式

### 多渠道验证

整合官网、Contact/About 页面、LinkedIn、企业目录、社交媒体等多个渠道的信息，并对每个联系方式标注可信度等级（高/中/低）。

### 联系方式类型

- 邮箱（Email）
- 电话（Phone，E.164 格式）
- WhatsApp（wa.me 链接）
- LinkedIn（个人/公司主页）
- 联系表单
- 其他社交媒体（Facebook、Instagram 等）

### 结构化输出

- **Markdown 报告** — 方便阅读和分享
- **JSON 数据** — 方便程序处理或导入 CRM

---

## 常见使用场景

| 场景 | 示例 |
|------|------|
| 供应链调研 | "东南亚光伏组件供应商" |
| 销售线索开发 | "美国医疗器械经销商" |
| 市场拓展 | "德国工业自动化公司" |
| 竞品分析 | "列出欧洲电动车电池厂商" |

---

## 技术架构

```
用户输入 → [Flow 编排层] → [Crew 单轮执行层] → [工具执行层]
                      ↓
              ContactDiscoveryFlow
                 (多轮循环控制)
                      ↓
         ┌────────────┴────────────┐
         ↓                         ↓
   searcher agent           organizer agent
   (搜索公司/联系方式)      (去重/整合/决策)
         ↓                         ↓
   Skills: contact-search    Skills: contact-organizer
         ↓                         ↓
   TavilySearchTool          FileWriterTool
   SpiderSinglePageContactTool   FileReadTool
   TavilySiteContactCrawlTool
```

**技术栈**：CrewAI Flow · DeepSeek-V3 · Tavily API · Spider-rs · Pydantic · ChromaDB · UV

---

## 进阶用法

### 编程调用

```python
from cobtainflow.main import kickoff

result = kickoff({
    "user_query": "solar refrigerator suppliers South Africa",
    "max_rounds": 4,           # 最大搜索轮数
    "max_companies_per_round": 8,  # 每轮最大处理公司数
})
```

### 生成流程图

```bash
uv run python -c "from cobtainflow.main import plot; plot()"
```

### 更换 LLM 模型

编辑 `src/cobtainflow/crews/seor_crew/config/agents.yaml` 中的 `llm` 字段。

---

## 输出示例

实际运行输出（搜索"南美洲太阳能冰箱供应商"）：

**报告摘要**：
- 执行轮次：3 轮
- 停止原因：无更多深搜目标
- 累计发现公司：7 家
- 完整度：所有公司均获得邮箱和电话

**完整示例**：见 [output/contact_discovery_report.md](output/contact_discovery_report.md)

---

## 自定义爬取工具

项目内置两个自定义工具：

| 工具 | 用途 | 适用场景 |
|------|------|----------|
| `SpiderSinglePageContactTool` | 单页面精准抓取 | 已知具体 URL |
| `TavilySiteContactCrawlTool` | 站点级深度爬取 | 需要遍历整站找联系方式 |

---

## 常见问题

**Q: 搜索结果太少怎么办？**
A: 尝试扩大搜索范围（如从"深圳"扩大到"华南地区"），或增加 `max_rounds` 参数。

**Q: 如何更换 LLM 模型？**
A: 编辑 `src/cobtainflow/crews/seor_crew/config/agents.yaml`，修改 `llm` 字段，如 `"openai/gpt-4o"`。

**Q: Memory 存储在哪里？**
A: 默认在项目根目录 `memory/` 文件夹，可通过 `CREWAI_STORAGE_DIR` 环境变量自定义。

---

## 项目结构

```
cobtainflow/
├── src/cobtainflow/
│   ├── main.py                  # Flow 入口 & CLI
│   ├── crews/seor_crew/
│   │   ├── seor_crew.py         # Crew 定义 & 输出模型
│   │   └── config/
│   │       ├── agents.yaml      # Agent 配置
│   │       └── tasks.yaml       # Task 配置
│   ├── tools/
│   │   └── contact_discovery_tools.py  # 自定义工具
│   ├── file_memory.py           # 文件存储后端 & HybridMemory
│   └── memory_factory.py        # 进程级共享 Memory 单例
├── skills/
│   ├── contact-search/           # 搜索能力
│   └── contact-organizer/        # 整理报告能力
├── memory/                       # Memory 持久化目录（自动创建）
├── output/                       # 运行输出目录
└── pyproject.toml               # 项目配置
```

---

## Memory 架构

项目实现了完整的自定义 Memory 系统，详情见 [file_memory.py](src/cobtainflow/file_memory.py)。

### 存储后端：FileStorageBackend

- **md 文件**为内容 source of truth
- **ChromaDB**作为向量索引
- **BM25**作为关键词检索
- **RRF 融合**（k=60）实现混合搜索

### Memory 类型

| 类 | 继承 | 用途 |
|---|------|------|
| `FileMemory` | CrewAI `Memory` | 文件存储后端 + ChromaDB 向量检索 |
| `HybridMemory` | `FileMemory` | 扩展 BM25 混合检索（解决 CrewAI recall 只传 embedding 的问题） |

### 检索流程

```
HybridMemory.recall(query)
  → 存储 raw query 到 _last_raw_query
  → 将 [query] 作为 categories[0] 传递给 storage.search()
  → FileStorageBackend.search() 用 categories[0] 做 BM25
  → 同时用 query_embedding 做 ChromaDB 向量检索
  → RRF 融合两路结果
```

### Scope 约定

| Scope | 内容 |
|-------|------|
| `/agent/searcher/{session_id}` | searcher agent 本轮搜索经验 |
| `/agent/organizer/{session_id}` | organizer agent 本轮整合经验 |
| `/global/searcher` | searcher 跨 session 累积洞察 |
| `/global/organizer` | organizer 跨 session 累积洞察 |

### 自定义 Embedding

使用 `EMBEDDING_API_KEY` + `EMBEDDING_BASE_URL` 配置自定义 embedding 提供者（默认 `text-embedding-v4`）。

---

## 技术参考

| 组件 | 技术 |
|------|------|
| 多 Agent 框架 | CrewAI Flow (>=1.13.0) |
| LLM | DeepSeek-V3.2 / GPT-4o / Claude |
| 搜索与爬取 | Tavily API (>=0.7.23) |
| 网页抓取 | Spider-rs (>=0.0.57) |
| 数据验证 | Pydantic |
| 向量存储 | ChromaDB |
| 包管理 | UV |