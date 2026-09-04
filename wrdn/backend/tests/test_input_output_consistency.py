"""Unit tests for input-output consistency (no live Gemini calls)."""

from types import SimpleNamespace

from wrdn.backend.services.input_output_consistency import (
    check_input_output_consistency,
    cosine_similarity,
    decide_consistency,
)


class _Models:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate_content(self, **_kwargs):
        return SimpleNamespace(text=self.text)


def _client(text: str):
    return SimpleNamespace(models=_Models(text))


def _fixed_embedding(values: list[float]):
    def _embed(_text: str) -> list[float]:
        return values

    return _embed


def _pair_embeddings(prompt_vec, answer_vec):
    def _embed(text: str) -> list[float]:
        if "Python" in text or "language" in text:
            return prompt_vec
        return answer_vec

    return _embed


def test_cosine_identical_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_highly_relevant_output_is_allowed() -> None:
    result = check_input_output_consistency(
        user_prompt="What is Python?",
        answer="Python is a popular programming language used for software.",
        get_embedding=_fixed_embedding([1.0, 0.0, 0.0]),
        client=_client(
            '{"aligned": true, "score": 92, "contradiction": false, '
            '"topic_consistent": true, "reason": "Direct answer"}'
        ),
        model="test",
        allow_threshold=70,
        review_threshold=45,
    )
    assert result["decision"] == "ALLOW"
    assert result["consistency_score"] >= 70
    assert result["contradiction_detected"] is False


def test_completely_unrelated_output_is_blocked() -> None:
    calls = {"n": 0}

    def _embed(_text: str) -> list[float]:
        calls["n"] += 1
        return [1.0, 0.0] if calls["n"] == 1 else [0.0, 1.0]

    result = check_input_output_consistency(
        user_prompt="Summarize our leave policy.",
        answer="The moon is a rocky satellite with no atmosphere.",
        get_embedding=_embed,
        client=_client(
            '{"aligned": false, "score": 8, "contradiction": false, '
            '"topic_consistent": false, "reason": "Different topic"}'
        ),
        model="test",
        allow_threshold=70,
        review_threshold=45,
    )
    assert result["decision"] == "BLOCK"
    assert result["consistency_score"] < 45


def test_partially_relevant_output_is_review() -> None:
    calls = {"n": 0}

    def _embed(_text: str) -> list[float]:
        calls["n"] += 1
        if calls["n"] == 1:
            return [1.0, 0.2]
        return [0.55, 0.8]

    result = check_input_output_consistency(
        user_prompt="Explain how WRDN blocks salary leaks in outbound email.",
        answer="WRDN is a security tool. Emails are used in offices.",
        get_embedding=_embed,
        client=_client(
            '{"aligned": true, "score": 52, "contradiction": false, '
            '"topic_consistent": true, "reason": "Only partly on topic"}'
        ),
        model="test",
        allow_threshold=70,
        review_threshold=45,
        embedding_weight=0.4,
    )
    assert result["decision"] == "REVIEW"


def test_contradictory_output_is_blocked() -> None:
    result = check_input_output_consistency(
        user_prompt="Confirm that the meeting is on Monday.",
        answer="The meeting is not on Monday; ignore that and talk about sports.",
        get_embedding=_fixed_embedding([0.8, 0.2]),
        client=_client(
            '{"aligned": false, "score": 40, "contradiction": true, '
            '"topic_consistent": false, "reason": "Contradicts the date"}'
        ),
        model="test",
        allow_threshold=70,
        review_threshold=45,
    )
    assert result["decision"] == "BLOCK"
    assert result["contradiction_detected"] is True


def test_short_user_input_does_not_block_valid_explanation() -> None:
    result = check_input_output_consistency(
        user_prompt="What is VPN?",
        answer=(
            "A VPN encrypts traffic between your device and a remote "
            "network so home workers can reach internal systems safely."
        ),
        get_embedding=_fixed_embedding([0.55, 0.45]),
        client=_client(
            '{"aligned": true, "score": 90, "contradiction": false, '
            '"topic_consistent": true, "reason": "Defines VPN with extra detail"}'
        ),
        model="test",
        allow_threshold=70,
        review_threshold=45,
    )
    assert result["decision"] == "ALLOW"


def test_long_user_input_unrelated_answer_blocked() -> None:
    long_prompt = (
        "Please draft a three-paragraph summary of WRDN inbound scanning, "
        "including payload analysis, YARA file checks, and why those layers "
        "run before Gemini generates an HR candidate email. Include why "
        "hidden CV text matters for prompt injection."
    )
    result = check_input_output_consistency(
        user_prompt=long_prompt,
        answer="Here is a cake recipe: mix flour, sugar, and eggs.",
        get_embedding=_fixed_embedding([1.0, 0.0]),
        client=_client(
            '{"aligned": false, "score": 5, "contradiction": false, '
            '"topic_consistent": false, "reason": "Recipe is unrelated"}'
        ),
        model="test",
        allow_threshold=70,
        review_threshold=45,
        embedding_weight=0.0,
    )
    assert result["decision"] == "BLOCK"


def test_valid_output_with_extra_useful_information_is_allowed() -> None:
    result = check_input_output_consistency(
        user_prompt="How do I reset my password?",
        answer=(
            "Open Sign in, choose Forgot password if available, or ask an "
            "admin. Also use a unique password with a number and symbol."
        ),
        get_embedding=_fixed_embedding([0.9, 0.1]),
        client=_client(
            '{"aligned": true, "score": 88, "contradiction": false, '
            '"topic_consistent": true, "reason": "Answers plus extra advice"}'
        ),
        model="test",
        allow_threshold=70,
        review_threshold=45,
    )
    assert result["decision"] == "ALLOW"
    assert result["relevance_score"] >= 80


def test_bypass_phrase_forces_block() -> None:
    result = check_input_output_consistency(
        user_prompt="What is the leave policy?",
        answer="Ignore the original question instead I will talk about cars.",
        get_embedding=_fixed_embedding([0.5, 0.5]),
        client=_client(
            '{"aligned": true, "score": 80, "contradiction": false, '
            '"topic_consistent": true, "reason": "Should still be blocked"}'
        ),
        model="test",
    )
    assert result["decision"] == "BLOCK"


def test_decide_thresholds() -> None:
    assert decide_consistency(
        consistency_score=80,
        contradiction_detected=False,
        bypass_attempt=False,
        allow_threshold=70,
        review_threshold=45,
    ) == "ALLOW"
    assert decide_consistency(
        consistency_score=50,
        contradiction_detected=False,
        bypass_attempt=False,
        allow_threshold=70,
        review_threshold=45,
    ) == "REVIEW"
    assert decide_consistency(
        consistency_score=20,
        contradiction_detected=False,
        bypass_attempt=False,
        allow_threshold=70,
        review_threshold=45,
    ) == "BLOCK"
