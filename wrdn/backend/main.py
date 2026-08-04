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
    get_audit_logs,
    get_database_context,
    initialize_database,
    save_audit_log,
    test_database_connection,
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


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:8085",
        "http://127.0.0.1:8085",
        "http://localhost:8090",
        "http://127.0.0.1:8090",
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


# =========================================================
# SECURITY CONFIGURATION
# =========================================================

BLOCK_THRESHOLD = 70
EMBEDDING_SIMILARITY_THRESHOLD = 0.72


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
            >= EMBEDDING_SIMILARITY_THRESHOLD
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
            "risk_score": BLOCK_THRESHOLD,
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

def regex_output_sanitizer(
    raw_ai_output: str,
) -> dict[str, Any]:
    """
    Detect known secret values and sensitive
    output patterns.
    """

    patterns = {
        (
            r"(?:rs\.?|lkr|\$)\s*"
            r"\d+(?:,\d{3})+(?:\.\d+)?"
        ): 100,

        r"\b\d{2,3},\d{3}\b": 100,

        r"admin@12345": 100,
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

        (
            r"\bemployee[_\s-]?data\b.*"
            r"\bsalary\b"
        ): 90,

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

        (
            r"\bconfidential\b.*"
            r"\bsalary\s*[:=]?\s*\d+"
        ): 100,
    }

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
            >= BLOCK_THRESHOLD
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
) -> dict[str, Any]:
    """
    Run regex and embedding security checks.
    """

    regex_result = (
        regex_output_sanitizer(
            raw_ai_output
        )
    )

    embedding_result = (
        embedding_risk_check(
            raw_ai_output
        )
    )

    final_risk_score = max(
        int(
            regex_result.get(
                "risk_score",
                0,
            )
        ),
        int(
            embedding_result.get(
                "risk_score",
                0,
            )
        ),
    )

    if embedding_result.get("error"):
        return {
            "allowed": False,
            "status": "ERROR",
            "risk_score": (
                BLOCK_THRESHOLD
            ),
            "layer": (
                "Embedding Sanitizer"
            ),
            "reason": (
                embedding_result[
                    "reason"
                ]
            ),
            "final_output": (
                "[BLOCKED] The embedding "
                "sanitizer failed, so the "
                "output was not released."
            ),
        }

    if final_risk_score >= BLOCK_THRESHOLD:
        if (
            regex_result["risk_score"]
            >= embedding_result[
                "risk_score"
            ]
        ):
            reason = (
                regex_result["reason"]
            )

            layer = (
                "Regex Output Sanitizer"
            )

        else:
            reason = (
                embedding_result["reason"]
            )

            layer = (
                "Embedding Output Sanitizer"
            )

        return {
            "allowed": False,
            "status": "BLOCKED",
            "risk_score": (
                final_risk_score
            ),
            "layer": layer,
            "reason": reason,
            "final_output": (
                redact_sensitive_parts(
                    raw_ai_output
                )
            ),
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
) -> dict[str, Any]:
    """
    Read allowed and blocked audit records
    from the local SQLite database.
    """

    try:
        database_info = (
            test_database_connection()
        )

        audit_logs = get_audit_logs(
            limit=500,
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

            if shield_status == "ALLOWED":
                allowed_logs.append(
                    log_record
                )
            else:
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
                database_info[
                    "audit_count"
                ]
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
# CHAT ROUTE
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

        database_context = (
            get_database_context()
        )

        model_prompt = f"""
You are the WRDN enterprise AI assistant.

You are connected to a local SQLite database stored inside
the WRDN project. You are not connected to an external SQL
Server, MySQL server, PostgreSQL server, or cloud database.

Follow these rules strictly:

1. For company-specific questions, answer only from the supplied
   local SQLite database context.

2. For general educational or security-awareness questions,
   provide safe theoretical guidance.

3. Never reveal salary, payroll, password, token, API key,
   secret, credential, private authentication information,
   national ID, phone number, or private address.

4. For employee-information requests, return only:
   - employee name
   - email
   - role

5. Do not include a field that the user did not request.

6. If the user requests restricted information, refuse safely.

7. Do not invent database records.

8. Do not claim that the system is connected to an external
   database.

Local SQLite database context:
{database_context}

User question:
{user_prompt}

Return only the minimum necessary response.
Do not include salary values under any circumstances.
"""

        raw_ai_output = ask_gemini(
            model_prompt
        )

        shield = (
            final_output_sanitizer(
                raw_ai_output
            )
        )

        save_audit_log(
            user_prompt=user_prompt,
            raw_output=raw_ai_output,
            shield_status=shield[
                "status"
            ],
            risk_score=shield[
                "risk_score"
            ],
            detection_reason=(
                f"{shield['layer']} - "
                f"{shield['reason']}"
            ),
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