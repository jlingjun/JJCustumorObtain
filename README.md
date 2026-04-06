# CObtainFlow

基于 [CrewAI](https://crewai.com) Flow 的 **AI 驱动 B2B 企业联系方式发现系统**。通过多智能体协作，自动搜索目标公司/行业供应商，提取并验证邮箱、电话、WhatsApp、LinkedIn、联系表单等多维度联系方式，生成结构化搜索报告。

## 功能特性

- **双模式智能搜索**：Broad（广泛发现新公司）+ Deep（深度补全缺失字段）自动切换
- **多轮循环策略**：自动评估信息完整性，对不完整的公司发起定向深搜，最多支持 4 轮迭代
- **多源交叉验证**：整合官网、Contact/About 页面、LinkedIn、企业目录、社交媒体等多渠道证据
- **自定义爬取工具**：
  - `SpiderSinglePageContactTool` — 基于 spider-rs 的单页面精准抓取
  - `TavilySiteContactCrawlTool` — 基于 Tavily 的站点级深度爬取
- **结构化数据输出**：Pydantic 模型驱动的类型安全输出，自动生成 JSON + Markdown 报告
- **跨轮次记忆系统**：共享 Memory + 自定义 Embedding，Agent 间经验持续积累
- **Skill 技能系统**：`contact-search`（搜索能力）与 `contact-organizer`（整理报告能力）解耦设计

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                ContactDiscoveryFlow                  │
│              (CrewAI Flow 编排层)                     │
│                                                      │
│  ┌──────────┐   ┌──────────────────────────────┐    │
│  │ initialize│──▶│ run_contact_discovery_round   │    │
│  └──────────┘   │         (Crew 执行)           │    │
│                 │  ┌─────────┐  ┌────────────┐  │    │
│                 │  │searcher │─▶│ organizer   │  │    │
│                 │  │(搜索专家)│  │(整理分析师) │  │    │
│                 │  └────┬────┘  └──────┬─────┘  │    │
│                 └───────┼─────────────┼────────┘    │
│                         │             │              │
│                 ┌───────▼─────────────▼────────┐    │
│                 │      decide_next_step         │    │
│                 │  (路由: continue / finish)     │    │
│                 └──────────────┬────────────────┘    │
│                                │                     │
│                    ┌───────────▼──────────┐         │
│                    │   prepare_next_round   │◀──┐    │
│                    └───────────┬───────────┘   │    │
│                                │ (continue)     │    │
│                    ┌───────────▼───────────┐  │    │
│                    │  run_next_round        │──┘    │
│                    └───────────┬───────────┘       │
│                                │ (finish)           │
│                    ┌───────────▼───────────┐       │
│                    │       finalize         │       │
│                    │  (生成最终报告 & 输出)  │       │
│                    └────────────────────────┘       │
└─────────────────────────────────────────────────────┘
```

### 核心组件

| 组件 | 说明 |
|------|------|
| **ContactDiscoveryFlow** | Flow 编排器，控制多轮循环、状态管理、停止条件判断 |
| **ContactDiscoveryCrew** | 单轮执行 Crew，包含 searcher + organizer 两个 Agent |
| **searcher Agent** | 全球 B2B 潜客搜索专家，负责公司发现与联系方式提取 |
| **organizer Agent** | 结果整合分析师，负责去重、完整性评估、轮次决策、报告生成 |
| **SpiderSinglePageContactTool** | 单页面联系方式抓取工具（spider-rs） |
| **TavilySiteContactCrawlTool** | 站点级联系方式爬取工具（Tavily Crawl API） |

### 项目结构

```
cobtainflow/
├── src/cobtainflow/
│   ├── __init__.py
│   ├── main.py                          # Flow 入口 & CLI
│   ├── crews/seor_crew/
│   │   ├── seor_crew.py                 # Crew 定义（Agent/Task/Crew）
│   │   └── config/
│   │       ├── agents.yaml              # Agent 配置（角色/目标/背景故事）
│   │       └── tasks.yaml               # Task 配置（描述/输出格式）
│   └── tools/
│       ├── __init__.py
│       └── contact_discovery_tools.py   # 自定义爬取工具实现
├── skills/
│   ├── contact-search/                  # 搜索 Skill
│   │   ├── SKILL.md                     # Skill 定义文档
│   │   ├── references/                  # 参考文档（浅搜索/深搜索/工具说明）
│   │   └── scripts/search_executor.py   # 辅助搜索脚本
│   └── contact-organizer/               # 整理报告 Skill
│       ├── SKILL.md                     # Skill 定义文档
│       └── evals/                       # 评估配置
├── output/                              # 运行输出目录
│   ├── contact_discovery_result.json    # 结构化结果（JSON）
│   └── contact_discovery_report.md      # 可读报告（Markdown）
├── docs/                                # 开发文档
├── pyproject.toml                       # 项目配置 & 依赖
├── AGENTS.md                            # CrewAI 开发参考
└── README.md                            # 本文件
```

## 快速开始

### 环境要求

- **Python**: >= 3.10, < 3.14
- **UV**: [UV 包管理器](https://docs.astral.sh/uv/)（推荐）
- **API Keys**:
  - `OPENAI_API_KEY` 或兼容的 LLM API Key（用于 CrewAI LLM 调用）
  - `TAVILY_API_KEY`（用于 Tavily 搜索和站点爬取）
  - `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL`（用于 Memory 嵌入）

### 安装

```bash
# 1. 安装 UV（如未安装）
pip install uv

# 2. 进入项目目录
cd cobtainflow

# 3. 安装依赖
uv sync
```

### 环境配置

在项目根目录创建 `.env` 文件：

```env
# LLM 配置（DeepSeek）
OPENAI_API_KEY=sk-your-api-key-here

# Tavily 搜索 & 爬取
TAVILY_API_KEY=tvly-your-tavily-key-here

# Memory Embedding
EMBEDDING_API_KEY=your-embedding-key
EMBEDDING_BASE_URL=https://your-embedding-endpoint
```

### 运行

#### 方式一：命令行交互运行

```bash
cd cobtainflow
uv run python -m cobtainflow.main
```

程序会提示输入搜索需求，例如：

```
请输入搜索需求（如：solar refrigerator suppliers in South Africa）: 10 EV battery suppliers in Nigeria
```

#### 方式二：编程调用

```python
from cobtainflow.main import kickoff

kickoff({
    "user_query": "10 EV battery suppliers in Nigeria",
    "max_rounds": 4,
    "max_companies_per_round": 8,
})
```

#### 方式三：CrewAI CLI

```bash
cd cobtainflow
crewai run
```

### 查看输出

运行完成后，结果保存在 `output/` 目录：

- **[contact_discovery_report.md](cobtainflow/output/contact_discovery_report.md)** — Markdown 格式的可读报告
- **[contact_discovery_result.json](cobtainflow/output/contact_discovery_result.json)** — 完整的结构化数据（含所有轮次状态）

### 生成流程图

```bash
cd cobtainflow
uv run python -c "from cobtainflow.main import plot; plot()"
```

会在项目根目录生成 `ContactDiscoveryFlow.html` 流程可视化图。

## 工作原理

### 搜索流程

1. **初始化** (`initialize`) — 解析用户查询、设置搜索参数、规范化初始状态
2. **首轮 Broad 搜索** (`run_contact_discovery_round`)：
   - **searcher** 使用 TavilySearchTool 进行网络搜索，发现候选公司
   - 对每个发现的公司使用爬取工具提取联系方式
   - 输出结构化的 `NormalSearchTaskOutput`
   - **organizer** 接收搜索结果，去重合并、评估完整性、决定是否需要深搜
   - 输出 `OrganizeTaskOutput`（含下一轮深搜目标列表）
3. **路由决策** (`decide_next_step`)：
   - 有深搜目标且未达最大轮数 → 继续循环 (`continue`)
   - 无深搜目标或已达最大轮次 → 结束 (`finish`)
4. **Deep 搜索轮次** (`prepare_next_round` → `run_next_round`)：
   - 仅针对上一轮标记为"仍缺关键字段"的公司进行定向深搜
   - 使用 SpiderSinglePageContactTool / TavilySiteContactCrawlTool 深度抓取
5. **结束 & 报告** (`finalize`) — 合并所有轮次结果，生成最终报告并写入文件

### 双搜索模式

| 模式 | 触发条件 | 行为 |
|------|----------|------|
| **Broad** | 首轮或无深搜目标时 | 广泛搜索，优先发现新的候选公司 |
| **Deep** | 有明确的深搜目标列表时 | 定向围绕指定公司补全缺失字段和证据 |

### 完整性评估标准

| 等级 | 条件 |
|------|------|
| **complete** | ≥ 3 种联系方式类型且有高可信度证据 |
| **partial** | 1-2 种联系方式类型 |
| **insufficient** | 0 种有效联系方式或无可信证据 |

### 提取的联系方式类型

- 📧 **Email** — 电子邮箱（含 mailto: 链接解析）
- 📞 **Phone** — 电话号码（E.164 格式标准化）
- 💬 **WhatsApp** — WhatsApp 号码（wa.me / api.whatsapp.com 解析）
- 💼 **LinkedIn** — LinkedIn 个人/公司主页
- 📝 **Contact Form** — 网站联系表单 URL
- 🔗 **Other Channels** — Twitter/X、Facebook、Instagram 等社交媒体

## 自定义工具

### SpiderSinglePageContactTool

单页面联系方式抓取工具，使用 [spider-rs](https://github.com/spider-rs/spider-rs) 引擎。

```python
from cobtainflow.tools import SpiderSinglePageContactTool

tool = SpiderSinglePageContactTool()
result = tool._run(
    url="https://example.com/contact",
    company_name="Example Corp",
    extract_contacts=True,
)
# 返回 NormalizedContactExtractionResult JSON
```

**适用场景**：已知具体 URL，需要从单个页面精确提取联系方式。

### TavilySiteContactCrawlTool

站点级深度爬取工具，使用 [Tavily Crawl API](https://tavily.com/#crawl)。

```python
from cobtainflow.tools import TavilySiteContactCrawlTool

tool = TavilySiteContactCrawlTool()
result = tool._run(
    url="https://example.com",
    company_name="Example Corp",
    max_depth=2,
    limit=30,
    instruction_mode="contacts_and_summary",
)
# 返回聚合了多个页面的 NormalizedContactExtractionResult JSON
```

**适用场景**：需要在整个网站范围内发现联系方式，不确定哪个页面包含联系信息。

## Agent 配置

Agent 的角色、目标和行为通过 YAML 配置文件定义：

- **[agents.yaml](cobtainflow/src/cobainflow/crews/seor_crew/config/agents.yaml)** — searcher 和 organizer 的角色定义
- **[tasks.yaml](cobtainflow/src/cobainflow/crews/seor_crew/config/tasks.yaml)** — normal_search_task 和 organize_task 的任务描述与输出格式

当前使用的 LLM 为 **DeepSeek-V3.2-Exp-Thinking**（思维链推理模型），可通过修改 `agents.yaml` 中的 `llm` 字段切换。

## Skill 系统

项目采用 CrewAI Skill 架构，将能力封装为可复用的技能单元：

| Skill | 目标 Agent | 功能 |
|-------|-----------|------|
| **[contact-search](cobtainflow/skills/contact-search/SKILL.md)** | searcher | 浅搜索策略、深搜索决策树、查询生成、结果累积与去重 |
| **[contact-organizer](cobtainflow/skills/contact-organizer/SKILL.md)** | organizer | 数据整理、置信度过滤、完整性评估、跨轮次 workspace 文件管理、报告生成 |

Skill 设计原则：**只提供能力和工具，输出格式由 Task 定义**，实现了能力与格式的解耦。

## 输出示例

以下是实际运行的输出片段（搜索"南美洲太阳能冰箱供应商"）：

```markdown
# 联系方式搜索报告

- 用户查询：帮我找10个以上南美洲的太阳能冰箱供应商的联系方式
- 执行轮次：3
- 停止原因：no_more_deep_search_targets
- 累计已搜索公司数：7
- 最终保留公司数：7

## 公司清单

### CIME COMERCIAL S.A.
- 国家：Peru
- 官网：https://cime.com.pe/
- 完整度：partial
- 证据质量：high
- 邮箱：cime@cime.com.pe
- 电话：+5113260601
```

完整示例见 [output/contact_discovery_report.md](cobtainflow/output/contact_discovery_report.md)。

## 技术栈

| 技术 | 用途 |
|------|------|
| [CrewAI](https://crewai.com) (>=1.13.0) | Multi-Agent 编排框架（Flow + Crew） |
| [DeepSeek-V3.2](https://platform.deepseek.com/) | LLM 推理引擎（思维链模式） |
| [spider-rs](https://github.com/spider-rs/spider-rs) (>=0.0.57) | 高性能网页抓取引擎 |
| [Tavily](https://tavily.com) (>=0.7.23) | AI 搜索 API & 站点爬取服务 |
| [Pydantic](https://docs.pydantic.dev/) | 数据模型验证与序列化 |
| [UV](https://docs.astral.sh/uv/) | Python 包管理与虚拟环境 |

## 常见问题

**Q: 如何更换 LLM 模型？**

A: 编辑 [agents.yaml](cobtainflow/src/cobainflow/crews/seor_crew/config/agents.yaml)，修改 `llm` 字段。CrewAI 支持多种 provider 格式，如 `"openai/gpt-4o"`、`"anthropic/claude-sonnet-4"` 等。

**Q: 搜索轮数太多或太少怎么办？**

A: 通过 `kickoff()` 的 `max_rounds` 参数控制（默认 4 轮），`max_companies_per_round` 控制每轮最大处理公司数（默认 10）。

**Q: Memory 存储在哪里？**

A: 默认存储在项目根目录的 `memory/` 文件夹中。可通过环境变量 `CREWAI_STORAGE_DIR` 自定义路径。

**Q: 如何查看详细的执行日志？**

A: Agent 配置中已启用 `verbose: true`，运行时会输出详细日志。也可使用 `crewai log-tasks-outputs` 查看最新任务输出。

