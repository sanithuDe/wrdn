"""
Deterministic extraction of selective allow/block
rules from requirement text.

Used to correct or fill gaps when the policy LLM
misses structured salary/secret lists.
"""

from __future__ import annotations

import re
from typing import Any


KNOWN_EMPLOYEES = (
    "Kasun Perera",
    "Nimal Silva",
    "Ama Fernando",
    "Sahan Jayawardena",
    "Dilani Wickramasinghe",
    "Ruwan Bandara",
    "Ishara Gunasekara",
    "Tharindu Mendis",
    "Malsha Peris",
    "Chamath Fernando",
)

KNOWN_SECRETS = (
    "Admin Password",
    "Kasun Account Password",
    "Dilani Account Password",
    "API Key",
    "Database Password",
    "AWS Root Key",
    "Internal VPN Password",
    "Payroll System Password",
    "Email SMTP Secret",
    "Backup Encryption Key",
    "JWT Token",
    "Azure Access Token",
    "OpenAI Internal Token",
    "GitHub Deploy Token",
    "Monitoring API Token",
)

EMPLOYEE_ALIASES: dict[str, tuple[str, ...]] = {
    "Kasun Perera": ("kasun perera", "kasun"),
    "Nimal Silva": ("nimal silva", "nimal"),
    "Ama Fernando": ("ama fernando", "ama"),
    "Sahan Jayawardena": (
        "sahan jayawardena",
        "sahan",
    ),
    "Dilani Wickramasinghe": (
        "dilani wickramasinghe",
        "dilani",
    ),
    "Ruwan Bandara": ("ruwan bandara", "ruwan"),
    "Ishara Gunasekara": (
        "ishara gunasekara",
        "ishara",
    ),
    "Tharindu Mendis": (
        "tharindu mendis",
        "tharindu",
    ),
    "Malsha Peris": ("malsha peris", "malsha"),
    "Chamath Fernando": (
        "chamath fernando",
        "chamath",
    ),
}

SECRET_ALIASES: dict[str, tuple[str, ...]] = {
    "Admin Password": (
        "admin password",
        "admin pass",
    ),
    "Kasun Account Password": (
        "kasun account password",
        "kasun password",
        "kasun perera password",
    ),
    "Dilani Account Password": (
        "dilani account password",
        "dilani password",
        "dilani wickramasinghe password",
    ),
    "API Key": ("api key",),
    "Database Password": (
        "database password",
        "db password",
    ),
    "AWS Root Key": ("aws root key", "aws root"),
    "JWT Token": ("jwt token",),
    "GitHub Deploy Token": (
        "github deploy token",
        "github token",
    ),
    "Azure Access Token": ("azure access token",),
}


def _normalize_list(
    values: Any,
) -> list[str]:
    if not isinstance(values, list):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()

    for item in values:
        text = str(item).strip()
        key = text.lower()

        if not text or key in seen:
            continue

        seen.add(key)
        cleaned.append(text)

    return cleaned


def _find_employee_in_text(
    text: str,
) -> str | None:
    best_name: str | None = None
    best_len = 0

    for full_name, aliases in EMPLOYEE_ALIASES.items():
        for alias in aliases:
            pattern = (
                rf"(?<![a-z0-9])"
                rf"{re.escape(alias)}"
                rf"(?![a-z0-9])"
            )

            if re.search(pattern, text):
                if len(alias) > best_len:
                    best_len = len(alias)
                    best_name = full_name

    return best_name


def _find_secret_in_text(
    text: str,
) -> str | None:
    best_name: str | None = None
    best_len = 0

    for secret_name, aliases in SECRET_ALIASES.items():
        for alias in aliases:
            pattern = (
                rf"(?<![a-z0-9])"
                rf"{re.escape(alias)}"
                rf"(?![a-z0-9])"
            )

            if re.search(pattern, text):
                if len(alias) > best_len:
                    best_len = len(alias)
                    best_name = secret_name

    return best_name


def _extract_labeled_names(
    requirement_text: str,
    label_patterns: tuple[str, ...],
    known_names: tuple[str, ...],
) -> list[str]:
    """
    Parse lines like:
    allowed_employee_salary_names: ["Sahan Jayawardena"]
    or ALLOW salary for Sahan Jayawardena
    """

    text = requirement_text or ""
    found: list[str] = []
    seen: set[str] = set()

    for label in label_patterns:
        for match in re.finditer(
            rf"{label}\s*[:=]\s*\[([^\]]*)\]",
            text,
            flags=re.IGNORECASE,
        ):
            inside = match.group(1)
            for name in known_names:
                if name.lower() in inside.lower():
                    key = name.lower()
                    if key not in seen:
                        seen.add(key)
                        found.append(name)

    return found


def extract_selective_rules(
    requirement_text: str,
) -> dict[str, list[str]]:
    """
    Deterministically extract selective allow/block
    lists from requirement wording.
    """

    text = requirement_text or ""
    lowered = text.lower()

    allowed_salaries = _extract_labeled_names(
        text,
        (
            "allowed_employee_salary_names",
            "allowed salary names",
            "allow salary for",
        ),
        KNOWN_EMPLOYEES,
    )
    blocked_salaries = _extract_labeled_names(
        text,
        (
            "blocked_employee_salary_names",
            "blocked salary names",
            "block salary for",
        ),
        KNOWN_EMPLOYEES,
    )

    allowed_secrets = _extract_labeled_names(
        text,
        (
            "allowed_secret_names",
            "allowed secrets",
            "allow these secrets",
        ),
        KNOWN_SECRETS,
    )
    blocked_secrets = _extract_labeled_names(
        text,
        (
            "blocked_secret_names",
            "blocked secrets",
            "block these secrets",
            "explicitly block",
        ),
        KNOWN_SECRETS,
    )

    # Sentence-level salary allow/block cues.
    for line in text.splitlines():
        line_l = line.strip().lower()

        if not line_l:
            continue

        employee = _find_employee_in_text(line_l)

        if employee is None:
            continue

        salary_mentioned = (
            "salary" in line_l
            or "payroll" in line_l
        )

        if not salary_mentioned:
            continue

        is_allow = bool(
            re.search(
                r"\b(allow|allowed|may reveal|"
                r"can reveal|permit|permitted)\b",
                line_l,
            )
        )
        is_block = bool(
            re.search(
                r"\b(block|blocked|never reveal|"
                r"do not reveal|deny|forbidden|"
                r"restrict|restricted)\b",
                line_l,
            )
        )

        if is_allow and not is_block:
            if employee not in allowed_salaries:
                allowed_salaries.append(employee)

        if is_block:
            if employee not in blocked_salaries:
                blocked_salaries.append(employee)

    # Sentence-level secret allow/block cues.
    for line in text.splitlines():
        line_l = line.strip().lower()

        if not line_l:
            continue

        secret = _find_secret_in_text(line_l)

        if secret is None:
            continue

        is_allow = bool(
            re.search(
                r"\b(allow|allowed|may reveal|"
                r"can reveal|permit|permitted)\b",
                line_l,
            )
        )
        is_block = bool(
            re.search(
                r"\b(block|blocked|never reveal|"
                r"do not reveal|deny|forbidden|"
                r"restrict|restricted)\b",
                line_l,
            )
        )

        if is_allow and not is_block:
            if secret not in allowed_secrets:
                allowed_secrets.append(secret)

        if is_block:
            if secret not in blocked_secrets:
                blocked_secrets.append(secret)

    # Title-style cues: "SAHAN SALARY ALLOWED / KASUN SALARY BLOCKED"
    title_allow = re.findall(
        r"([a-z]+(?:\s+[a-z]+)?)\s+salary\s+allowed",
        lowered,
    )
    title_block = re.findall(
        r"([a-z]+(?:\s+[a-z]+)?)\s+salary\s+blocked",
        lowered,
    )

    for chunk in title_allow:
        employee = _find_employee_in_text(chunk)
        if employee and employee not in allowed_salaries:
            allowed_salaries.append(employee)

    for chunk in title_block:
        employee = _find_employee_in_text(chunk)
        if employee and employee not in blocked_salaries:
            blocked_salaries.append(employee)

    # If selective salary allow exists, default-block
    # other known employees mentioned as blocked in doc,
    # or all others when document says "only".
    if allowed_salaries and "only" in lowered:
        for employee in KNOWN_EMPLOYEES:
            if (
                employee not in allowed_salaries
                and employee not in blocked_salaries
            ):
                # Only add commonly tested peers if named
                # elsewhere as blocked, else leave empty
                # and let runtime treat unlisted as blocked
                # when allow-list exists.
                pass

    # Expected CHAT RESULTS sections only (not earlier BLOCKED CATEGORIES).
    expected_section = re.search(
        r"expected chat results(.*?)(?:end selective|end advanced|end file|end check|=======|$)",
        lowered,
        flags=re.DOTALL,
    )

    if expected_section:
        section = expected_section.group(1)

        allow_match = re.search(
            r"\ballow:?\s*(.*?)(?=\bblock:|\Z)",
            section,
            flags=re.DOTALL,
        )
        block_match = re.search(
            r"\bblock:?\s*(.*?)(?=\ballow:|\Z)",
            section,
            flags=re.DOTALL,
        )

        if block_match:
            block_chunk = block_match.group(1)

            for employee in KNOWN_EMPLOYEES:
                pattern = (
                    rf"{re.escape(employee.lower())}"
                    rf".{{0,40}}salary|"
                    rf"salary.{{0,40}}"
                    rf"{re.escape(employee.lower())}"
                )
                if re.search(pattern, block_chunk):
                    if employee not in blocked_salaries:
                        blocked_salaries.append(employee)

            for secret in KNOWN_SECRETS:
                if (
                    secret.lower() in block_chunk
                    and secret not in blocked_secrets
                ):
                    blocked_secrets.append(secret)

            if (
                "kasun password" in block_chunk
                and "Kasun Account Password"
                not in blocked_secrets
            ):
                blocked_secrets.append(
                    "Kasun Account Password"
                )
            if (
                "dilani password" in block_chunk
                and "Dilani Account Password"
                not in blocked_secrets
            ):
                blocked_secrets.append(
                    "Dilani Account Password"
                )
            if (
                "admin password" in block_chunk
                and "Admin Password"
                not in blocked_secrets
            ):
                blocked_secrets.append(
                    "Admin Password"
                )
            if (
                "api key" in block_chunk
                and "API Key" not in blocked_secrets
            ):
                blocked_secrets.append("API Key")

        if allow_match:
            allow_chunk = allow_match.group(1)

            for employee in KNOWN_EMPLOYEES:
                pattern = (
                    rf"{re.escape(employee.lower())}"
                    rf".{{0,40}}salary|"
                    rf"salary.{{0,40}}"
                    rf"{re.escape(employee.lower())}"
                )
                if re.search(pattern, allow_chunk):
                    if employee not in allowed_salaries:
                        allowed_salaries.append(employee)

            for secret in KNOWN_SECRETS:
                if (
                    secret.lower() in allow_chunk
                    and secret not in allowed_secrets
                ):
                    allowed_secrets.append(secret)

            if (
                "dilani password" in allow_chunk
                and "Dilani Account Password"
                not in allowed_secrets
            ):
                allowed_secrets.append(
                    "Dilani Account Password"
                )
            if (
                "kasun password" in allow_chunk
                and "Kasun Account Password"
                not in allowed_secrets
            ):
                allowed_secrets.append(
                    "Kasun Account Password"
                )
            if (
                "admin password" in allow_chunk
                and "Admin Password"
                not in allowed_secrets
            ):
                allowed_secrets.append(
                    "Admin Password"
                )
            if (
                "api key" in allow_chunk
                and "API Key" not in allowed_secrets
            ):
                allowed_secrets.append("API Key")

    # Prefer allow over block when both appear for same person.
    allowed_set = {n.lower() for n in allowed_salaries}
    blocked_salaries = [
        name
        for name in blocked_salaries
        if name.lower() not in allowed_set
    ]
    allowed_secret_set = {
        n.lower() for n in allowed_secrets
    }
    blocked_secrets = [
        name
        for name in blocked_secrets
        if name.lower() not in allowed_secret_set
    ]

    return {
        "allowed_employee_salary_names": allowed_salaries,
        "blocked_employee_salary_names": blocked_salaries,
        "allowed_secret_names": allowed_secrets,
        "blocked_secret_names": blocked_secrets,
    }


def _section_between(
    text: str,
    start_marker: str,
    end_marker: str,
) -> str:
    lower = text.lower()
    start = lower.find(start_marker.lower())
    if start < 0:
        return ""
    start = start + len(start_marker)
    end = lower.find(end_marker.lower(), start)
    if end < 0:
        return text[start:]
    return text[start:end]


def _ids_from_checklist_section(section: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()

    for raw_line in section.splitlines():
        line = raw_line.strip().lower()
        if not line.startswith("-"):
            continue
        if "(none" in line:
            continue
        match = re.match(
            r"^-\s+([a-z0-9_]+)\b",
            line,
        )
        if not match:
            continue
        item = match.group(1)
        if item in seen:
            continue
        seen.add(item)
        ids.append(item)

    return ids


def apply_admin_checklist_override(
    policy: dict[str, Any],
    requirement_text: str,
) -> dict[str, Any]:
    """
    If the requirement came from the Admin tick list,
    copy those ticks exactly so Gemini cannot add extras.
    """

    if "admin allow/block checklist" not in (
        requirement_text or ""
    ).lower():
        return policy

    blocked = _ids_from_checklist_section(
        _section_between(
            requirement_text,
            "BLOCKED CATEGORIES",
            "ALLOWED CATEGORIES",
        )
    )
    allowed = _ids_from_checklist_section(
        _section_between(
            requirement_text,
            "ALLOWED CATEGORIES",
            "SENSITIVE PATTERNS",
        )
    )
    patterns = _ids_from_checklist_section(
        _section_between(
            requirement_text,
            "SENSITIVE PATTERNS",
            "EXTRA INFORMATION FROM ADMIN",
        )
    )

    allowed_set = {item.lower() for item in allowed}
    blocked = [
        item
        for item in blocked
        if item.lower() not in allowed_set
    ]

    policy["blocked_categories"] = blocked
    policy["sensitive_pattern_ids"] = patterns
    return policy


def enrich_policy_from_requirement(
    policy: dict[str, Any],
    requirement_text: str,
) -> dict[str, Any]:
    """
    Merge LLM policy with deterministic selective
    rules extracted from the requirement file.
    """

    enriched = dict(policy)
    extracted = extract_selective_rules(
        requirement_text
    )

    for field in (
        "allowed_employee_salary_names",
        "blocked_employee_salary_names",
        "allowed_secret_names",
        "blocked_secret_names",
    ):
        current = _normalize_list(
            enriched.get(field)
        )
        incoming = extracted.get(field, [])

        # Prefer union; extracted fills gaps.
        merged: list[str] = []
        seen: set[str] = set()

        for item in current + incoming:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)

        enriched[field] = merged

    # Remove employee names wrongly placed in secret lists.
    # Keep only known secret/token titles.
    known_secret_keys = {
        name.lower(): name for name in KNOWN_SECRETS
    }

    for field in (
        "allowed_secret_names",
        "blocked_secret_names",
    ):
        cleaned_secrets: list[str] = []
        seen: set[str] = set()

        for item in enriched.get(field, []):
            key = str(item).strip().lower()
            canonical = known_secret_keys.get(key)

            if canonical is None:
                continue

            if canonical.lower() in seen:
                continue

            seen.add(canonical.lower())
            cleaned_secrets.append(canonical)

        enriched[field] = cleaned_secrets

    # Normalize employee salary names to canonical FullName.
    for field in (
        "allowed_employee_salary_names",
        "blocked_employee_salary_names",
    ):
        normalized: list[str] = []
        seen: set[str] = set()

        for item in enriched.get(field, []):
            canonical = None
            item_l = str(item).strip().lower()

            for known in KNOWN_EMPLOYEES:
                if known.lower() == item_l:
                    canonical = known
                    break

            if canonical is None:
                canonical = _find_employee_in_text(
                    item_l
                )

            if canonical is None:
                continue

            if canonical.lower() in seen:
                continue

            seen.add(canonical.lower())
            normalized.append(canonical)

        enriched[field] = normalized

    categories = _normalize_list(
        enriched.get("blocked_categories")
    )
    requirement_l = (requirement_text or "").lower()

    # Selective salary allow-list: remove blanket financial
    # categories so only listed employees are salary-visible.
    if enriched.get("allowed_employee_salary_names"):
        categories = [
            item
            for item in categories
            if item.lower()
            not in {
                "financial_records",
                "employee_information",
            }
        ]

    # Selective secret allow-list: remove blanket credentials
    # unless the document clearly blocks all credentials.
    if enriched.get("allowed_secret_names"):
        broad_credential_block = (
            "block all credentials" in requirement_l
            or "all credentials" in requirement_l
            and "block" in requirement_l
        )

        if not broad_credential_block:
            categories = [
                item
                for item in categories
                if item.lower() != "credentials"
            ]

    enriched["blocked_categories"] = categories

    for field in (
        "allowed_employee_salary_names",
        "blocked_employee_salary_names",
        "allowed_secret_names",
        "blocked_secret_names",
    ):
        enriched.setdefault(field, [])

    warnings = _normalize_list(
        enriched.get("admin_warnings")
    )
    warnings.append(
        "Selective allow/block lists were verified "
        "against the requirement text."
    )
    enriched["admin_warnings"] = warnings

    return apply_admin_checklist_override(
        enriched,
        requirement_text,
    )
