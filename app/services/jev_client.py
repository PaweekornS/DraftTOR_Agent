"""Client for TypeSafe Jev, a structured decision model served on OpenRouter's decisions endpoint.

Jev does not use chat/completions. A request carries shared `state` (string or object) and a
record of `questions`; `choice` questions return the chosen option plus softmax `probabilities`.
The API is alpha and undocumented publicly; the shapes below were confirmed against the live endpoint.
"""
import time
from typing import Any, Callable, Dict

import httpx

from app.config import settings

DecideFn = Callable[[Dict[str, Any], Dict[str, Dict[str, Any]]], Dict[str, Dict[str, Any]]]


def decide(state: Dict[str, Any], questions: Dict[str, Dict[str, Any]],
           retries: int = 2, timeout: float = 30.0) -> Dict[str, Dict[str, Any]]:
    """Returns the `answers` record keyed by question id. Raises after the last failed attempt."""
    body = {"model": settings.JEV_MODEL_NAME, "state": state, "questions": questions}
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    last: Exception = RuntimeError("no attempt made")
    for attempt in range(retries + 1):
        try:
            r = httpx.post(settings.JEV_DECISIONS_URL, headers=headers, json=body, timeout=timeout)
            r.raise_for_status()
            return r.json()["answers"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            last = e
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    raise last
