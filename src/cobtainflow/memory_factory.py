from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

from crewai import Memory, LLM
from openai import OpenAI


class CleanJSONLLM(LLM):
    """Custom LLM wrapper that strips markdown code blocks from JSON responses
    and intercepts response_format for providers that don't support it natively."""

    def call(
        self,
        messages: List[Any],
        tools: Optional[List[Any]] = None,
        callbacks: Optional[List[Any]] = None,
        available_functions: Optional[dict] = None,
        response_format: Optional[Any] = None,
    ) -> str:

        result = super().call(
            messages=messages,
            tools=tools,
            callbacks=callbacks,
            available_functions=available_functions,
        )

        if isinstance(result, str):
            cleaned = self._clean_json_output(result)
            return cleaned

        return result

    def _clean_json_output(self, text: str) -> str:
        """Clean and validate JSON output from LLM."""
        if not isinstance(text, str):
            return text

        # Handle empty or whitespace-only responses
        stripped = text.strip()
        if not stripped or stripped in ('\n', '\r\n', '\r', '\t', '""', "''"):
            # Return valid empty JSON object instead of failing
            return "{}"

        cleaned = stripped

        # Remove markdown code blocks
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        # If empty after cleaning, return empty JSON
        if not cleaned:
            return "{}"

        # If it looks like JSON, validate it
        if cleaned.startswith("{") or cleaned.startswith("["):
            try:
                json.loads(cleaned)
                return cleaned
            except json.JSONDecodeError:
                # Try to fix common JSON issues
                fixed = self._fix_common_json_issues(cleaned)
                try:
                    json.loads(fixed)
                    return fixed
                except json.JSONDecodeError:
                    pass

        return cleaned

    def _fix_common_json_issues(self, text: str) -> str:
        """Attempt to fix common JSON formatting issues."""
        # Remove trailing commas before closing braces/brackets
        text = re.sub(r',([\n\r\s\t]*[}\]])', r'\1', text)

        # Remove control characters except newlines and tabs
        text = re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1f]', '', text)

        # Try to fix unclosed strings by escaping newlines in strings
        # This is a last resort - just return as-is if still invalid
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            return text


def _ensure_crewai_storage_dir() -> None:
    """
    Ensure CREWAI_STORAGE_DIR is set to this project's local `memory/` folder.

    This keeps Flow memory and Crew memory in sync even if callers don't import
    `cobtainflow.main` (which also sets the env var).
    """
    if os.getenv("CREWAI_STORAGE_DIR"):
        return
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    custom_storage_dir = project_root / "memory"
    custom_storage_dir.mkdir(parents=True, exist_ok=True)
    os.environ["CREWAI_STORAGE_DIR"] = str(custom_storage_dir)


def _embedding_callable(texts: List[str]) -> List[List[float]]:
    dimensions = 1024
    try:
        client = OpenAI(
            api_key=os.getenv("EMBEDDING_API_KEY"),
            base_url=os.getenv("EMBEDDING_BASE_URL"),
        )
        batch_size = 10
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            completion = client.embeddings.create(
                model="text-embedding-v4",
                input=batch,
                dimensions=dimensions,
                encoding_format="float",
            )
            all_embeddings.extend([item.embedding for item in completion.data])
        return all_embeddings
    except Exception:
        return [[0.0] * dimensions for _ in texts]


@lru_cache(maxsize=1)
def get_shared_memory() -> Memory:
    """Return a process-wide unified Memory configured for this project."""
    _ensure_crewai_storage_dir()
    
    memory_llm = CleanJSONLLM(
        model="deepseek/deepseek-v3.2-exp-thinking",
        temperature=0.1,
        max_tokens=2000,
    )
    
    return Memory(
        llm=memory_llm,
        embedder=_embedding_callable,
    )

