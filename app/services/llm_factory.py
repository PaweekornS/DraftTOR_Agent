import sys
import time
from openai import OpenAI
from app.config import settings

def get_llm_client(timeout: float = 40.0) -> OpenAI:
    """Returns an OpenAI-compatible client initialized from settings with timeout."""
    return OpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        timeout=timeout
    )

def call_llm(messages: list, temperature: float = None, max_tokens: int = 2048) -> str:
    """
    Convenience helper to call the configured LLM.
    Passes reasoning effort: none to turn off verbose thinking scratchpad on OpenRouter reasoning models,
    delivering instant direct text responses.
    """
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    primary_model = settings.LLM_MODEL_NAME
    fallback_model = "qwen/qwen-2.5-7b-instruct"

    models_to_try = [primary_model]
    if primary_model != fallback_model:
        models_to_try.append(fallback_model)

    last_error = None
    for model_name in models_to_try:
        try:
            print(f"    [LLM] Calling model: {model_name}...", flush=True)
            client = get_llm_client(timeout=40.0)
            
            # Pass reasoning: effort: none to bypass scratchpad loop
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temp,
                max_tokens=max_tokens,
                extra_body={"reasoning": {"effort": "none"}}
            )
            choice = response.choices[0]
            content = choice.message.content
            if content and content.strip():
                print(f"    [LLM] Received {len(content)} chars from {model_name}.", flush=True)
                return content.strip()
            
            reasoning = getattr(choice.message, 'reasoning', None)
            if reasoning and reasoning.strip():
                print(f"    [LLM] Extracted from reasoning ({len(reasoning)} chars).", flush=True)
                return reasoning.strip()

        except Exception as e:
            print(f"    [LLM Warning] Call failed for {model_name}: {e}. Retrying...", flush=True)
            last_error = e

    if last_error:
        print(f"    [LLM Error] All models failed. Error: {last_error}", flush=True)
    return ""
