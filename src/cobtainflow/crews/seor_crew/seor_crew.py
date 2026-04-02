import os
# from __future__ import annotations

from typing import Any, Dict, List, Literal

from crewai import Agent, Crew, Memory, Process, Task
from crewai.project import CrewBase, after_kickoff, agent, before_kickoff, crew, task
from pydantic import BaseModel, Field
from crewai_tools import TavilySearchTool
from cobtainflow.tools import TavilySiteContactCrawlTool, SpiderSinglePageContactTool
from crewai.agents.agent_builder.base_agent import BaseAgent
from openai import OpenAI

# =========================
# Structured output schemas
# =========================

class EvidenceContact(BaseModel):
    value: str
    source_url: str
    evidence: str
    confidence: Literal["high", "medium", "low"]


class ContactsBundle(BaseModel):
    emails: List[EvidenceContact] = Field(default_factory=list)
    phones: List[EvidenceContact] = Field(default_factory=list)
    whatsapp: List[EvidenceContact] = Field(default_factory=list)
    linkedin: List[EvidenceContact] = Field(default_factory=list)
    contact_forms: List[EvidenceContact] = Field(default_factory=list)
    other_channels: List[EvidenceContact] = Field(default_factory=list)


class ResearchedCompany(BaseModel):
    company_name: str
    canonical_company_name: str
    country: str | None = None
    website: str | None = None
    company_profile_summary: str
    contacts: ContactsBundle
    evidence_urls: List[str] = Field(default_factory=list)
    completeness_status: Literal["complete", "partial", "insufficient"]
    missing_fields: List[str] = Field(default_factory=list)
    search_notes: str


class NormalSearchTaskOutput(BaseModel):
    round_index: int
    search_mode: Literal["broad", "deep"]
    user_query: str
    researched_companies: List[ResearchedCompany] = Field(default_factory=list)
    new_company_names_discovered: List[str] = Field(default_factory=list)
    companies_skipped_as_already_covered: List[str] = Field(default_factory=list)
    dedup_notes: List[str] = Field(default_factory=list)


class DeepSearchTarget(BaseModel):
    company_name: str
    missing_fields: List[str] = Field(default_factory=list)
    reason_for_deep_search: str
    priority: Literal["high", "medium", "low"]


class BestContactChannels(BaseModel):
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    whatsapp: List[str] = Field(default_factory=list)
    linkedin: List[str] = Field(default_factory=list)
    contact_forms: List[str] = Field(default_factory=list)
    other_channels: List[str] = Field(default_factory=list)


class FinalCompanyRecord(BaseModel):
    company_name: str
    country: str | None = None
    website: str | None = None
    best_contact_channels: BestContactChannels
    completeness_status: Literal["complete", "partial", "insufficient"]
    missing_fields: List[str] = Field(default_factory=list)
    evidence_quality: Literal["high", "medium", "low"]


class MemoryUpdateNotes(BaseModel):
    organizer_should_remember_companies: List[str] = Field(default_factory=list)
    organizer_round_summary: str


class OrganizeTaskOutput(BaseModel):
    round_index: int
    should_continue: bool
    searched_companies_this_round: List[str] = Field(default_factory=list)
    all_known_companies_after_merge: List[str] = Field(default_factory=list)
    next_round_deep_search_companies: List[DeepSearchTarget] = Field(default_factory=list)
    final_company_records: List[FinalCompanyRecord] = Field(default_factory=list)
    report_markdown: str
    memory_update_notes: MemoryUpdateNotes


# =========================
# Crew definition
# =========================

@CrewBase
class ContactDiscoveryCrew():
    """Single-round contact discovery crew.

    Design intent:
    - Crew only completes one round of search + organization.
    - Flow decides whether to loop again based on the final JSON output.
    - Crew owns a shared memory store.
    - Each agent also gets a private memory scope for agent-specific experience.
    """

    # agents_config = "config/agent.yaml"
    # tasks_config = "config/task.yaml"
    agents: list[BaseAgent]
    tasks: list[Task]



    # ---------- lifecycle hooks ----------

    @before_kickoff
    def prepare_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Flow state before interpolation into YAML task prompts."""
        normalized = dict(inputs or {})

        normalized.setdefault("user_query", "")
        normalized.setdefault("round_index", 1)
        normalized.setdefault("search_mode", "broad")
        normalized.setdefault("max_companies_per_round", 10)

        normalized["already_seen_companies"] = self._normalize_string_list(
            normalized.get("already_seen_companies")
        )
        normalized["target_companies_for_deep_search"] = self._normalize_deep_targets(
            normalized.get("target_companies_for_deep_search")
        )

        if normalized["search_mode"] not in {"broad", "deep"}:
            normalized["search_mode"] = "broad"

        # Safety fallback: if Flow accidentally requests deep mode without targets,
        # run a broad round instead of giving the searcher contradictory instructions.
        if (
            normalized["search_mode"] == "deep"
            and not normalized["target_companies_for_deep_search"]
        ):
            normalized["search_mode"] = "broad"

        return normalized

    @after_kickoff
    def process_output(self, output):
        """Leave the structured CrewOutput intact for Flow consumption.

        With output_json configured on the final task, Flow can read:
        - output.json_dict
        - output.tasks_output
        - output.raw
        """
        return output
    
    
    # ---------- memory ----------
    def my_embedder(self, texts: list[str]) -> list[list[float]]:
    # Your embedding logic here
        client = OpenAI(
            api_key=os.getenv("EMBEDDING_API_KEY"),  # 如果您没有配置环境变量，请在此处用您的API Key进行替换
            base_url=os.getenv("EMBEDDING_BASE_URL")  # 百炼服务的base_url
        )
        completion = client.embeddings.create(
            model="text-embedding-v4",
            input=texts,
            dimensions=1024, # 指定向量维度（仅 text-embedding-v3及 text-embedding-v4支持该参数）
            encoding_format="float"
        )
        return [item.embedding for item in completion.data]
    
    def _shared_memory(self) -> Memory:
        if not hasattr(self, "__shared_memory"):
            self.__shared_memory = Memory(llm="deepseek/DeepSeek-V3.2",
                embedder=self.my_embedder
            )
        return self.__shared_memory


    # ---------- agents ----------

    @agent
    def searcher(self) -> Agent:
        return Agent(
            config=self.agents_config["searcher"],
            tools=[TavilySearchTool(), SpiderSinglePageContactTool(), TavilySiteContactCrawlTool()],
            memory=self._shared_memory().scope("/agent/searcher"),
            skills=["./skills/contact-search"]
        )

    @agent
    def organizer(self) -> Agent:
        return Agent(
            config=self.agents_config["organizer"],
            memory=self._shared_memory().scope("/agent/organizer"),
            skills=["./skills/contact-organizer"]
        )

    # ---------- tasks ----------

    @task
    def normal_search_task(self) -> Task:
        return Task(
            config=self.tasks_config["normal_search_task"],
            agent=self.searcher(),
            output_json=NormalSearchTaskOutput,
        )

    @task
    def organize_task(self) -> Task:
        return Task(
            config=self.tasks_config["organize_task"],
            agent=self.organizer(),
            context=[self.normal_search_task()],
            output_json=OrganizeTaskOutput,
        )

    # ---------- crew ----------

    @crew
    def crew(self) -> Crew:
        """Creates the single-round contact discovery crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            memory=self._shared_memory(),
            verbose=True,
            cache=True,
        )

    # ---------- helpers ----------

    @staticmethod
    def _normalize_string_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            items = value
        else:
            items = [value]

        normalized: List[str] = []
        seen: set[str] = set()
        for item in items:
            text = str(item).strip()
            if text and text not in seen:
                normalized.append(text)
                seen.add(text)
        return normalized

    @staticmethod
    def _normalize_deep_targets(value: Any) -> List[Dict[str, Any]]:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]

        normalized: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for item in value:
            if isinstance(item, str):
                company_name = item.strip()
                payload = {
                    "company_name": company_name,
                    "missing_fields": [],
                    "reason_for_deep_search": "",
                    "priority": "medium",
                }
            elif isinstance(item, dict):
                company_name = str(item.get("company_name", "")).strip()
                payload = {
                    "company_name": company_name,
                    "missing_fields": item.get("missing_fields", []) or [],
                    "reason_for_deep_search": str(item.get("reason_for_deep_search", "")),
                    "priority": item.get("priority", "medium") or "medium",
                }
            else:
                continue

            if not company_name or company_name in seen:
                continue

            if payload["priority"] not in {"high", "medium", "low"}:
                payload["priority"] = "medium"

            normalized.append(payload)
            seen.add(company_name)

        return normalized
