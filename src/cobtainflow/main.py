#!/usr/bin/env python
from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from crewai.flow.flow import Flow, listen, or_, router, start
import dotenv
dotenv.load_dotenv()
# Support both package-style and flat-script imports.
# Package-style is the default shape shown in CrewAI flow docs.

from cobtainflow.crews.seor_crew.seor_crew import ContactDiscoveryCrew  # type: ignore




# =========================
# Flow state models
# =========================


class DeepSearchTargetState(BaseModel):
    company_name: str
    missing_fields: List[str] = Field(default_factory=list)
    reason_for_deep_search: str = ""
    priority: Literal["high", "medium", "low"] = "medium"


class BestContactChannelsState(BaseModel):
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    whatsapp: List[str] = Field(default_factory=list)
    linkedin: List[str] = Field(default_factory=list)
    contact_forms: List[str] = Field(default_factory=list)
    other_channels: List[str] = Field(default_factory=list)


class FinalCompanyRecordState(BaseModel):
    company_name: str
    country: Optional[str] = None
    website: Optional[str] = None
    best_contact_channels: BestContactChannelsState = Field(
        default_factory=BestContactChannelsState
    )
    completeness_status: Literal["complete", "partial", "insufficient"] = "insufficient"
    missing_fields: List[str] = Field(default_factory=list)
    evidence_quality: Literal["high", "medium", "low"] = "low"


class ContactDiscoveryState(BaseModel):
    # User / runtime inputs
    user_query: str = ""
    current_year: int = Field(default_factory=lambda: date.today().year)
    max_rounds: int = 4
    max_companies_per_round: int = 10

    # Loop control
    round_index: int = 1
    search_mode: Literal["broad", "deep"] = "broad"
    should_continue: bool = False
    stop_reason: str = ""
    last_target_signature: List[str] = Field(default_factory=list)

    # Accumulated flow state
    already_seen_companies: List[str] = Field(default_factory=list)
    searched_companies_history: List[str] = Field(default_factory=list)
    all_known_companies: List[str] = Field(default_factory=list)
    next_round_deep_search_companies: List[DeepSearchTargetState] = Field(
        default_factory=list
    )
    final_company_records: List[FinalCompanyRecordState] = Field(default_factory=list)

    # Reporting / debugging
    latest_crew_output: Dict[str, Any] = Field(default_factory=dict)
    latest_report_markdown: str = ""
    final_report_markdown: str = ""
    round_reports: List[str] = Field(default_factory=list)
    organizer_memory_log: List[str] = Field(default_factory=list)


# =========================
# Flow definition
# =========================


class ContactDiscoveryFlow(Flow[ContactDiscoveryState]):
    """Flow that loops a single-round crew until no more deep-search targets remain.

    Design:
    - The crew does one round only.
    - The flow owns loop control, stopping criteria, and cross-round aggregation.
    - The same ContactDiscoveryCrew instance is reused so agent memory persists
      across rounds within the same flow execution.
    """

    def _crew_bundle(self) -> ContactDiscoveryCrew:
        if not hasattr(self, "_cached_contact_crew"):
            self._cached_contact_crew = ContactDiscoveryCrew()
        return self._cached_contact_crew

    @start()
    def initialize(self) -> Dict[str, Any]:
        """Normalize initial state.

        CrewAI populates matching state fields from kickoff(inputs={...}), so this
        method mainly validates and fills defaults.
        """
        if not self.state.user_query.strip():
            self.state.user_query = input("请输入搜索需求（如：solar refrigerator suppliers in South Africa）: ").strip()

        if self.state.max_rounds < 1:
            self.state.max_rounds = 1
        if self.state.max_companies_per_round < 1:
            self.state.max_companies_per_round = 10
        if self.state.round_index < 1:
            self.state.round_index = 1

        self.state.already_seen_companies = self._dedupe_strings(
            self.state.already_seen_companies
        )
        self.state.searched_companies_history = self._dedupe_strings(
            self.state.searched_companies_history
        )
        self.state.all_known_companies = self._dedupe_strings(self.state.all_known_companies)
        self.state.next_round_deep_search_companies = self._normalize_targets(
            self.state.next_round_deep_search_companies
        )

        if self.state.next_round_deep_search_companies:
            self.state.search_mode = "deep"
        elif self.state.search_mode not in {"broad", "deep"}:
            self.state.search_mode = "broad"

        print("=" * 72)
        print("ContactDiscoveryFlow started")
        print(f"query={self.state.user_query}")
        print(f"round={self.state.round_index}, mode={self.state.search_mode}")
        print("=" * 72)

        return {
            "round_index": self.state.round_index,
            "search_mode": self.state.search_mode,
        }
    
    @listen("continue")
    def prepare_next_round(self) -> Dict[str, Any]:
        """Advance state for the next loop."""
        self.state.round_index += 1
        self.state.search_mode = "deep"

        print(
            f"Preparing next round: round={self.state.round_index}, "
            f"targets={[t.company_name for t in self.state.next_round_deep_search_companies]}"
        )
        return {
            "round_index": self.state.round_index,
            "search_mode": self.state.search_mode,
        }

    @listen(or_(initialize, prepare_next_round))
    def run_contact_discovery_round(self, _: Any = None) -> Dict[str, Any]:
        """Kick off exactly one crew round and merge the result into flow state."""
        crew_inputs = {
            "user_query": self.state.user_query,
            "current_year": self.state.current_year,
            "round_index": self.state.round_index,
            "search_mode": self.state.search_mode,
            "max_companies_per_round": self.state.max_companies_per_round,
            "already_seen_companies": self.state.already_seen_companies,
            "target_companies_for_deep_search": [
                target.model_dump() for target in self.state.next_round_deep_search_companies
            ],
        }

        print(
            f"\n--- Running crew round {self.state.round_index} "
            f"({self.state.search_mode}) ---"
        )
        crew_output = self._crew_bundle().crew().kickoff(inputs=crew_inputs)
        payload = self._coerce_crew_output_to_dict(crew_output)
        self.state.latest_crew_output = payload

        searched_this_round = self._dedupe_strings(
            payload.get("searched_companies_this_round", [])
        )
        known_companies_after_merge = self._dedupe_strings(
            payload.get("all_known_companies_after_merge", [])
        )
        report_markdown = str(payload.get("report_markdown", "") or "")
        self.state.latest_report_markdown = report_markdown
        if report_markdown:
            self.state.round_reports.append(
                f"# Round {self.state.round_index}\n\n{report_markdown}".strip()
            )

        # State accumulation
        self.state.searched_companies_history = self._dedupe_strings(
            self.state.searched_companies_history + searched_this_round
        )
        self.state.already_seen_companies = self._dedupe_strings(
            self.state.already_seen_companies + searched_this_round
        )
        self.state.all_known_companies = self._dedupe_strings(
            self.state.all_known_companies + known_companies_after_merge
        )
        self.state.should_continue = bool(payload.get("should_continue", False))
        self.state.next_round_deep_search_companies = self._normalize_targets(
            payload.get("next_round_deep_search_companies", [])
        )
        self.state.final_company_records = self._merge_company_records(
            self.state.final_company_records,
            payload.get("final_company_records", []),
        )

        self._store_round_memories(payload, searched_this_round)

        return payload

    @router(run_contact_discovery_round)
    def decide_next_step(self, result: Dict[str, Any]) -> str:
        """Choose whether to continue looping or finish."""
        targets = self._normalize_targets(
            result.get("next_round_deep_search_companies", [])
        )
        current_signature = sorted(
            [self._canonical_key(target.company_name) for target in targets]
        )

        if self.state.round_index >= self.state.max_rounds:
            self.state.stop_reason = "reached_max_rounds"
            return "finish"

        if not result.get("should_continue", False) or not targets:
            self.state.stop_reason = "no_more_deep_search_targets"
            return "finish"

        # Safety rail against endless repetition of the exact same target set.
        if self.state.last_target_signature and current_signature == self.state.last_target_signature:
            self.state.stop_reason = "repeated_targets_without_progress"
            return "finish"

        self.state.last_target_signature = current_signature
        return "continue"

    

    @listen("finish")
    def finalize(self) -> Dict[str, Any]:
        """Build final report and write artifacts to disk."""
        self.state.final_report_markdown = self._build_final_report()
        self._save_outputs()

        print("\nFlow finished")
        print(f"stop_reason={self.state.stop_reason}")
        print(f"rounds_completed={self.state.round_index}")
        print(f"companies_found={len(self.state.final_company_records)}")

        return {
            "user_query": self.state.user_query,
            "stop_reason": self.state.stop_reason,
            "rounds_completed": self.state.round_index,
            "all_known_companies": self.state.all_known_companies,
            "already_seen_companies": self.state.already_seen_companies,
            "next_round_deep_search_companies": [
                target.model_dump() for target in self.state.next_round_deep_search_companies
            ],
            "final_company_records": [
                record.model_dump() for record in self.state.final_company_records
            ],
            "final_report_markdown": self.state.final_report_markdown,
        }

    # =========================
    # Internal helpers
    # =========================

    def _store_round_memories(
        self,
        organize_payload: Dict[str, Any],
        searched_this_round: List[str],
    ) -> None:
        """Write explicit per-agent memories after each round.

        Reusing the same ContactDiscoveryCrew instance preserves the shared Memory()
        object across rounds. These explicit remembers reinforce what the organizer
        and searcher should keep for later rounds.
        """
        memory_owner = self._crew_bundle()
        if not hasattr(memory_owner, "_shared_memory"):
            return

        try:
            shared_memory = memory_owner._shared_memory()
            searcher_memory = shared_memory.scope("/agent/searcher")
            organizer_memory = shared_memory.scope("/agent/organizer")

            searcher_note = (
                f"Round {self.state.round_index} | mode={self.state.search_mode} | "
                f"query={self.state.user_query} | searched companies={', '.join(searched_this_round) or 'none'}"
            )
            organizer_targets = [
                t.company_name for t in self.state.next_round_deep_search_companies
            ]
            organizer_summary = str(
                organize_payload.get("memory_update_notes", {}).get(
                    "organizer_round_summary", ""
                )
                or ""
            )
            organizer_note = (
                f"Round {self.state.round_index} | should_continue={self.state.should_continue} | "
                f"searched companies={', '.join(searched_this_round) or 'none'} | "
                f"next targets={', '.join(organizer_targets) or 'none'} | "
                f"summary={organizer_summary}"
            )

            searcher_memory.remember(
                searcher_note,
                source="flow:contact-discovery",
            )
            organizer_memory.remember(
                organizer_note,
                source="flow:contact-discovery",
            )
            self.state.organizer_memory_log.append(organizer_note)
        except Exception as exc:
            # Memory should enhance the flow, not break it.
            self.state.organizer_memory_log.append(
                f"Memory write skipped in round {self.state.round_index}: {exc}"
            )

    @staticmethod
    def _coerce_crew_output_to_dict(crew_output: Any) -> Dict[str, Any]:
        if crew_output is None:
            raise ValueError("Crew returned no output.")

        if hasattr(crew_output, "json_dict") and crew_output.json_dict:
            return dict(crew_output.json_dict)

        if hasattr(crew_output, "pydantic") and crew_output.pydantic is not None:
            return ContactDiscoveryFlow._model_dump(crew_output.pydantic)

        if hasattr(crew_output, "to_dict"):
            maybe_dict = crew_output.to_dict()
            if isinstance(maybe_dict, dict) and maybe_dict:
                return maybe_dict

        raw = getattr(crew_output, "raw", None)
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Crew output is not valid JSON and no structured output was available."
                ) from exc

        raise ValueError("Unable to convert crew output into a dictionary.")

    @staticmethod
    def _model_dump(obj: Any) -> Dict[str, Any]:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        raise TypeError(f"Object of type {type(obj)} cannot be converted to dict")

    @staticmethod
    def _dedupe_strings(values: List[Any]) -> List[str]:
        result: List[str] = []
        seen: set[str] = set()
        for value in values or []:
            text = str(value).strip()
            if not text:
                continue
            key = ContactDiscoveryFlow._canonical_key(text)
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    @staticmethod
    def _canonical_key(text: str) -> str:
        return " ".join(text.strip().lower().split())

    @classmethod
    def _normalize_targets(cls, value: Any) -> List[DeepSearchTargetState]:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]

        normalized: List[DeepSearchTargetState] = []
        seen: set[str] = set()
        for item in value:
            if isinstance(item, DeepSearchTargetState):
                target = item
            elif isinstance(item, str):
                target = DeepSearchTargetState(company_name=item.strip())
            elif isinstance(item, dict):
                target = DeepSearchTargetState(
                    company_name=str(item.get("company_name", "")).strip(),
                    missing_fields=[str(x) for x in item.get("missing_fields", []) or []],
                    reason_for_deep_search=str(item.get("reason_for_deep_search", "") or ""),
                    priority=(item.get("priority", "medium") or "medium"),
                )
            else:
                continue

            if not target.company_name:
                continue
            key = cls._canonical_key(target.company_name)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(target)
        return normalized

    @classmethod
    def _merge_company_records(
        cls,
        existing_records: List[FinalCompanyRecordState],
        incoming_records: List[Dict[str, Any]],
    ) -> List[FinalCompanyRecordState]:
        by_company: Dict[str, FinalCompanyRecordState] = {
            cls._canonical_key(record.company_name): record
            for record in existing_records
        }

        for payload in incoming_records or []:
            candidate = cls._coerce_company_record(payload)
            key = cls._canonical_key(candidate.company_name)
            if key not in by_company:
                by_company[key] = candidate
                continue
            by_company[key] = cls._merge_two_company_records(by_company[key], candidate)

        return sorted(by_company.values(), key=lambda record: record.company_name.lower())

    @classmethod
    def _coerce_company_record(cls, payload: Any) -> FinalCompanyRecordState:
        if isinstance(payload, FinalCompanyRecordState):
            return payload
        if not isinstance(payload, dict):
            raise TypeError(f"Invalid company record payload: {payload!r}")

        channels = payload.get("best_contact_channels", {}) or {}
        record = FinalCompanyRecordState(
            company_name=str(payload.get("company_name", "")).strip(),
            country=payload.get("country"),
            website=payload.get("website"),
            best_contact_channels=BestContactChannelsState(
                emails=[str(x) for x in channels.get("emails", []) or []],
                phones=[str(x) for x in channels.get("phones", []) or []],
                whatsapp=[str(x) for x in channels.get("whatsapp", []) or []],
                linkedin=[str(x) for x in channels.get("linkedin", []) or []],
                contact_forms=[str(x) for x in channels.get("contact_forms", []) or []],
                other_channels=[str(x) for x in channels.get("other_channels", []) or []],
            ),
            completeness_status=payload.get("completeness_status", "insufficient") or "insufficient",
            missing_fields=[str(x) for x in payload.get("missing_fields", []) or []],
            evidence_quality=payload.get("evidence_quality", "low") or "low",
        )
        record.missing_fields = cls._derive_missing_fields(record)
        return record

    @classmethod
    def _merge_two_company_records(
        cls,
        old: FinalCompanyRecordState,
        new: FinalCompanyRecordState,
    ) -> FinalCompanyRecordState:
        merged = FinalCompanyRecordState(
            company_name=new.company_name or old.company_name,
            country=new.country or old.country,
            website=new.website or old.website,
            best_contact_channels=BestContactChannelsState(
                emails=cls._dedupe_strings(
                    old.best_contact_channels.emails + new.best_contact_channels.emails
                ),
                phones=cls._dedupe_strings(
                    old.best_contact_channels.phones + new.best_contact_channels.phones
                ),
                whatsapp=cls._dedupe_strings(
                    old.best_contact_channels.whatsapp + new.best_contact_channels.whatsapp
                ),
                linkedin=cls._dedupe_strings(
                    old.best_contact_channels.linkedin + new.best_contact_channels.linkedin
                ),
                contact_forms=cls._dedupe_strings(
                    old.best_contact_channels.contact_forms
                    + new.best_contact_channels.contact_forms
                ),
                other_channels=cls._dedupe_strings(
                    old.best_contact_channels.other_channels
                    + new.best_contact_channels.other_channels
                ),
            ),
            completeness_status=cls._best_completeness(
                old.completeness_status,
                new.completeness_status,
            ),
            missing_fields=[],
            evidence_quality=cls._best_evidence_quality(
                old.evidence_quality,
                new.evidence_quality,
            ),
        )
        merged.missing_fields = cls._derive_missing_fields(merged)
        return merged

    @staticmethod
    def _best_completeness(
        left: Literal["complete", "partial", "insufficient"],
        right: Literal["complete", "partial", "insufficient"],
    ) -> Literal["complete", "partial", "insufficient"]:
        rank = {"insufficient": 0, "partial": 1, "complete": 2}
        return left if rank[left] >= rank[right] else right

    @staticmethod
    def _best_evidence_quality(
        left: Literal["high", "medium", "low"],
        right: Literal["high", "medium", "low"],
    ) -> Literal["high", "medium", "low"]:
        rank = {"low": 0, "medium": 1, "high": 2}
        return left if rank[left] >= rank[right] else right

    @classmethod
    def _derive_missing_fields(cls, record: FinalCompanyRecordState) -> List[str]:
        missing: List[str] = []
        if not record.website:
            missing.append("website")
        if not record.country:
            missing.append("country")
        if not record.best_contact_channels.emails:
            missing.append("emails")
        if not record.best_contact_channels.phones:
            missing.append("phones")
        if not record.best_contact_channels.whatsapp:
            missing.append("whatsapp")
        if not record.best_contact_channels.linkedin:
            missing.append("linkedin")
        if not record.best_contact_channels.contact_forms:
            missing.append("contact_forms")
        return missing

    def _build_final_report(self) -> str:
        lines: List[str] = []
        lines.append(f"# 联系方式搜索报告")
        lines.append("")
        lines.append(f"- 用户查询：{self.state.user_query}")
        lines.append(f"- 执行轮次：{self.state.round_index}")
        lines.append(f"- 停止原因：{self.state.stop_reason or 'completed'}")
        lines.append(f"- 累计已搜索公司数：{len(self.state.already_seen_companies)}")
        lines.append(f"- 最终保留公司数：{len(self.state.final_company_records)}")
        lines.append("")

        if self.state.final_company_records:
            lines.append("## 公司清单")
            lines.append("")
            for record in self.state.final_company_records:
                lines.append(f"### {record.company_name}")
                lines.append(f"- 国家：{record.country or '未知'}")
                lines.append(f"- 官网：{record.website or '未找到'}")
                lines.append(f"- 完整度：{record.completeness_status}")
                lines.append(f"- 证据质量：{record.evidence_quality}")
                lines.append(
                    f"- 邮箱：{', '.join(record.best_contact_channels.emails) or '未找到'}"
                )
                lines.append(
                    f"- 电话：{', '.join(record.best_contact_channels.phones) or '未找到'}"
                )
                lines.append(
                    f"- WhatsApp：{', '.join(record.best_contact_channels.whatsapp) or '未找到'}"
                )
                lines.append(
                    f"- LinkedIn：{', '.join(record.best_contact_channels.linkedin) or '未找到'}"
                )
                lines.append(
                    f"- 联系表单：{', '.join(record.best_contact_channels.contact_forms) or '未找到'}"
                )
                if record.best_contact_channels.other_channels:
                    lines.append(
                        f"- 其他渠道：{', '.join(record.best_contact_channels.other_channels)}"
                    )
                if record.missing_fields:
                    lines.append(f"- 仍缺字段：{', '.join(record.missing_fields)}")
                lines.append("")
        else:
            lines.append("## 公司清单")
            lines.append("")
            lines.append("本次没有得到足够可靠的公司联系方式结果。")
            lines.append("")

        if self.state.round_reports:
            lines.append("## 各轮整理摘要")
            lines.append("")
            lines.append("\n\n---\n\n".join(self.state.round_reports))
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _save_outputs(self) -> None:
        os.makedirs("output", exist_ok=True)

        result_payload = {
            "user_query": self.state.user_query,
            "current_year": self.state.current_year,
            "max_rounds": self.state.max_rounds,
            "max_companies_per_round": self.state.max_companies_per_round,
            "round_index": self.state.round_index,
            "search_mode": self.state.search_mode,
            "should_continue": self.state.should_continue,
            "stop_reason": self.state.stop_reason,
            "already_seen_companies": self.state.already_seen_companies,
            "searched_companies_history": self.state.searched_companies_history,
            "all_known_companies": self.state.all_known_companies,
            "next_round_deep_search_companies": [
                target.model_dump() for target in self.state.next_round_deep_search_companies
            ],
            "final_company_records": [
                record.model_dump() for record in self.state.final_company_records
            ],
            "latest_crew_output": self.state.latest_crew_output,
            "organizer_memory_log": self.state.organizer_memory_log,
        }

        with open("output/contact_discovery_result.json", "w", encoding="utf-8") as f:
            json.dump(result_payload, f, ensure_ascii=False, indent=2)

        with open("output/contact_discovery_report.md", "w", encoding="utf-8") as f:
            f.write(self.state.final_report_markdown or self._build_final_report())


# =========================
# CLI helpers
# =========================


def kickoff(inputs: Optional[Dict[str, Any]] = None) -> Any:
    """Run the flow.

    Example:
        kickoff({
            "user_query": "10 EV battery suppliers in Nigeria",
            "max_rounds": 4,
            "max_companies_per_round": 8,
        })
    """
    flow = ContactDiscoveryFlow()
    return flow.kickoff(inputs=inputs or {})


def plot() -> None:
    """Generate an HTML flow graph."""
    flow = ContactDiscoveryFlow()
    flow.plot("ContactDiscoveryFlow")


if __name__ == "__main__":
    kickoff()
