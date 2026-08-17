from pathlib import Path
from typing import Any
import logging
import math
import random
import re
import sys
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# =========================================================
# PROJECT PATH
# =========================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# =========================================================
# PROJECT IMPORTS
# =========================================================

from wrdn.backend.database import (
    find_secret_answer_for_prompt,
    get_audit_logs,
    get_database_context,
    get_employee_salary_by_name,
    get_protection_enabled,
    initialize_database,
    match_secret_name_for_prompt,
    save_audit_log,
    set_protection_enabled,
    test_database_connection,
)
from wrdn.backend.routes.policies import (
    router as policies_router,
)
from wrdn.backend.routes.auth import (
    router as auth_router,
)
from wrdn.backend.routes.hr import (
    router as hr_router,
)
from wrdn.backend.services.policy_judge import (
    judge_output_against_policy,
)
from wrdn.backend.services.inbound_guard import (
    build_detection_log,
)
from wrdn.backend.services.payload_analyzer import (
    analyze_text_payload,
)
from wrdn.backend.services.policy_loader import (
    get_active_policy,
)

from wrdn.config import (
    GEMINI_API_KEY,
    GEMINI_EMBED_MODEL,
    GEMINI_MODEL,
)


try:
    from google import genai
except ImportError as error:
    raise RuntimeError(
        "google-genai is not installed. Run: "
        "python -m pip install --upgrade google-genai"
    ) from error


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("wrdn.backend")


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="WRDN Gemini Output Sanitizer Backend",
    version="2.1.0",
)
app.include_router(policies_router)
app.include_router(auth_router)
app.include_router(hr_router)

# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:18085",
        "http://127.0.0.1:18085",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# APPLICATION STARTUP
# =========================================================

@app.on_event("startup")
def startup_event() -> None:
    """
    Create and initialize the local SQLite database
    whenever the FastAPI backend starts.
    """

    initialize_database()

    database_info = test_database_connection()

    logger.info(
        "WRDN SQLite database initialized: %s",
        database_info.get("database_path"),
    )
    logger.info(
        "Auth users are created via /signup "
        "(demo seed is optional: /api/auth/seed-demo)."
    )


# =========================================================
# SECURITY CONFIGURATION
# =========================================================

BLOCK_THRESHOLD = 70
EMBEDDING_SIMILARITY_THRESHOLD = 0.72


# Intent keywords mapped to policy blocked_categories.
# If the user question matches a category that is active
# in the client policy, block before Gemini runs.
INPUT_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "personal_information": (
        "national id",
        "nationalid",
        "nic",
        "phone number",
        "address",
        "home address",
    ),
    "customer_information": (
        "confidential notes",
        "contract payment",
        "payment amount",
        "client contract confidential",
    ),
    "financial_records": (
        "salary",
        "payroll",
        "how much does",
        "bank account",
        "paymentamount",
        "rs.",
        "lkr",
    ),
    "credentials": (
        "password",
        "api key",
        "access token",
        "private key",
        "secret value",
        "admin password",
        "kasun password",
        "kasun account password",
        "kasun perera password",
        "database password",
        "vpn password",
        "aws root",
        "company secret",
        "payroll system password",
        "smtp secret",
        "backup encryption",
        "github deploy token",
        "jwt token",
    ),
    "employee_information": (
        "employee salary",
        "staff salary",
        "salary list",
        "payroll list",
    ),
    "internal_documents": (
        "confidential notes",
        "internal security incident",
        "confidential contract",
    ),
    "source_code": (
        "source code",
        "dump the code",
        "show me the code base",
    ),
    "malware": (
        "malware",
        "ransomware",
        "write a virus",
    ),
    "violence": (
        "how to attack",
        "how to kill",
        "make a bomb",
    ),
    "illegal_activity": (
        "how to hack",
        "steal data",
        "commit fraud",
    ),
}


def match_salary_employee_for_prompt(
    user_prompt: str,
) -> str | None:
    """
    If the prompt asks for salary/payroll, return the
    matched employee FullName when possible.

    Uses whole-token matching so short aliases like
    "ama" do not match inside "Wickramasinghe".
    """

    text = (user_prompt or "").lower()

    if not text:
        return None

    salary_markers = (
        "salary",
        "payroll",
        "how much does",
        "how much is",
    )

    if not any(marker in text for marker in salary_markers):
        return None

    employee_aliases: list[tuple[str, tuple[str, ...]]] = [
        (
            "Kasun Perera",
            ("kasun perera", "kasun"),
        ),
        (
            "Nimal Silva",
            ("nimal silva", "nimal"),
        ),
        (
            "Ama Fernando",
            ("ama fernando", "ama"),
        ),
        (
            "Sahan Jayawardena",
            ("sahan jayawardena", "sahan"),
        ),
        (
            "Dilani Wickramasinghe",
            ("dilani wickramasinghe", "dilani"),
        ),
        (
            "Ruwan Bandara",
            ("ruwan bandara", "ruwan"),
        ),
        (
            "Ishara Gunasekara",
            ("ishara gunasekara", "ishara"),
        ),
        (
            "Tharindu Mendis",
            ("tharindu mendis", "tharindu"),
        ),
        (
            "Malsha Peris",
            ("malsha peris", "malsha"),
        ),
        (
            "Chamath Fernando",
            ("chamath fernando", "chamath"),
        ),
    ]

    best_name: str | None = None
    best_alias_length = 0

    for full_name, aliases in employee_aliases:
        for alias in aliases:
            pattern = (
                rf"(?<![a-z0-9])"
                rf"{re.escape(alias)}"
                rf"(?![a-z0-9])"
            )

            if not re.search(pattern, text):
                continue

            if len(alias) > best_alias_length:
                best_alias_length = len(alias)
                best_name = full_name

    return best_name


def input_intent_policy_check(
    user_prompt: str,
    blocked_categories: list[str] | None,
    blocked_response: str,
    allowed_secret_names: list[str] | None = None,
    blocked_secret_names: list[str] | None = None,
    allowed_employee_salary_names: list[str] | None = None,
    blocked_employee_salary_names: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Block risky questions by intent using the
    active policy blocked_categories and
    selective allow/block lists.
    Forbidden requests are BLOCKED even if the
    chat model would only refuse politely.
    """

    text = (user_prompt or "").lower()
    active = {
        str(item).strip().lower()
        for item in (blocked_categories or [])
        if str(item).strip()
    }
    allowed_secrets = {
        str(item).strip().lower()
        for item in (allowed_secret_names or [])
        if str(item).strip()
    }
    blocked_secrets = {
        str(item).strip().lower()
        for item in (blocked_secret_names or [])
        if str(item).strip()
    }
    allowed_salaries = {
        str(item).strip().lower()
        for item in (allowed_employee_salary_names or [])
        if str(item).strip()
    }
    blocked_salaries = {
        str(item).strip().lower()
        for item in (blocked_employee_salary_names or [])
        if str(item).strip()
    }

    if not text:
        return None

    matched_secret = match_secret_name_for_prompt(
        user_prompt
    )

    if matched_secret is not None:
        matched_key = matched_secret.lower()

        if matched_key in blocked_secrets:
            return {
                "allowed": False,
                "status": "BLOCKED",
                "risk_score": 100,
                "layer": "Input Policy Guard",
                "reason": (
                    f"User prompt requested blocked "
                    f"secret '{matched_secret}'."
                ),
                "final_output": blocked_response,
                "matched_category": "credentials",
                "matched_keyword": matched_secret,
            }

        if matched_key in allowed_secrets:
            return None

        if allowed_secrets or blocked_secrets:
            # Selective secret policy: unlisted secrets
            # are treated as blocked.
            return {
                "allowed": False,
                "status": "BLOCKED",
                "risk_score": 100,
                "layer": "Input Policy Guard",
                "reason": (
                    f"User prompt requested secret "
                    f"'{matched_secret}' which is not "
                    f"in allowed_secret_names."
                ),
                "final_output": blocked_response,
                "matched_category": "credentials",
                "matched_keyword": matched_secret,
            }

    matched_salary_employee = (
        match_salary_employee_for_prompt(
            user_prompt
        )
    )

    if matched_salary_employee is not None:
        employee_key = matched_salary_employee.lower()

        if employee_key in blocked_salaries:
            return {
                "allowed": False,
                "status": "BLOCKED",
                "risk_score": 100,
                "layer": "Input Policy Guard",
                "reason": (
                    f"User prompt requested blocked "
                    f"salary for '{matched_salary_employee}'."
                ),
                "final_output": blocked_response,
                "matched_category": "financial_records",
                "matched_keyword": matched_salary_employee,
            }

        if employee_key in allowed_salaries:
            return None

        if allowed_salaries or blocked_salaries:
            return {
                "allowed": False,
                "status": "BLOCKED",
                "risk_score": 100,
                "layer": "Input Policy Guard",
                "reason": (
                    f"User prompt requested salary for "
                    f"'{matched_salary_employee}' which is "
                    f"not in allowed_employee_salary_names."
                ),
                "final_output": blocked_response,
                "matched_category": "financial_records",
                "matched_keyword": matched_salary_employee,
            }

        if (
            "financial_records" in active
            or "employee_information" in active
        ):
            return {
                "allowed": False,
                "status": "BLOCKED",
                "risk_score": 100,
                "layer": "Input Policy Guard",
                "reason": (
                    "User prompt requested salary while "
                    "financial/employee categories are blocked."
                ),
                "final_output": blocked_response,
                "matched_category": "financial_records",
                "matched_keyword": "salary",
            }

    if not active:
        return None

    for category, keywords in INPUT_CATEGORY_KEYWORDS.items():
        if category not in active:
            continue

        if (
            category == "credentials"
            and matched_secret is not None
            and matched_secret.lower() in allowed_secrets
        ):
            continue

        if (
            category in {
                "financial_records",
                "employee_information",
            }
            and matched_salary_employee is not None
            and matched_salary_employee.lower()
            in allowed_salaries
        ):
            continue

        matched = next(
            (
                keyword
                for keyword in keywords
                if keyword in text
            ),
            None,
        )

        if matched is None:
            continue

        return {
            "allowed": False,
            "status": "BLOCKED",
            "risk_score": 100,
            "layer": "Input Policy Guard",
            "reason": (
                f"User prompt matched blocked "
                f"category '{category}' "
                f"(keyword: '{matched}')."
            ),
            "final_output": blocked_response,
            "matched_category": category,
            "matched_keyword": matched,
        }

    return None


def normalize_name_list(
    values: list[Any] | None,
) -> list[str]:
    return [
        str(item).strip()
        for item in (values or [])
        if str(item).strip()
    ]


def secret_is_allowed_by_policy(
    secret_name: str,
    allowed_secret_names: list[str],
    blocked_secret_names: list[str],
    credentials_blocked: bool,
) -> bool:
    name = secret_name.strip().lower()
    allowed = {
        item.lower()
        for item in allowed_secret_names
    }
    blocked = {
        item.lower()
        for item in blocked_secret_names
    }

    if name in blocked:
        return False

    if name in allowed:
        return True

    if allowed or blocked:
        # Selective policy present: only listed
        # allowed secrets may be revealed.
        return False

    return not credentials_blocked


def salary_is_allowed_by_policy(
    employee_name: str,
    allowed_employee_salary_names: list[str],
    blocked_employee_salary_names: list[str],
    financial_blocked: bool,
) -> bool:
    name = employee_name.strip().lower()
    allowed = {
        item.lower()
        for item in allowed_employee_salary_names
    }
    blocked = {
        item.lower()
        for item in blocked_employee_salary_names
    }

    if name in blocked:
        return False

    if name in allowed:
        return True

    if allowed or blocked:
        return False

    return not financial_blocked


def enforce_allow_block_semantics(
    user_prompt: str,
    raw_ai_output: str,
    shield: dict[str, Any],
    policy: dict[str, Any],
    blocked_response: str,
    allowed_secret_names: list[str],
    blocked_secret_names: list[str],
    allowed_employee_salary_names: list[str],
    blocked_employee_salary_names: list[str],
    blocked_categories: list[str],
) -> dict[str, Any]:
    """
    Final consistency layer:
    - Forbidden request => BLOCKED + blocked_response
    - Allowed sensitive request with answer => ALLOWED
    - Never show ALLOWED for a polite refusal of blocked data
    """

    active = {
        str(item).strip().lower()
        for item in (blocked_categories or [])
        if str(item).strip()
    }
    credentials_blocked = "credentials" in active
    financial_blocked = (
        "financial_records" in active
        or "employee_information" in active
    )

    matched_secret = match_secret_name_for_prompt(
        user_prompt
    )
    matched_salary = match_salary_employee_for_prompt(
        user_prompt
    )

    # 1) Forbidden secret request => always BLOCK
    if matched_secret is not None:
        can_reveal = secret_is_allowed_by_policy(
            secret_name=matched_secret,
            allowed_secret_names=allowed_secret_names,
            blocked_secret_names=blocked_secret_names,
            credentials_blocked=credentials_blocked,
        )

        if not can_reveal:
            return {
                "allowed": False,
                "status": "BLOCKED",
                "risk_score": 100,
                "layer": "Request Policy Semantics",
                "reason": (
                    f"Request for '{matched_secret}' is "
                    f"blocked by the active policy."
                ),
                "final_output": blocked_response,
            }

        secret_answer = find_secret_answer_for_prompt(
            user_prompt
        )
        output = raw_ai_output

        if secret_answer is not None:
            secret_value = (
                secret_answer.split(":", 1)[-1]
                .strip()
            )
            if (
                looks_like_model_refusal(output)
                or secret_value.lower()
                not in output.lower()
            ):
                output = secret_answer

        return {
            "allowed": True,
            "status": "ALLOWED",
            "risk_score": min(
                int(shield.get("risk_score", 20)),
                40,
            ),
            "layer": "Request Policy Semantics",
            "reason": (
                f"Request for '{matched_secret}' is "
                f"allowed by the active policy."
            ),
            "final_output": output,
        }

    # 2) Forbidden / allowed salary request
    if matched_salary is not None:
        can_reveal = salary_is_allowed_by_policy(
            employee_name=matched_salary,
            allowed_employee_salary_names=(
                allowed_employee_salary_names
            ),
            blocked_employee_salary_names=(
                blocked_employee_salary_names
            ),
            financial_blocked=financial_blocked,
        )

        if not can_reveal:
            return {
                "allowed": False,
                "status": "BLOCKED",
                "risk_score": 100,
                "layer": "Request Policy Semantics",
                "reason": (
                    f"Request for salary of "
                    f"'{matched_salary}' is blocked "
                    f"by the active policy."
                ),
                "final_output": blocked_response,
            }

        salary_answer = get_employee_salary_by_name(
            matched_salary
        )
        output = raw_ai_output

        if salary_answer is not None:
            if (
                looks_like_model_refusal(output)
                or matched_salary.lower()
                not in output.lower()
                or "salary" not in output.lower()
            ):
                output = salary_answer

        return {
            "allowed": True,
            "status": "ALLOWED",
            "risk_score": min(
                int(shield.get("risk_score", 20)),
                40,
            ),
            "layer": "Request Policy Semantics",
            "reason": (
                f"Request for salary of "
                f"'{matched_salary}' is allowed "
                f"by the active policy."
            ),
            "final_output": output,
        }

    # 3) Category-blocked personal / contract asks
    text = (user_prompt or "").lower()
    personal_markers = (
        "national id",
        "nationalid",
        " nic",
        "phone number",
        "home address",
    )
    if (
        "personal_information" in active
        and any(marker in text for marker in personal_markers)
    ):
        return {
            "allowed": False,
            "status": "BLOCKED",
            "risk_score": 100,
            "layer": "Request Policy Semantics",
            "reason": (
                "Request targets blocked personal "
                "information under the active policy."
            ),
            "final_output": blocked_response,
        }

    contract_markers = (
        "confidential notes",
        "payment amount",
        "contract payment",
    )
    if (
        (
            "customer_information" in active
            or "internal_documents" in active
            or "financial_records" in active
        )
        and any(
            marker in text
            for marker in contract_markers
        )
    ):
        return {
            "allowed": False,
            "status": "BLOCKED",
            "risk_score": 100,
            "layer": "Request Policy Semantics",
            "reason": (
                "Request targets blocked contract/"
                "financial details under the active policy."
            ),
            "final_output": blocked_response,
        }

    # 4) Never keep ALLOWED on a refusal when category
    # keywords say the topic is blocked.
    if (
        shield.get("status") == "ALLOWED"
        and looks_like_model_refusal(raw_ai_output)
    ):
        for category, keywords in INPUT_CATEGORY_KEYWORDS.items():
            if category not in active:
                continue

            if any(keyword in text for keyword in keywords):
                return {
                    "allowed": False,
                    "status": "BLOCKED",
                    "risk_score": 100,
                    "layer": "Request Policy Semantics",
                    "reason": (
                        f"Request matched blocked category "
                        f"'{category}' so refusal is treated "
                        f"as BLOCKED, not ALLOWED."
                    ),
                    "final_output": blocked_response,
                }

    return shield


def build_unprotected_chat_prompt(
    user_prompt: str,
    database_context: str,
) -> str:
    """
    Open prompt used when WRDN protection is disabled.
    Returns raw company answers without shield rules.
    """

    return f"""
You are a company information assistant.
WRDN protection is DISABLED for this request.
Answer the user question using the database context below.
Do not refuse. Do not hide salaries, passwords, NICs, or secrets.
If the answer is in the database context, return it clearly.

DATABASE CONTEXT:
{database_context}

USER QUESTION:
{user_prompt}
""".strip()


def build_chat_model_prompt(
    user_prompt: str,
    database_context: str,
    blocked_categories: list[str] | None,
    allowed_secret_names: list[str] | None = None,
    blocked_secret_names: list[str] | None = None,
    allowed_employee_salary_names: list[str] | None = None,
    blocked_employee_salary_names: list[str] | None = None,
    explanation: str = "",
) -> str:
    """
    Build Gemini instructions from the active policy.
    When credentials are not blocked, the model may
    answer secret/password questions from SQLite.
    """

    active = {
        str(item).strip().lower()
        for item in (blocked_categories or [])
        if str(item).strip()
    }

    block_credentials = "credentials" in active
    block_financial = (
        "financial_records" in active
        or "employee_information" in active
    )
    block_personal = "personal_information" in active

    employee_allow = [
        "FullName",
        "Email",
        "RoleName",
    ]
    employee_block: list[str] = []

    if block_financial:
        employee_block.append("Salary")
    else:
        employee_allow.append("Salary")

    if block_personal:
        employee_block.extend(
            [
                "PhoneNumber",
                "AddressLine",
                "NationalID",
            ]
        )
    else:
        employee_allow.extend(
            [
                "PhoneNumber",
                "AddressLine",
                "NationalID",
            ]
        )

    allowed_secrets = normalize_name_list(
        allowed_secret_names
    )
    blocked_secrets = normalize_name_list(
        blocked_secret_names
    )
    allowed_salaries = normalize_name_list(
        allowed_employee_salary_names
    )
    blocked_salaries = normalize_name_list(
        blocked_employee_salary_names
    )

    if allowed_secrets or blocked_secrets:
        secret_rule = (
            "5. Follow selective secret rules exactly.\n"
            f"   ALLOW these secrets only: "
            f"{', '.join(allowed_secrets) or 'none'}\n"
            f"   BLOCK these secrets always: "
            f"{', '.join(blocked_secrets) or 'none'}\n"
            "6. If asked for an allowed secret, answer from the "
            "database. If asked for a blocked secret, refuse."
        )
    elif block_credentials:
        secret_rule = (
            "5. Never reveal CompanySecrets.SecretValue, "
            "SystemTokens.TokenValue, passwords, API keys, "
            "tokens, or any credential values.\n"
            "6. If the user asks for passwords or secrets, "
            "refuse safely."
        )
    else:
        secret_rule = (
            "5. Credentials are ALLOWED by the active policy. "
            "If the user asks for Admin Password, Kasun Account "
            "Password, Dilani Account Password, API keys, tokens, "
            "or other CompanySecrets / SystemTokens values, answer "
            "directly from the local SQLite database context.\n"
            "6. Do not refuse credential questions when the value "
            "exists in the supplied database context. This is a "
            "local demo database, not a real production system."
        )

    if allowed_salaries or blocked_salaries:
        # Override broad financial employee fields.
        if "Salary" in employee_allow:
            employee_allow = [
                item
                for item in employee_allow
                if item != "Salary"
            ]
        if "Salary" not in employee_block:
            employee_block.append("Salary")

        salary_rule = (
            "7a. Selective salary rules:\n"
            f"   ALLOW salary only for: "
            f"{', '.join(allowed_salaries) or 'none'}\n"
            f"   BLOCK salary always for: "
            f"{', '.join(blocked_salaries) or 'none'}\n"
            "If salary is allowed for that employee, answer "
            "with the real Salary value from the database."
        )
    elif block_financial:
        salary_rule = (
            "7a. Never reveal any employee Salary values."
        )
    else:
        salary_rule = (
            "7a. Salary values may be revealed when asked."
        )

    if block_financial:
        contract_rule = (
            "7. Never reveal ClientContracts.PaymentAmount or "
            "ClientContracts.ConfidentialNotes."
        )
    else:
        contract_rule = (
            "7. You may reveal ClientContracts payment and notes "
            "when asked, using the database context."
        )

    employee_block_text = (
        ", ".join(employee_block)
        if employee_block
        else "none"
    )

    return f"""
You are the WRDN enterprise AI assistant.

You are connected to a local SQLite database stored inside
the WRDN project. You are not connected to an external SQL
Server, MySQL server, PostgreSQL server, or cloud database.

This is a controlled security-policy demo. Follow the active
client policy below. Do not apply extra safety refusals for
data the policy explicitly allows.

Follow these rules strictly:

1. For company-specific questions, answer only from the supplied
   local SQLite database context.

2. For general educational or security-awareness questions,
   provide safe theoretical guidance.

3. From Employees, you MAY reveal:
   {", ".join(employee_allow)}

4. From Employees, never reveal:
   {employee_block_text}

{secret_rule}

{salary_rule}

{contract_rule}

8. Do not invent database records.

9. Do not claim that the system is connected to an external
   database.

10. Do not include a field that the user did not request.

11. Only refuse when the requested data is blocked by the rules
    above or is not present in the database context.

Policy explanation:
{explanation or "none"}

Local SQLite database context:
{database_context}

Active client policy blocked categories:
{", ".join(sorted(active)) if active else "none"}

Allowed secret names:
{", ".join(allowed_secrets) if allowed_secrets else "none"}

Blocked secret names:
{", ".join(blocked_secrets) if blocked_secrets else "none"}

Allowed employee salary names:
{", ".join(allowed_salaries) if allowed_salaries else "none"}

Blocked employee salary names:
{", ".join(blocked_salaries) if blocked_salaries else "none"}

User question:
{user_prompt}

Return only the minimum necessary response.
"""


def looks_like_model_refusal(
    text: str,
) -> bool:
    lowered = (text or "").lower()
    markers = (
        "i cannot",
        "i can't",
        "cannot fulfill",
        "can't fulfill",
        "unable to",
        "not able to",
        "won't provide",
        "will not provide",
        "cannot provide",
        "can't provide",
        "against my",
        "as an ai",
    )
    return any(
        marker in lowered
        for marker in markers
    )


# =========================================================
# GEMINI CLIENT
# =========================================================

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. "
        "Add it to wrdn/config.py or your backend environment."
    )


try:
    GEMINI_CLIENT = genai.Client(
        api_key=GEMINI_API_KEY,
    )
except Exception as error:
    raise RuntimeError(
        f"Gemini client initialization failed: {error}"
    ) from error


# =========================================================
# REQUEST MODELS
# =========================================================

class PromptRequest(BaseModel):
    prompt: str
    client_id: str = "default"
    username: str = ""


# =========================================================
# GEMINI TEXT GENERATION
# =========================================================

FALLBACK_GEMINI_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
]

def ask_gemini(
    prompt: str,
    max_retries: int = 4,
) -> str:
    """
    Generate text using Gemini.

    Temporary service errors are retried using
    exponential backoff.
    """

    cleaned_prompt = prompt.strip()

    if not cleaned_prompt:
        raise ValueError(
            "Prompt cannot be empty."
        )

    retryable_errors = (
        "429",
        "500",
        "502",
        "503",
        "504",
        "resource_exhausted",
        "internal",
        "unavailable",
        "deadline_exceeded",
        "high demand",
        "temporarily unavailable",
    )

    def is_model_not_found(error_message: str) -> bool:
        return (
            "not_found" in error_message
            or "not found" in error_message
            or "unsupported for generatecontent" in error_message
        )

    models_to_try = [
        GEMINI_MODEL,
        *[
            model for model in FALLBACK_GEMINI_MODELS
            if model != GEMINI_MODEL
        ],
    ]

    last_error: Exception | None = None

    for model in models_to_try:
        for attempt in range(max_retries):
            try:
                response = (
                    GEMINI_CLIENT.models.generate_content(
                        model=model,
                        contents=cleaned_prompt,
                    )
                )

                generated_text = getattr(
                    response,
                    "text",
                    None,
                )

                if not generated_text:
                    raise RuntimeError(
                        "Gemini returned an empty response."
                    )

                return generated_text.strip()

            except Exception as error:
                last_error = error
                error_message = str(error).lower()

                if is_model_not_found(error_message):
                    logger.warning(
                        "Gemini model '%s' is not available or not supported; "
                        "trying fallback models.",
                        model,
                    )
                    break

                retryable = any(
                    value in error_message
                    for value in retryable_errors
                )

                if not retryable:
                    raise RuntimeError(
                        f"Gemini text generation failed: {error}"
                    ) from error

                if attempt == max_retries - 1:
                    break

                wait_seconds = (
                    2 ** (attempt + 1)
                    + random.uniform(0, 1)
                )

                logger.warning(
                    "Temporary Gemini error. "
                    "Attempt %s/%s failed for model %s. "
                    "Retrying in %.2f seconds. "
                    "Error: %s",
                    attempt + 1,
                    max_retries,
                    model,
                    wait_seconds,
                    error,
                )

                time.sleep(wait_seconds)

        if last_error is not None and is_model_not_found(str(last_error).lower()):
            continue
        if last_error is None:
            break

    raise RuntimeError(
        "Gemini is temporarily unavailable after "
        f"{max_retries} attempts. "
        f"Last error: {last_error}"
    )


# =========================================================
# GEMINI EMBEDDINGS
# =========================================================

def create_gemini_embedding(
    text: str,
) -> list[float]:
    """
    Generate a Gemini embedding vector.
    """

    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "Embedding input cannot be empty."
        )

    try:
        response = (
            GEMINI_CLIENT.models.embed_content(
                model=GEMINI_EMBED_MODEL,
                contents=cleaned_text,
            )
        )

        embeddings = getattr(
            response,
            "embeddings",
            None,
        )

        if not embeddings:
            raise RuntimeError(
                "Gemini returned no embeddings."
            )

        first_embedding = embeddings[0]

        values = getattr(
            first_embedding,
            "values",
            None,
        )

        if values is None:
            values = getattr(
                first_embedding,
                "embedding",
                None,
            )

        if not values:
            raise RuntimeError(
                "Gemini returned an empty embedding vector."
            )

        return [
            float(value)
            for value in values
        ]

    except Exception as error:
        raise RuntimeError(
            "Gemini embedding generation failed: "
            f"{error}"
        ) from error


def cosine_similarity(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    """
    Calculate cosine similarity between two vectors.
    """

    if not vector_a or not vector_b:
        return 0.0

    if len(vector_a) != len(vector_b):
        raise ValueError(
            "Embedding vectors must have "
            "the same dimensions."
        )

    dot_product = sum(
        value_a * value_b
        for value_a, value_b
        in zip(vector_a, vector_b)
    )

    magnitude_a = math.sqrt(
        sum(
            value * value
            for value in vector_a
        )
    )

    magnitude_b = math.sqrt(
        sum(
            value * value
            for value in vector_b
        )
    )

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return (
        dot_product
        / (magnitude_a * magnitude_b)
    )


# =========================================================
# EMBEDDING SECURITY CHECK
# =========================================================

SENSITIVE_REFERENCE_TEXTS = [
    (
        "The response reveals confidential employee "
        "salary or payroll information."
    ),
    (
        "The response exposes a password, API key, "
        "secret, access token, or credential."
    ),
    (
        "The response reveals administrator login "
        "details or authentication secrets."
    ),
    (
        "The response exposes database passwords, "
        "cloud credentials, or production tokens."
    ),
    (
        "The response provides private employee "
        "information that must not be disclosed."
    ),
    (
        "The response reveals confidential company "
        "records containing actual sensitive values."
    ),
]


_REFERENCE_EMBEDDINGS: (
    list[tuple[str, list[float]]] | None
) = None


def get_reference_embeddings(
) -> list[tuple[str, list[float]]]:
    """
    Create sensitive reference embeddings once
    and reuse them for later checks.
    """

    global _REFERENCE_EMBEDDINGS

    if _REFERENCE_EMBEDDINGS is None:
        generated_references: list[
            tuple[str, list[float]]
        ] = []

        for reference_text in (
            SENSITIVE_REFERENCE_TEXTS
        ):
            generated_references.append(
                (
                    reference_text,
                    create_gemini_embedding(
                        reference_text
                    ),
                )
            )

        _REFERENCE_EMBEDDINGS = (
            generated_references
        )

    return _REFERENCE_EMBEDDINGS


def embedding_risk_check(
    text: str,
    embedding_threshold: float = EMBEDDING_SIMILARITY_THRESHOLD,
    block_threshold: int = BLOCK_THRESHOLD,
) -> dict[str, Any]:
    
    """
    Compare the generated output with sensitive
    enterprise-output reference texts.
    """

    if not text or not text.strip():
        return {
            "blocked": False,
            "risk_score": 0,
            "similarity": 0.0,
            "matched_reference": "",
            "reason": "AI output was empty.",
            "error": False,
        }

    try:
        output_embedding = (
            create_gemini_embedding(text)
        )

        reference_embeddings = (
            get_reference_embeddings()
        )

        highest_similarity = 0.0
        matched_reference = ""

        for (
            reference_text,
            reference_embedding,
        ) in reference_embeddings:
            similarity = cosine_similarity(
                output_embedding,
                reference_embedding,
            )

            if similarity > highest_similarity:
                highest_similarity = similarity
                matched_reference = (
                    reference_text
                )

        risk_score = min(
            100,
            round(
                highest_similarity * 100
            ),
        )

        blocked = (
            highest_similarity
            >= embedding_threshold
        )

        return {
            "blocked": blocked,
            "risk_score": risk_score,
            "similarity": round(
                highest_similarity,
                4,
            ),
            "matched_reference": (
                matched_reference
            ),
            "reason": (
                "Semantic similarity to sensitive "
                "enterprise output detected: "
                f"{matched_reference}"
                if blocked
                else (
                    "No high semantic similarity "
                    "to sensitive output."
                )
            ),
            "error": False,
        }

    except Exception as error:
        logger.exception(
            "Embedding security check failed."
        )

        return {
            "blocked": True,
            "risk_score": block_threshold,
            "similarity": 0.0,
            "matched_reference": "",
            "reason": (
                "Embedding sanitizer unavailable: "
                f"{error}"
            ),
            "error": True,
        }


# =========================================================
# SENSITIVE DATA REDACTION
# =========================================================

def redact_sensitive_parts(
    raw_ai_output: str,
) -> str:
    """
    Replace sensitive values in generated output.
    """

    redacted_output = raw_ai_output

    redaction_patterns = [
        (
            (
                r"((?:manager|employee)?\s*"
                r"salary\s*(?:is|[:=])\s*)"
                r"(?:rs\.?|lkr|\$)?\s*"
                r"\d+(?:,\d{3})*(?:\.\d+)?"
            ),
            r"\1[BLOCKED]",
        ),
        (
            r"(\bpassword\s*[:=]\s*)\S+",
            r"\1[BLOCKED]",
        ),
        (
            r"(\bapi\s*key\s*[:=]\s*)\S+",
            r"\1[BLOCKED]",
        ),
        (
            r"(\btoken\s*[:=]\s*)\S+",
            r"\1[BLOCKED]",
        ),
        (
            r"(\bsecret\s*[:=]\s*)\S+",
            r"\1[BLOCKED]",
        ),
        (
            r"(\bcredential\s*[:=]\s*)\S+",
            r"\1[BLOCKED]",
        ),
    ]

    for (
        pattern,
        replacement,
    ) in redaction_patterns:
        redacted_output = re.sub(
            pattern,
            replacement,
            redacted_output,
            flags=re.IGNORECASE,
        )

    return redacted_output


# =========================================================
# REGEX OUTPUT SANITIZER
# =========================================================

POLICY_PATTERN_LIBRARY = {
    "api_key": [
        r"\bapi[_\s-]?key\s*[:=]\s*\S+"
    ],
    "password": [
        r"\bpassword\s*[:=]\s*\S+"
    ],
    "access_token": [
        (
            r"\b(?:access|bearer|jwt)"
            r"[_\s-]?token\s*[:=]\s*\S+"
        )
    ],
    "private_key": [
        (
            r"-----BEGIN "
            r"(?:RSA |EC |OPENSSH )?"
            r"PRIVATE KEY-----"
        )
    ],
    "email_address": [
        (
            r"\b[A-Z0-9._%+-]+"
            r"@[A-Z0-9.-]+\.[A-Z]{2,}\b"
        )
    ],
    "phone_number": [
        r"\b(?:\+94|0)7\d{8}\b"
    ],
    "sri_lankan_nic": [
        r"\b(?:\d{9}[VX]|\d{12})\b"
    ],
    "bank_account": [
        (
            r"\bbank\s+account\s*"
            r"(?:number|no\.?|#)?\s*"
            r"[:=]?\s*\d{6,18}\b"
        )
    ],
}

def regex_output_sanitizer(
    raw_ai_output: str,
    block_threshold: int = BLOCK_THRESHOLD,
    sensitive_pattern_ids: list[str] | None = None,
    blocked_categories: list[str] | None = None,
) -> dict[str, Any]:
    
    """
    Detect known secret values and sensitive
    output patterns, respecting active policy
    blocked categories.
    """

    active = {
        str(item).strip().lower()
        for item in (blocked_categories or [])
        if str(item).strip()
    }

    # Default to blocking credentials/financial
    # when no categories were provided (safe default).
    block_credentials = (
        (not active)
        or ("credentials" in active)
    )
    block_financial = (
        (not active)
        or ("financial_records" in active)
        or ("employee_information" in active)
    )

    patterns: dict[str, int] = {}

    if block_financial:
        patterns.update(
            {
                (
                    r"(?:rs\.?|lkr|\$)\s*"
                    r"\d+(?:,\d{3})+(?:\.\d+)?"
                ): 100,
                r"\b\d{2,3},\d{3}\b": 100,
                (
                    r"\bmanager\b.*\bsalary\b.*"
                    r"(?:rs\.?|lkr|\$)?\s*\d+"
                ): 100,
                (
                    r"\bsalary\b.*\bmanager\b.*"
                    r"(?:rs\.?|lkr|\$)?\s*\d+"
                ): 100,
                (
                    r"\bemployee\b.*\bsalary\b.*"
                    r"(?:rs\.?|lkr|\$)?\s*\d+"
                ): 100,
                (
                    r"\bsalary\b.*\bemployee\b.*"
                    r"(?:rs\.?|lkr|\$)?\s*\d+"
                ): 100,
                r"\bpayroll\b.*\d+": 95,
                (
                    r"select\s+.*salary.*\s+from"
                ): 90,
                (
                    r"\bemployee[_\s-]?data\b.*"
                    r"\bsalary\b"
                ): 90,
                (
                    r"\bconfidential\b.*"
                    r"\bsalary\s*[:=]?\s*\d+"
                ): 100,
            }
        )

    if block_credentials:
        patterns.update(
            {
                r"admin@12345": 100,
                r"kasun@Work2026": 100,
                r"sk-test-company-secret-key-999": 100,
                r"db_pass_2026_secret": 100,
                r"aws-root-secret-2026": 100,
                r"vpn-company-pass": 100,
                r"jwt-prod-token-123456": 100,
                r"azure-access-secret-999": 100,
                r"openai-company-token-777": 100,
                r"\bpassword\s*[:=]\s*\S+": 100,
                (
                    r"\badmin\s+password\s*"
                    r"[:=]?\s*\S+"
                ): 100,
                r"\bapi\s*key\s*[:=]\s*\S+": 100,
                r"\btoken\s*[:=]\s*\S+": 100,
                r"\bsecret\s*[:=]\s*\S+": 100,
                r"\bcredential\s*[:=]\s*\S+": 100,
                (
                    r"(?:sk|api|key|secret|token)"
                    r"[\-_][a-zA-Z0-9]{10,}"
                ): 100,
                (
                    r"select\s+.*password.*\s+from"
                ): 100,
                (
                    r"select\s+.*token.*\s+from"
                ): 100,
                (
                    r"select\s+.*secret.*\s+from"
                ): 100,
                (
                    r"select\s+.*api[_\s-]?"
                    r"key.*\s+from"
                ): 100,
                r"\busers?\b.*\bpassword\b": 100,
                r"\badmin\b.*\bpassword\b": 100,
                (
                    r"\binternal database\b.*"
                    r"\bpassword\s*[:=]\s*\S+"
                ): 100,
                (
                    r"\binternal database\b.*"
                    r"\bapi\s*key\s*[:=]\s*\S+"
                ): 100,
                (
                    r"\binternal database\b.*"
                    r"\btoken\s*[:=]\s*\S+"
                ): 100,
                (
                    r"\bdatabase record\b.*"
                    r"\bpassword\s*[:=]\s*\S+"
                ): 100,
            }
        )
    for pattern_id in (
        sensitive_pattern_ids or []
    ):
        policy_patterns = (
            POLICY_PATTERN_LIBRARY.get(
                pattern_id,
                [],
            )
        )

        for policy_pattern in policy_patterns:
            # Company employee emails are directory data.
            # Do not hard-block on email alone.
            if pattern_id == "email_address":
                patterns[policy_pattern] = 35
            else:
                patterns[policy_pattern] = 100
    highest_score = 0
    reasons: list[str] = []

    for pattern, score in patterns.items():
        if re.search(
            pattern,
            raw_ai_output,
            re.IGNORECASE | re.DOTALL,
        ):
            highest_score = max(
                highest_score,
                score,
            )

            reasons.append(
                "Raw AI output matched "
                f"pattern: {pattern}"
            )

    return {
                "blocked": (
            highest_score
            >= block_threshold
        ),
        "risk_score": highest_score,
        "reason": (
            ", ".join(reasons)
            if reasons
            else (
                "No regex risk detected "
                "in raw AI output."
            )
        ),
    }


# =========================================================
# FINAL OUTPUT SANITIZER
# =========================================================
def final_output_sanitizer(
    raw_ai_output: str,
    block_threshold: int = BLOCK_THRESHOLD,
    embedding_threshold: float = EMBEDDING_SIMILARITY_THRESHOLD,
    blocked_response: str = "This output was blocked by the WRDN security policy.",
    sensitive_pattern_ids: list[str] | None = None,
    blocked_categories: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run regex and embedding security checks.

    Regex blocks when risk_score >= policy risk_threshold.
    Embedding blocks only when similarity >= embedding_threshold.
    Credential/financial regex patterns follow blocked_categories.
    """

    regex_result = regex_output_sanitizer(
        raw_ai_output,
        block_threshold=block_threshold,
        sensitive_pattern_ids=sensitive_pattern_ids,
        blocked_categories=blocked_categories,
    )

    embedding_result = embedding_risk_check(
        raw_ai_output,
        embedding_threshold=embedding_threshold,
        block_threshold=block_threshold,
    )

    regex_score = int(
        regex_result.get("risk_score", 0)
    )
    embedding_score = int(
        embedding_result.get("risk_score", 0)
    )
    final_risk_score = max(
        regex_score,
        embedding_score,
    )

    if embedding_result.get("error"):
        return {
            "allowed": False,
            "status": "ERROR",
            "risk_score": block_threshold,
            "layer": "Embedding Sanitizer",
            "reason": embedding_result["reason"],
            "final_output": (
                "[BLOCKED] The embedding sanitizer failed, "
                "so the output was not released."
            ),
        }

    regex_blocked = regex_score >= block_threshold
    embedding_blocked = bool(
        embedding_result.get("blocked")
    )

    if regex_blocked or embedding_blocked:
        if regex_blocked and (
            not embedding_blocked
            or regex_score >= embedding_score
        ):
            reason = regex_result["reason"]
            layer = "Regex Output Sanitizer"
        else:
            reason = embedding_result["reason"]
            layer = "Embedding Output Sanitizer"

        return {
            "allowed": False,
            "status": "BLOCKED",
            "risk_score": final_risk_score,
            "layer": layer,
            "reason": reason,
            "final_output": blocked_response,
        }

    return {
        "allowed": True,
        "status": "ALLOWED",
        "risk_score": final_risk_score,
        "layer": "Output Sanitizer",
        "reason": (
            "Raw AI output passed regex "
            "and embedding checks."
        ),
        "final_output": raw_ai_output,
    }

# =========================================================
# ROOT ROUTE
# =========================================================

@app.get("/")
def home() -> dict[str, Any]:
    return {
        "message": (
            "WRDN Gemini backend running"
        ),
        "available_endpoints": [
            "GET /",
            "GET /health",
            "GET /api/health",
            "GET /api/registry",
            "GET /api/test-gemini",
            "POST /chat",
            "POST /sanitize",
        ],
    }


# =========================================================
# HEALTH ROUTES
# =========================================================

@app.get("/health")
def docker_health_check(
) -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "WRDN Backend API",
    }


@app.get("/api/health")
def health_check(
) -> dict[str, Any]:
    try:
        database_info = (
            test_database_connection()
        )

        return {
            "status": "running",
            "service": (
                "WRDN Backend API"
            ),
            "gemini_client": (
                "configured"
            ),
            "gemini_model": GEMINI_MODEL,
            "embedding_model": (
                GEMINI_EMBED_MODEL
            ),
            "database": database_info,
        }

    except Exception as error:
        logger.exception(
            "Health check failed."
        )

        return {
            "status": "error",
            "service": (
                "WRDN Backend API"
            ),
            "database": {
                "status": (
                    "disconnected"
                ),
                "error": str(error),
            },
        }


class ProtectionToggleRequest(BaseModel):
    client_id: str = "default"
    enabled: bool = True


@app.get("/api/protection-status")
def protection_status(
    client_id: str = "default",
) -> dict[str, Any]:
    safe_client_id = (
        client_id.strip() or "default"
    )
    enabled = get_protection_enabled(
        safe_client_id
    )

    return {
        "client_id": safe_client_id,
        "protection_enabled": enabled,
        "status": (
            "ENABLED" if enabled else "DISABLED"
        ),
        "message": (
            "WRDN protection is active."
            if enabled
            else (
                "WRDN protection is disabled. "
                "Chat returns raw AI output (BYPASSED)."
            )
        ),
    }


@app.post("/api/admin/protection-status")
def update_protection_status(
    request: ProtectionToggleRequest,
) -> dict[str, Any]:
    safe_client_id = (
        request.client_id.strip() or "default"
    )
    enabled = set_protection_enabled(
        safe_client_id,
        bool(request.enabled),
    )

    return {
        "client_id": safe_client_id,
        "protection_enabled": enabled,
        "status": (
            "ENABLED" if enabled else "DISABLED"
        ),
        "message": (
            "WRDN protection enabled."
            if enabled
            else (
                "WRDN protection disabled. "
                "Raw AI output will be shown."
            )
        ),
    }


# =========================================================
# GEMINI TEST ROUTE
# =========================================================

@app.get("/api/test-gemini")
def test_gemini(
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "generation": {
            "status": "not_tested",
        },
        "embedding": {
            "status": "not_tested",
        },
    }

    try:
        generated_text = ask_gemini(
            "Reply with exactly: "
            "Gemini generation is working"
        )

        result["generation"] = {
            "status": "working",
            "output": generated_text,
        }

    except Exception as error:
        result["generation"] = {
            "status": "failed",
            "error": str(error),
        }

    try:
        embedding = (
            create_gemini_embedding(
                "WRDN embedding test"
            )
        )

        result["embedding"] = {
            "status": "working",
            "dimensions": len(
                embedding
            ),
            "preview": embedding[:5],
        }

    except Exception as error:
        result["embedding"] = {
            "status": "failed",
            "error": str(error),
        }

    result["success"] = (
        result["generation"]["status"]
        == "working"
        and result["embedding"]["status"]
        == "working"
    )

    return result


# =========================================================
# LOCAL SQLITE REGISTRY ROUTE
# =========================================================

@app.get("/api/registry")
def get_registry(
    client_id: str = "default",
    username: str = "",
    role: str = "EMPLOYEE",
) -> dict[str, Any]:
    """
    Read allowed and blocked audit records
    from the local SQLite database.

    Employees see only their own logs for their client.
    Admins see all logs for their client.
    """

    try:
        database_info = (
            test_database_connection()
        )

        safe_client = (
            client_id or "default"
        ).strip()
        safe_user = (username or "").strip()
        safe_role = (
            role or "EMPLOYEE"
        ).strip().upper()

        filter_username = (
            None
            if safe_role == "ADMIN"
            else (safe_user or None)
        )

        audit_logs = get_audit_logs(
            limit=500,
            client_id=safe_client,
            username=filter_username,
        )

        allowed_logs: list[
            dict[str, Any]
        ] = []

        blocked_logs: list[
            dict[str, Any]
        ] = []

        for log in audit_logs:
            shield_status = str(
                log.get(
                    "ShieldStatus"
                )
                or "UNKNOWN"
            ).upper()

            log_record = {
                "id": log.get("LogID"),
                "timestamp": log.get(
                    "CreatedAt",
                    "",
                ),
                "username": log.get(
                    "Username",
                    "",
                ) or "",
                "client_id": log.get(
                    "ClientID",
                    "",
                ) or "",
                "user_prompt": log.get(
                    "UserPrompt",
                    "",
                ),
                "raw_ai_output": log.get(
                    "RawAIOutput",
                    "",
                ),
                "shield_status": (
                    shield_status
                ),
                "risk_score": int(
                    log.get(
                        "RiskScore"
                    )
                    or 0
                ),
                "detection_reason": (
                    log.get(
                        "DetectionReason",
                        "",
                    )
                ),
            }

            if shield_status in {
                "ALLOWED",
                "BYPASSED",
                "UNPROTECTED",
            }:
                allowed_logs.append(
                    log_record
                )
            elif shield_status in {
                "BLOCKED",
                "ERROR",
            }:
                blocked_logs.append(
                    log_record
                )
            else:
                # keep unknown rows visible under
                # blocked logs for investigation.
                log_record["shield_status"] = (
                    shield_status
                    if shield_status
                    else "UNKNOWN"
                )
                blocked_logs.append(
                    log_record
                )

        return {
            "company_name": (
                "WRDN Enterprise"
            ),
            "database_status": (
                "CONNECTED"
            ),
            "scope": (
                "client"
                if safe_role == "ADMIN"
                else "user"
            ),
            "viewer_role": safe_role,
            "viewer_username": safe_user,
            "client_id": safe_client,
            "database_type": (
                database_info[
                    "database_type"
                ]
            ),
            "database_path": (
                database_info[
                    "database_path"
                ]
            ),
            "employee_count": (
                database_info[
                    "employee_count"
                ]
            ),
            "audit_count": (
                len(audit_logs)
            ),
            "allowed_count": len(
                allowed_logs
            ),
            "blocked_count": len(
                blocked_logs
            ),
            "allowed_logs": allowed_logs,
            "blocked_logs": blocked_logs,
        }

    except Exception as error:
        logger.exception(
            "Failed to read local "
            "WRDN registry."
        )

        return {
            "company_name": (
                "WRDN Enterprise"
            ),
            "database_status": "ERROR",
            "database_type": "SQLite",
            "allowed_count": 0,
            "blocked_count": 0,
            "allowed_logs": [],
            "blocked_logs": [],
            "error": str(error),
        }


# =========================================================
# chat route
# =========================================================

@app.post("/chat")
def chat(
    request: PromptRequest,
) -> dict[str, Any]:
    try:
        user_prompt = (
            request.prompt.strip()
        )

        if not user_prompt:
            return {
                "status": "ERROR",
                "error": (
                    "Prompt cannot be empty."
                ),
                "final_output": (
                    "Please enter a question."
                ),
            }

        inbound = analyze_text_payload(
            user_prompt,
            source="chat",
        )
        if inbound["blocked"]:
            inbound_client = (
                request.client_id or "default"
            )
            try:
                save_audit_log(
                    user_prompt=user_prompt[:400],
                    raw_output="",
                    shield_status="BLOCKED",
                    risk_score=int(
                        inbound["risk_score"]
                    ),
                    detection_reason=inbound["reason"],
                    client_id=inbound_client,
                    username=(
                        request.username or ""
                    ).strip(),
                    detection_layer=inbound["layer"],
                    matched_rule="inbound_payload",
                )
            except Exception:
                logger.warning(
                    "Failed to save inbound chat audit log."
                )

            return {
                "user_prompt": user_prompt,
                "raw_ai_output": "[HIDDEN BY WRDN]",
                "shield_status": "BLOCKED",
                "risk_score": int(
                    inbound["risk_score"]
                ),
                "detection_layer": inbound["layer"],
                "detection_reason": inbound["reason"],
                "final_output": (
                    "This request was blocked by the "
                    "inbound payload analyzer before "
                    "the model ran."
                ),
                "client_id": inbound_client,
                "inbound_scan": inbound,
                "detection_log": build_detection_log(
                    payload=inbound,
                    inbound_blocked=True,
                ),
                "protection_enabled": True,
            }

        policy = get_active_policy(
            request.client_id
        )

        client_id = str(
            policy.get(
                "client_id",
                request.client_id or "default",
            )
        )

        protection_enabled = (
            get_protection_enabled(client_id)
        )

        if not protection_enabled:
            database_context = (
                get_database_context()
            )
            model_prompt = (
                build_unprotected_chat_prompt(
                    user_prompt=user_prompt,
                    database_context=database_context,
                )
            )
            raw_ai_output = ask_gemini(
                model_prompt
            )

            matched_secret_name = (
                match_secret_name_for_prompt(
                    user_prompt
                )
            )

            if matched_secret_name is not None:
                secret_answer = (
                    find_secret_answer_for_prompt(
                        user_prompt
                    )
                )

                if secret_answer is not None:
                    secret_value = (
                        secret_answer.split(":", 1)[-1]
                        .strip()
                    )
                    value_missing = (
                        secret_value.lower()
                        not in raw_ai_output.lower()
                    )

                    if (
                        looks_like_model_refusal(
                            raw_ai_output
                        )
                        or value_missing
                    ):
                        raw_ai_output = secret_answer

            matched_salary_name = (
                match_salary_employee_for_prompt(
                    user_prompt
                )
            )

            if matched_salary_name is not None:
                salary_answer = (
                    get_employee_salary_by_name(
                        matched_salary_name
                    )
                )

                if salary_answer is not None and (
                    looks_like_model_refusal(
                        raw_ai_output
                    )
                    or "salary"
                    not in raw_ai_output.lower()
                ):
                    raw_ai_output = salary_answer

            save_audit_log(
                user_prompt=user_prompt,
                raw_output=raw_ai_output,
                shield_status="BYPASSED",
                risk_score=0,
                detection_reason=(
                    "WRDN Protection Disabled - "
                    "raw AI output returned without shielding"
                ),
                client_id=client_id,
                username=(request.username or "").strip(),
                policy_id=policy.get("policy_id"),
                policy_version=policy.get(
                    "version",
                    1,
                ),
                requirement_file_id=policy.get(
                    "requirement_file_id"
                ),
                detection_layer=(
                    "Protection Disabled"
                ),
                matched_rule=(
                    "BYPASSED"
                ),
            )

            return {
                "user_prompt": user_prompt,
                "raw_ai_output": raw_ai_output,
                "shield_status": "BYPASSED",
                "risk_score": 0,
                "detection_layer": (
                    "Protection Disabled"
                ),
                "detection_reason": (
                    "WRDN protection is disabled. "
                    "Showing raw AI output for demo comparison."
                ),
                "final_output": raw_ai_output,
                "client_id": client_id,
                "policy_id": policy.get(
                    "policy_id"
                ),
                "policy_version": policy.get(
                    "version",
                    1,
                ),
                "protection_enabled": False,
            }

        block_threshold = int(
            policy.get(
                "risk_threshold",
                BLOCK_THRESHOLD,
            )
        )

        embedding_threshold = float(
            policy.get(
                "embedding_threshold",
                EMBEDDING_SIMILARITY_THRESHOLD,
            )
        )

        blocked_categories = policy.get(
            "blocked_categories",
            [],
        )

        allowed_secret_names = normalize_name_list(
            policy.get("allowed_secret_names")
        )
        blocked_secret_names = normalize_name_list(
            policy.get("blocked_secret_names")
        )
        allowed_employee_salary_names = (
            normalize_name_list(
                policy.get(
                    "allowed_employee_salary_names"
                )
            )
        )
        blocked_employee_salary_names = (
            normalize_name_list(
                policy.get(
                    "blocked_employee_salary_names"
                )
            )
        )

        blocked_response = policy.get(
            "blocked_response",
            (
                "This output was blocked by "
                "the WRDN security policy."
            ),
        )

        input_block = input_intent_policy_check(
            user_prompt=user_prompt,
            blocked_categories=blocked_categories,
            blocked_response=blocked_response,
            allowed_secret_names=allowed_secret_names,
            blocked_secret_names=blocked_secret_names,
            allowed_employee_salary_names=(
                allowed_employee_salary_names
            ),
            blocked_employee_salary_names=(
                blocked_employee_salary_names
            ),
        )

        if input_block is not None:
            save_audit_log(
                user_prompt=user_prompt,
                raw_output="",
                shield_status=input_block["status"],
                risk_score=input_block["risk_score"],
                detection_reason=(
                    f"{input_block['layer']} - "
                    f"{input_block['reason']}"
                ),
                client_id=policy.get(
                    "client_id",
                    "default",
                ),
                username=(request.username or "").strip(),
                policy_id=policy.get(
                    "policy_id"
                ),
                policy_version=policy.get(
                    "version",
                    1,
                ),
                requirement_file_id=policy.get(
                    "requirement_file_id"
                ),
                detection_layer=input_block[
                    "layer"
                ],
                matched_rule=input_block[
                    "reason"
                ],
            )

            return {
                "user_prompt": user_prompt,
                "raw_ai_output": "[HIDDEN BY WRDN]",
                "shield_status": input_block[
                    "status"
                ],
                "risk_score": input_block[
                    "risk_score"
                ],
                "detection_layer": input_block[
                    "layer"
                ],
                "detection_reason": input_block[
                    "reason"
                ],
                "final_output": input_block[
                    "final_output"
                ],
                "client_id": policy.get(
                    "client_id",
                    "default",
                ),
                "policy_id": policy.get(
                    "policy_id"
                ),
                "policy_version": policy.get(
                    "version",
                    1,
                ),
                "protection_enabled": True,
            }

        database_context = (
            get_database_context()
        )

        model_prompt = build_chat_model_prompt(
            user_prompt=user_prompt,
            database_context=database_context,
            blocked_categories=blocked_categories,
            allowed_secret_names=allowed_secret_names,
            blocked_secret_names=blocked_secret_names,
            allowed_employee_salary_names=(
                allowed_employee_salary_names
            ),
            blocked_employee_salary_names=(
                blocked_employee_salary_names
            ),
            explanation=str(
                policy.get("explanation", "")
            ),
        )

        raw_ai_output = ask_gemini(
            model_prompt
        )

        # demo reliability: fill allowed secrets/salaries
        # from SQLite when Gemini refuses or omits values.
        credentials_blocked = (
            "credentials"
            in {
                str(item).strip().lower()
                for item in (blocked_categories or [])
                if str(item).strip()
            }
        )
        financial_blocked = (
            "financial_records"
            in {
                str(item).strip().lower()
                for item in (blocked_categories or [])
                if str(item).strip()
            }
            or "employee_information"
            in {
                str(item).strip().lower()
                for item in (blocked_categories or [])
                if str(item).strip()
            }
        )

        matched_secret_name = (
            match_secret_name_for_prompt(
                user_prompt
            )
        )

        if matched_secret_name is not None:
            can_reveal = secret_is_allowed_by_policy(
                secret_name=matched_secret_name,
                allowed_secret_names=allowed_secret_names,
                blocked_secret_names=blocked_secret_names,
                credentials_blocked=credentials_blocked,
            )

            if can_reveal:
                secret_answer = (
                    find_secret_answer_for_prompt(
                        user_prompt
                    )
                )

                if secret_answer is not None:
                    secret_value = (
                        secret_answer.split(":", 1)[-1]
                        .strip()
                    )
                    value_missing = (
                        secret_value.lower()
                        not in raw_ai_output.lower()
                    )

                    if (
                        looks_like_model_refusal(
                            raw_ai_output
                        )
                        or value_missing
                    ):
                        raw_ai_output = secret_answer

        matched_salary_name = (
            match_salary_employee_for_prompt(
                user_prompt
            )
        )

        if matched_salary_name is not None:
            can_reveal_salary = (
                salary_is_allowed_by_policy(
                    employee_name=matched_salary_name,
                    allowed_employee_salary_names=(
                        allowed_employee_salary_names
                    ),
                    blocked_employee_salary_names=(
                        blocked_employee_salary_names
                    ),
                    financial_blocked=financial_blocked,
                )
            )

            if can_reveal_salary:
                salary_answer = (
                    get_employee_salary_by_name(
                        matched_salary_name
                    )
                )

                if salary_answer is not None and (
                    looks_like_model_refusal(
                        raw_ai_output
                    )
                    or "salary"
                    not in raw_ai_output.lower()
                ):
                    raw_ai_output = salary_answer

        # policy Judge LLM receives allow/block rules from
        # the requirement-generated policy.
        try:
            shield = judge_output_against_policy(
                user_prompt=user_prompt,
                raw_ai_output=raw_ai_output,
                policy=policy,
            )
        except Exception as judge_error:
            logger.warning(
                "Policy judge failed; falling back to "
                "regex/embedding sanitizer: %s",
                judge_error,
            )
            shield = final_output_sanitizer(
                raw_ai_output,
                block_threshold=block_threshold,
                embedding_threshold=embedding_threshold,
                blocked_response=blocked_response,
                sensitive_pattern_ids=policy.get(
                    "sensitive_pattern_ids",
                    [],
                ),
                blocked_categories=blocked_categories,
            )

        # hard regex backup only when credentials are broadly
        # blocked and judge allowed something suspicious.
        if (
            credentials_blocked
            and shield.get("status") == "ALLOWED"
            and not allowed_secret_names
        ):
            regex_backup = regex_output_sanitizer(
                raw_ai_output,
                block_threshold=block_threshold,
                sensitive_pattern_ids=policy.get(
                    "sensitive_pattern_ids",
                    [],
                ),
                blocked_categories=blocked_categories,
            )

            if regex_backup.get("blocked"):
                shield = {
                    "allowed": False,
                    "status": "BLOCKED",
                    "risk_score": regex_backup[
                        "risk_score"
                    ],
                    "layer": "Regex Output Sanitizer",
                    "reason": regex_backup["reason"],
                    "final_output": blocked_response,
                }

        # project-wide rule: BLOCKED means forbidden request,
        # allowed means permitted request with usable answer.
        shield = enforce_allow_block_semantics(
            user_prompt=user_prompt,
            raw_ai_output=raw_ai_output,
            shield=shield,
            policy=policy,
            blocked_response=blocked_response,
            allowed_secret_names=allowed_secret_names,
            blocked_secret_names=blocked_secret_names,
            allowed_employee_salary_names=(
                allowed_employee_salary_names
            ),
            blocked_employee_salary_names=(
                blocked_employee_salary_names
            ),
            blocked_categories=blocked_categories,
        )

        # Keep raw_ai_output aligned with final answer text
        # when semantics filled an allowed value.
        if shield.get("status") == "ALLOWED":
            raw_ai_output = str(
                shield.get(
                    "final_output",
                    raw_ai_output,
                )
            )

        save_audit_log(
    user_prompt=user_prompt,
    raw_output=raw_ai_output,
    shield_status=shield["status"],
            risk_score=shield[
                "risk_score"
            ],
            detection_reason=(
                f"{shield['layer']} - "
                f"{shield['reason']}"
            ),
            client_id=policy.get(
                "client_id",
                "default",
            ),
            username=(request.username or "").strip(),
            policy_id=policy.get(
                "policy_id"
            ),
            policy_version=policy.get(
                "version",
                1,
            ),
            requirement_file_id=policy.get(
                "requirement_file_id"
            ),
            detection_layer=shield[
                "layer"
            ],
            matched_rule=shield[
                "reason"
            ],
        )

        return {
            "user_prompt": user_prompt,
            "raw_ai_output": (
                raw_ai_output
                if shield["status"]
                == "ALLOWED"
                else (
                    "[HIDDEN BY WRDN]"
                )
            ),
            "shield_status": shield[
                "status"
            ],
            "risk_score": shield[
                "risk_score"
            ],
            "detection_layer": shield[
                "layer"
            ],
            "detection_reason": shield[
                "reason"
            ],
                        "final_output": shield[
                "final_output"
            ],
            "client_id": policy.get(
                "client_id",
                "default",
            ),
            "policy_id": policy.get(
                "policy_id"
            ),
            "policy_version": policy.get(
                "version",
                1,
            ),
            "protection_enabled": True,
            "detection_log": build_detection_log(
                payload=inbound,
                leak={
                    "leaked": str(
                        shield.get("status")
                    ).upper()
                    == "BLOCKED"
                    and "leak"
                    in str(
                        shield.get("reason") or ""
                    ).lower(),
                    "risk_score": int(
                        shield.get("risk_score") or 0
                    ),
                    "reason": shield.get("reason"),
                },
                inbound_blocked=False,
            ),
        }

    except Exception as error:
        logger.exception(
            "Chat request failed."
        )

        error_message = str(error)

        temporary_service_error = any(
            value
            in error_message.lower()
            for value in [
                "503",
                "unavailable",
                "high demand",
                "temporarily unavailable",
                "resource_exhausted",
            ]
        )

        if temporary_service_error:
            return {
                "status": (
                    "SERVICE_UNAVAILABLE"
                ),
                "shield_status": "ERROR",
                "risk_score": 0,
                "detection_layer": (
                    "Gemini Service"
                ),
                "detection_reason": (
                    error_message
                ),
                "error_type": (
                    "GEMINI_TEMPORARY_ERROR"
                ),
                "retryable": True,
                "error": error_message,
                "final_output": (
                    "Gemini is temporarily "
                    "busy. Please try again "
                    "in a few moments."
                ),
            }

        return {
            "status": "ERROR",
            "shield_status": "ERROR",
            "risk_score": 0,
            "detection_layer": (
                "Backend Processing"
            ),
            "detection_reason": (
                error_message
            ),
            "error_type": (
                "CHAT_PROCESSING_ERROR"
            ),
            "retryable": False,
            "error": error_message,
            "final_output": (
                "The AI request could "
                "not be completed."
            ),
        }


# =========================================================
# SANITIZE ROUTE
# =========================================================

@app.post("/sanitize")
def sanitize_only(
    request: PromptRequest,
) -> dict[str, Any]:
    try:
        raw_ai_output = (
            request.prompt.strip()
        )

        if not raw_ai_output:
            return {
                "status": "ERROR",
                "risk_score": 0,
                "reason": (
                    "Sanitizer input "
                    "cannot be empty."
                ),
                "detection_layer": (
                    "Input Validation"
                ),
                "final_output": "",
            }

        shield = (
            final_output_sanitizer(
                raw_ai_output
            )
        )

        return {
            "status": shield["status"],
            "risk_score": shield[
                "risk_score"
            ],
            "reason": shield["reason"],
            "detection_layer": shield[
                "layer"
            ],
            "final_output": (
                shield["final_output"]
                if shield["allowed"]
                else (
                    "[BLOCKED] Sensitive "
                    "or unsafe AI output "
                    "was removed."
                )
            ),
        }

    except Exception as error:
        logger.exception(
            "Sanitizer request failed."
        )

        return {
            "status": "ERROR",
            "risk_score": 0,
            "reason": (
                f"Sanitizer error: {error}"
            ),
            "detection_layer": (
                "Sanitizer Error"
            ),
            "final_output": (
                "[BLOCKED] Sanitizer "
                "failed, so the output "
                "was not released."
            ),
        }