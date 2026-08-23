import json
import re
from typing import Any

from google import genai

from wrdn.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
)


def build_policy_judge_prompt(
    user_prompt: str,
    raw_ai_output: str,
    policy: dict[str, Any],
) -> str:
    blocked_categories = policy.get(
        "blocked_categories",
        [],
    )
    sensitive_pattern_ids = policy.get(
        "sensitive_pattern_ids",
        [],
    )
    allowed_secret_names = policy.get(
        "allowed_secret_names",
        [],
    )
    blocked_secret_names = policy.get(
        "blocked_secret_names",
        [],
    )
    allowed_employee_salary_names = policy.get(
        "allowed_employee_salary_names",
        [],
    )
    blocked_employee_salary_names = policy.get(
        "blocked_employee_salary_names",
        [],
    )
    explanation = policy.get(
        "explanation",
        "",
    )
    blocked_response = policy.get(
        "blocked_response",
        "",
    )
    policy_name = policy.get(
        "policy_name",
        "",
    )

    return f"""
You are the WRDN policy judge LLM.

Decide whether the USER REQUEST is permitted under
the active client security policy.

Important:
- Judge the USER QUESTION first, not only the assistant text.
- If the user asks for data the policy forbids, verdict is BLOCK
  even when the assistant refused and leaked nothing.
- ALLOW only when the request itself is permitted and the
  assistant output does not leak forbidden data.
- Do not invent extra restrictions.
- Return one valid JSON object only.

Decision rules:
1. If the user asks for a secret/token in blocked_secret_names,
   verdict must be BLOCK.
2. If the user asks for a secret/token in allowed_secret_names,
   and output reveals it or correctly says missing, ALLOW.
3. If the user asks for salary of someone in
   blocked_employee_salary_names, verdict must be BLOCK.
4. If the user asks for salary of someone in
   allowed_employee_salary_names, ALLOW if no other leak.
5. If selective salary lists exist and the asked employee is
   not in allowed_employee_salary_names, BLOCK salary questions.
6. If blocked_categories contains credentials/financial/
   personal and the request targets that blocked data without
   an explicit allow-list exception, BLOCK.
7. Safe directory questions (name/email/role only) are ALLOW
   when not otherwise restricted.
8. A model refusal does NOT turn a forbidden request into ALLOW.

Active policy:
policy_name: {policy_name}
blocked_categories: {json.dumps(blocked_categories)}
sensitive_pattern_ids: {json.dumps(sensitive_pattern_ids)}
allowed_secret_names: {json.dumps(allowed_secret_names)}
blocked_secret_names: {json.dumps(blocked_secret_names)}
allowed_employee_salary_names: {json.dumps(allowed_employee_salary_names)}
blocked_employee_salary_names: {json.dumps(blocked_employee_salary_names)}
explanation: {explanation}
blocked_response: {blocked_response}

User question:
{user_prompt}

Assistant raw output:
{raw_ai_output}

Required JSON:
{{
  "verdict": "ALLOW",
  "risk_score": 0,
  "reason": "short reason"
}}

verdict must be exactly ALLOW or BLOCK.
risk_score must be an integer from 0 to 100.
""".strip()


def parse_judge_response(
    response_text: str,
) -> dict[str, Any]:
    cleaned = (response_text or "").strip()

    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        cleaned,
        re.DOTALL | re.IGNORECASE,
    )

    if fenced:
        cleaned = fenced.group(1)

    parsed = json.loads(cleaned)

    if not isinstance(parsed, dict):
        raise ValueError(
            "Policy judge response must be a JSON object."
        )

    verdict = str(
        parsed.get("verdict", "")
    ).strip().upper()

    if verdict not in {"ALLOW", "BLOCK"}:
        raise ValueError(
            "Policy judge verdict must be ALLOW or BLOCK."
        )

    risk_score = parsed.get("risk_score", 0)

    if (
        isinstance(risk_score, bool)
        or not isinstance(risk_score, int)
        or not 0 <= risk_score <= 100
    ):
        risk_score = 100 if verdict == "BLOCK" else 20

    reason = str(
        parsed.get("reason", "")
    ).strip() or (
        "Policy judge returned no reason."
    )

    return {
        "verdict": verdict,
        "risk_score": risk_score,
        "reason": reason,
    }


def judge_output_against_policy(
    user_prompt: str,
    raw_ai_output: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """
    Ask Gemini to judge the user request and output
    using the active policy allow/block rules.
    """

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=build_policy_judge_prompt(
            user_prompt=user_prompt,
            raw_ai_output=raw_ai_output,
            policy=policy,
        ),
    )

    response_text = getattr(
        response,
        "text",
        "",
    )

    if not response_text:
        raise RuntimeError(
            "Policy judge returned an empty response."
        )

    judged = parse_judge_response(
        response_text
    )

    blocked = judged["verdict"] == "BLOCK"
    blocked_response = policy.get(
        "blocked_response",
        "This output was blocked by the WRDN security policy.",
    )

    return {
        "allowed": not blocked,
        "status": (
            "BLOCKED" if blocked else "ALLOWED"
        ),
        "risk_score": judged["risk_score"],
        "layer": "Policy Judge LLM",
        "reason": judged["reason"],
        "final_output": (
            blocked_response
            if blocked
            else raw_ai_output
        ),
    }
