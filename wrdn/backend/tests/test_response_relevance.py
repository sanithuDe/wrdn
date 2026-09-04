"""Unit tests for the response relevance stage (no network calls)."""

from types import SimpleNamespace

from wrdn.backend.services.response_relevance import (
    _extract_json,
    check_response_relevance,
)


class _Models:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate_content(self, **_kwargs):
        return SimpleNamespace(text=self.text)


def _client(text: str):
    return SimpleNamespace(models=_Models(text))


def test_extracts_markdown_wrapped_json() -> None:
    result = _extract_json('```json\n{"aligned": true, "score": 91}\n```')
    assert result["aligned"] is True
    assert result["score"] == 91


def test_relevant_answer_is_aligned() -> None:
    result = check_response_relevance(
        client=_client('{"aligned": true, "score": 88, "reason": "Direct"}'),
        model="test-model",
        user_prompt="What is Python?",
        answer="Python is a programming language.",
        threshold=65,
    )
    assert result["aligned"] is True
    assert result["score"] == 88


def test_low_score_overrides_model_boolean() -> None:
    result = check_response_relevance(
        client=_client('{"aligned": true, "score": 30, "reason": "Off topic"}'),
        model="test-model",
        user_prompt="What is Python?",
        answer="The moon is rocky.",
        threshold=65,
    )
    assert result["aligned"] is False
