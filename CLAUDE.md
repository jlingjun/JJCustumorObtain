# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CObtainFlow is a CrewAI Flow-based B2B contact discovery system. It uses multi-agent collaboration to search for target companies/suppliers and extract contact information (email, phone, WhatsApp, LinkedIn, contact forms), generating structured search reports.

## Commands

```bash
# Install dependencies
uv sync

# Run the flow (interactive CLI)
uv run python -m cobtainflow.main

# Run via CrewAI CLI
crewai run

# Generate flow visualization HTML
uv run python -c "from cobtainflow.main import plot; plot()"

# Programmatic usage
python -c "from cobtainflow.main import kickoff; kickoff({'user_query': 'solar suppliers Nigeria', 'max_rounds': 4})"
```

## Architecture

### Two-Layer Loop Design

The system uses **Flow** for loop control and **Crew** for single-round execution:

- **ContactDiscoveryFlow** (`src/cobtainflow/main.py`): Owns multi-round loop control, state accumulation, and stopping decisions. Uses `broad` mode for initial discovery and `deep` mode for targeted follow-up.
- **ContactDiscoveryCrew** (`src/cobtainflow/crews/seor_crew/seor_crew.py`): Executes one round of search + organization. Reused across rounds so agent memory persists.

### Flow State Flow

```
initialize() → run_contact_discovery_round() → decide_next_step()
                                                       ↓
                         ┌─ "continue" → prepare_next_round() → run_next_round()
                         │
                         └─ "finish" → finalize()
```

### Key Patterns

**Skills vs Tasks**: Skills (in `skills/`) provide capabilities and tools. Tasks (in `config/tasks.yaml`) define output formats via `expected_output`. The searcher agent uses `contact-search` skill; the organizer uses `contact-organizer` skill.

**Structured Output**: All agent outputs use Pydantic models (`NormalSearchTaskOutput`, `OrganizeTaskOutput`) defined in `seor_crew.py`. Tasks configure `output_json=ModelName`.

**Shared Memory**: `memory_factory.py` provides a process-wide `Memory` instance with custom embedding support for cross-round experience accumulation.

## Key Files

| File | Purpose |
|------|---------|
| `src/cobtainflow/main.py` | Flow orchestration, state models, loop control |
| `src/cobtainflow/crews/seor_crew/seor_crew.py` | Crew definition, Pydantic output schemas, lifecycle hooks |
| `src/cobtainflow/crews/seor_crew/config/agents.yaml` | Agent roles/goals/backstories |
| `src/cobtainflow/crews/seor_crew/config/tasks.yaml` | Task descriptions and expected JSON output formats |
| `src/cobtainflow/tools/contact_discovery_tools.py` | Custom tools: `SpiderSinglePageContactTool`, `TavilySiteContactCrawlTool` |
| `src/cobtainflow/memory_factory.py` | Shared memory with custom embedding provider |
| `skills/contact-search/SKILL.md` | Search capability (shallow/deep search strategies) |
| `skills/contact-organizer/SKILL.md` | Organization capability (dedup, confidence filtering, reporting) |

## Agent Tools

**searcher agent**: TavilySearchTool, SpiderSinglePageContactTool, TavilySiteContactCrawlTool

**organizer agent**: FileWriterTool, FileReadTool

## Environment Variables

Required in `.env`:
- `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` — LLM API
- `TAVILY_API_KEY` — Search and crawl API
- `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` — Memory embedding provider

## Output

Results are written to `output/`:
- `{flow_id}_contact_discovery_result.json` — Full structured data
- `{flow_id}_contact_discovery_report.md` — Human-readable report

## CrewAI Reference

`AGENTS.md` in project root contains the authoritative CrewAI patterns. Key points:
- Use `crewai.LLM` or string shorthand (`"openai/gpt-4o"`) — NOT `ChatOpenAI`
- Crew classes use `@CrewBase` decorator with YAML config
- Add `# type: ignore[index]` on config dictionary access
- Flow uses `@start()`, `@listen()`, `@router()` decorators
