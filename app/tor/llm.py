"""Structured-output wrapper: ask for JSON, validate with Pydantic, retry once with the error."""
import json
import re
from typing import Callable, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.services.llm_factory import call_llm
from app.tor.concurrency import limited

LLMFn = Callable[[List[dict]], str]
T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")


def _extract_json(text: str) -> str:
    m = _FENCE.search(text)
    if m:
        return m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        return text
    end = max(text.rfind("}"), text.rfind("]"))
    return text[start:end + 1]


def call_structured(
    prompt: str,
    model: Type[T],
    llm: Optional[LLMFn] = None,
    max_attempts: int = 2,
) -> Optional[T]:
    """Returns a validated model, or None if every attempt failed (caller decides the fallback)."""
    llm = limited(llm or call_llm)  # at most TOR_LLM_CONCURRENCY requests in flight
    schema = json.dumps(model.model_json_schema(), ensure_ascii=False)
    messages = [{
        "role": "user",
        "content": f"{prompt}\n\nตอบเป็น JSON เท่านั้น ตาม JSON Schema นี้ ห้ามมีข้อความอื่น:\n{schema}",
    }]
    for _ in range(max_attempts):
        raw = llm(messages)
        if not raw:
            continue
        try:
            return model.model_validate_json(_extract_json(raw))
        except (ValidationError, ValueError) as e:
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"JSON ไม่ถูกต้องตาม schema: {str(e)[:500]}\nโปรดตอบใหม่เป็น JSON ที่ถูกต้องเท่านั้น"},
            ]
    return None
