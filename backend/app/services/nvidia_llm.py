from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI

from ..config import settings

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
log = logging.getLogger(__name__)

ResponseValidator = Callable[[str], None]


class LLMResponseError(RuntimeError):
    """Raised when the provider returned an unusable completion."""


class LLMEmptyResponseError(LLMResponseError):
    """Raised when the completion has no usable text content."""


class LLMTruncatedResponseError(LLMResponseError):
    """Raised when the provider reports or strongly suggests truncation."""


class LLMResponseValidationError(LLMResponseError):
    """Raised when caller-specific response validation fails."""


def load_prompt(name: str) -> str:
    p = _PROMPTS_DIR / name
    return p.read_text(encoding="utf-8")


_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.NVIDIA_API_KEY:
            raise RuntimeError(
                "NVIDIA_API_KEY is not set. Configure it in backend/.env."
            )
        _client = OpenAI(
            api_key=settings.NVIDIA_API_KEY,
            base_url=settings.NVIDIA_BASE_URL,
        )
    return _client


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
                continue
            if isinstance(part, dict):
                text = part.get("text")
            else:
                text = getattr(part, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)
    return str(content)


def _validate_chat_response(resp: Any, requested_max_tokens: Optional[int]) -> str:
    choices = getattr(resp, "choices", None)
    if not choices:
        raise LLMEmptyResponseError("LLM response has no choices")

    choice = choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason == "length":
        raise LLMTruncatedResponseError("LLM response was truncated: finish_reason=length")
    if finish_reason in {"content_filter", "tool_calls", "function_call"}:
        raise LLMResponseError(f"LLM response stopped unexpectedly: finish_reason={finish_reason}")

    message = getattr(choice, "message", None)
    if message is None:
        raise LLMEmptyResponseError("LLM response choice has no message")

    refusal = getattr(message, "refusal", None)
    if refusal:
        raise LLMResponseError(f"LLM response was refused: {str(refusal)[:200]}")

    text = _content_to_text(getattr(message, "content", None)).strip()
    if not text:
        raise LLMEmptyResponseError("LLM response content is empty")

    usage = getattr(resp, "usage", None)
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
    if (
        requested_max_tokens is not None
        and isinstance(completion_tokens, int)
        and completion_tokens >= requested_max_tokens
        and finish_reason != "stop"
    ):
        raise LLMTruncatedResponseError(
            "LLM response likely hit max_tokens: "
            f"completion_tokens={completion_tokens}, max_tokens={requested_max_tokens}, "
            f"finish_reason={finish_reason}"
        )

    return text


def _run_validators(text: str, validators: Optional[Sequence[ResponseValidator]]) -> None:
    for validator in validators or ():
        try:
            validator(text)
        except LLMResponseError:
            raise
        except Exception as exc:
            raise LLMResponseValidationError(str(exc)) from exc


def _retry_delay_seconds(attempt_index: int) -> float:
    base = max(settings.LLM_RETRY_INITIAL_DELAY_SECONDS, 0.0)
    cap = max(settings.LLM_RETRY_MAX_DELAY_SECONDS, base)
    delay = min(cap, base * (2 ** max(attempt_index - 1, 0)))
    if delay <= 0:
        return 0.0
    return delay + random.uniform(0.0, min(delay * 0.25, 1.0))


def _bump_max_tokens(
    current: Optional[int],
    retry_max_tokens: Optional[int],
) -> Optional[int]:
    if current is None:
        return None
    cap = retry_max_tokens or settings.LLM_RETRY_MAX_TOKENS
    if cap <= current:
        return current
    return min(cap, max(current + 1024, current * 2))


def chat_complete_sync(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    max_retries: Optional[int] = None,
    retry_max_tokens: Optional[int] = None,
    validators: Optional[Sequence[ResponseValidator]] = None,
) -> str:
    client = get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    attempts = 1 + max(max_retries if max_retries is not None else settings.LLM_MAX_RETRIES, 0)
    request_max_tokens = max_tokens or settings.LLM_MAX_TOKENS
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            resp = client.chat.completions.create(
                model=model or settings.LLM_MODEL,
                messages=messages,
                temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
                max_tokens=request_max_tokens,
            )
            text = _validate_chat_response(resp, request_max_tokens)
            _run_validators(text, validators)
            return text
        except Exception as exc:
            if isinstance(exc, RuntimeError) and "NVIDIA_API_KEY is not set" in str(exc):
                raise
            last_exc = exc
            if attempt >= attempts:
                break
            if isinstance(exc, LLMTruncatedResponseError):
                request_max_tokens = _bump_max_tokens(request_max_tokens, retry_max_tokens)
            delay = _retry_delay_seconds(attempt)
            log.warning(
                "LLM completion attempt %d/%d failed; retrying in %.2fs: %s",
                attempt,
                attempts,
                delay,
                exc,
            )
            if delay:
                time.sleep(delay)

    assert last_exc is not None
    raise last_exc


async def chat_complete(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    max_retries: Optional[int] = None,
    retry_max_tokens: Optional[int] = None,
    validators: Optional[Sequence[ResponseValidator]] = None,
) -> str:
    return await asyncio.to_thread(
        chat_complete_sync,
        prompt,
        system=system,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        retry_max_tokens=retry_max_tokens,
        validators=validators,
    )
