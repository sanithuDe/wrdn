import json
from typing import Any


SUPPORTED_CATEGORIES = {
    "credentials",
    "personal_information",
    "financial_records",
    "customer_information",
    "employee_information",
    "internal_documents",
    "source_code",
    "malware",
    "violence",
    "illegal_activity",
}

SUPPORTED_PATTERN_IDS = {
    "api_key",
    "password",
    "access_token",
    "private_key",
    "email_address",
    "phone_number",
    "sri_lankan_nic",
    "bank_account",
}

SUPPORTED_ACTIONS = {
    "ALLOW",
    "REDACT",
    "BLOCK",
}

REQUIRED_FIELDS = {
    "client_id",
    "policy_name",
    "risk_threshold",
    "embedding_threshold",
    "blocked_categories",
    "sensitive_pattern_ids",
    "allowed_actions",
    "blocked_response",
    "explanation",
    "admin_warnings",
}

OPTIONAL_LIST_FIELDS = {
    "allowed_secret_names",
    "blocked_secret_names",
    "allowed_employee_salary_names",
    "blocked_employee_salary_names",
}

FORBIDDEN_CODE_MARKERS = (
    "#!/bin/",
    "import os",
    "subprocess.",
    "os.system(",
    "eval(",
    "exec(",
    "powershell ",
    "sudo ",
    "rm -rf",
)


def validate_policy(
    policy: Any,
    expected_client_id: str | None = None,
) -> list[str]:
    """
    Validate an AI-generated client security policy.

    Returns an empty list when the policy is valid.
    Otherwise, it returns a list of validation errors.
    """

    errors: list[str] = []

    if not isinstance(policy, dict):
        return [
            "Policy must be a JSON object."
        ]

    missing_fields = sorted(
        REQUIRED_FIELDS - set(policy)
    )

    if missing_fields:
        errors.append(
            "Missing fields: "
            + ", ".join(missing_fields)
        )

    if (
        expected_client_id
        and policy.get("client_id")
        != expected_client_id
    ):
        errors.append(
            "The generated policy belongs to a different client."
        )

    policy_name = policy.get("policy_name")

    if (
        not isinstance(policy_name, str)
        or not policy_name.strip()
    ):
        errors.append(
            "policy_name is required."
        )

    risk_threshold = policy.get(
        "risk_threshold"
    )

    if (
        isinstance(risk_threshold, bool)
        or not isinstance(
            risk_threshold,
            int,
        )
        or not 0 <= risk_threshold <= 100
    ):
        errors.append(
            "risk_threshold must be an integer from 0 to 100."
        )

    embedding_threshold = policy.get(
        "embedding_threshold"
    )

    if (
        isinstance(embedding_threshold, bool)
        or not isinstance(
            embedding_threshold,
            (int, float),
        )
        or not 0.0
        <= embedding_threshold
        <= 1.0
    ):
        errors.append(
            "embedding_threshold must be between 0.0 and 1.0."
        )

    categories = policy.get(
        "blocked_categories"
    )

    if not isinstance(categories, list):
        errors.append(
            "blocked_categories must be a list."
        )

    else:
        unsupported_categories = (
            set(categories)
            - SUPPORTED_CATEGORIES
        )

        if unsupported_categories:
            errors.append(
                "Unsupported categories: "
                + ", ".join(
                    sorted(
                        unsupported_categories
                    )
                )
            )

    pattern_ids = policy.get(
        "sensitive_pattern_ids"
    )

    if not isinstance(pattern_ids, list):
        errors.append(
            "sensitive_pattern_ids must be a list."
        )

    else:
        unsupported_patterns = (
            set(pattern_ids)
            - SUPPORTED_PATTERN_IDS
        )

        if unsupported_patterns:
            errors.append(
                "Unsupported pattern IDs: "
                + ", ".join(
                    sorted(
                        unsupported_patterns
                    )
                )
            )

    actions = policy.get(
        "allowed_actions"
    )

    if (
        not isinstance(actions, list)
        or not actions
        or not set(actions).issubset(
            SUPPORTED_ACTIONS
        )
    ):
        errors.append(
            "Only ALLOW, REDACT and BLOCK actions are supported."
        )

    blocked_response = policy.get(
        "blocked_response"
    )

    if (
        not isinstance(
            blocked_response,
            str,
        )
        or not blocked_response.strip()
    ):
        errors.append(
            "blocked_response is required."
        )

    if not isinstance(
        policy.get("admin_warnings"),
        list,
    ):
        errors.append(
            "admin_warnings must be a list."
        )

    for field_name in OPTIONAL_LIST_FIELDS:
        value = policy.get(field_name)

        if value is None:
            continue

        if not isinstance(value, list):
            errors.append(
                f"{field_name} must be a list."
            )
            continue

        if not all(
            isinstance(item, str)
            and item.strip()
            for item in value
        ):
            errors.append(
                f"{field_name} must contain non-empty strings."
            )

    serialized_policy = json.dumps(
        policy,
        ensure_ascii=False,
    ).lower()

    for marker in FORBIDDEN_CODE_MARKERS:
        if marker in serialized_policy:
            errors.append(
                "Executable-code marker is not allowed: "
                + marker
            )

    return errors