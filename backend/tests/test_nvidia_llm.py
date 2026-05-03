from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.services import nvidia_llm


def _response(content: str | None, finish_reason: str | None = "stop") -> SimpleNamespace:
    message = SimpleNamespace(content=content, refusal=None)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(
        choices=[choice],
        usage=SimpleNamespace(completion_tokens=len(content or "")),
    )


class _FakeCompletions:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = responses
        self.max_tokens_seen: list[int] = []

    def create(self, **kwargs):
        self.max_tokens_seen.append(kwargs["max_tokens"])
        if not self._responses:
            raise AssertionError("no fake LLM responses left")
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.completions = _FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


class ChatCompleteSyncTest(TestCase):
    def test_retries_empty_content(self) -> None:
        client = _FakeClient([_response("   "), _response("usable content")])
        with (
            patch.object(nvidia_llm, "get_client", return_value=client),
            patch.object(nvidia_llm, "_retry_delay_seconds", return_value=0.0),
            patch.object(nvidia_llm.log, "warning"),
        ):
            result = nvidia_llm.chat_complete_sync("prompt", max_retries=1)

        self.assertEqual(result, "usable content")
        self.assertEqual(len(client.completions.max_tokens_seen), 2)

    def test_retries_truncated_content_with_larger_token_budget(self) -> None:
        client = _FakeClient([_response("partial", "length"), _response("complete")])
        with (
            patch.object(nvidia_llm, "get_client", return_value=client),
            patch.object(nvidia_llm, "_retry_delay_seconds", return_value=0.0),
            patch.object(nvidia_llm.log, "warning"),
        ):
            result = nvidia_llm.chat_complete_sync(
                "prompt",
                max_tokens=100,
                max_retries=1,
                retry_max_tokens=300,
            )

        self.assertEqual(result, "complete")
        self.assertEqual(client.completions.max_tokens_seen, [100, 300])

    def test_retries_validator_failure(self) -> None:
        client = _FakeClient([_response("bad"), _response("good table")])

        def validator(text: str) -> None:
            if "good" not in text:
                raise ValueError("missing expected marker")

        with (
            patch.object(nvidia_llm, "get_client", return_value=client),
            patch.object(nvidia_llm, "_retry_delay_seconds", return_value=0.0),
            patch.object(nvidia_llm.log, "warning"),
        ):
            result = nvidia_llm.chat_complete_sync(
                "prompt",
                max_retries=1,
                validators=[validator],
            )

        self.assertEqual(result, "good table")
        self.assertEqual(len(client.completions.max_tokens_seen), 2)


class ValidateChatResponseTest(TestCase):
    def test_rejects_missing_choices(self) -> None:
        with self.assertRaises(nvidia_llm.LLMEmptyResponseError):
            nvidia_llm._validate_chat_response(SimpleNamespace(choices=[]), 100)

    def test_rejects_length_finish_reason(self) -> None:
        with self.assertRaises(nvidia_llm.LLMTruncatedResponseError):
            nvidia_llm._validate_chat_response(_response("partial", "length"), 100)
