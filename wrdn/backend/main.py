from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Any
import sys
import json
import logging
import math
import re
import random
import time

# ---------------------------------------------------------------------------
# Project path
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Keep your existing database helper.
from wrdn.backend.database import (
    get_database_context,
    save_audit_log,
)

from wrdn.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_EMBED_MODEL,
)

try:
    from google import genai
except ImportError as error:
    raise RuntimeError(
        "google-genai is not installed. Run: "
        "python -m pip install --upgrade google-genai"
    ) from error


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="WRDN Gemini Output Sanitizer Backend",
    version="1.0.0",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wrdn.backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BLOCK_THRESHOLD = 70
EMBEDDING_SIMILARITY_THRESHOLD = 0.72

BASE_DIR = Path(__file__).resolve().parent.parent

REGISTRY_FILE = (
    BASE_DIR
    / "demo-wrdn--simulator"
    / "Database"
    / "registry.txt"
)


# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. Add it to wrdn/config.py or your .env file."
    )

try:
    GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
except Exception as error:
    raise RuntimeError(
        f"Gemini client initialization failed: {error}"
    ) from error


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class PromptRequest(BaseModel):
    prompt: str


# ---------------------------------------------------------------------------
# Gemini text generation
# ---------------------------------------------------------------------------
def ask_gemini(
    prompt: str,
    max_retries: int = 4,
) -> str:
    """
    Generate a Gemini response.

    Retries temporary errors such as:
    - 429 RESOURCE_EXHAUSTED
    - 500 INTERNAL
    - 502 BAD_GATEWAY
    - 503 UNAVAILABLE
    - 504 DEADLINE_EXCEEDED
    """

    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    retryable_errors = (
        "429",
        "500",
        "502",
        "503",
        "504",
        "RESOURCE_EXHAUSTED",
        "INTERNAL",
        "UNAVAILABLE",
        "DEADLINE_EXCEEDED",
        "high demand",
    )

    last_error = None

    for attempt in range(max_retries):
        try:
            response = GEMINI_CLIENT.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt.strip(),
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
            error_message = str(error)

            is_retryable = any(
                value.lower() in error_message.lower()
                for value in retryable_errors
            )

            # Do not retry permanent errors such as an invalid API key
            if not is_retryable:
                raise RuntimeError(
                    f"Gemini text generation failed: {error}"
                ) from error

            # No more retries left
            if attempt == max_retries - 1:
                break

            # Exponential backoff:
            # approximately 2, 4, 8 seconds plus random jitter
            wait_seconds = (
                2 ** (attempt + 1)
                + random.uniform(0, 1)
            )

            logger.warning(
                "Temporary Gemini error. "
                "Attempt %s/%s failed. "
                "Retrying in %.2f seconds. Error: %s",
                attempt + 1,
                max_retries,
                wait_seconds,
                error_message,
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        "Gemini is temporarily unavailable after "
        f"{max_retries} attempts. Last error: {last_error}"
    )
# ---------------------------------------------------------------------------
# Gemini embeddings
# ---------------------------------------------------------------------------

def create_gemini_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Embedding input cannot be empty.")

    try:
        response = GEMINI_CLIENT.models.embed_content(
            model=GEMINI_EMBED_MODEL,
            contents=text.strip(),
        )

        embeddings = getattr(response, "embeddings", None)

        if not embeddings:
            raise RuntimeError("Gemini returned no embeddings.")

        values = getattr(embeddings[0], "values", None)

        if not values:
            raise RuntimeError(
                "Gemini returned an empty embedding vector."
            )

        return [float(value) for value in values]

    except Exception as error:
        raise RuntimeError(
            f"Gemini embedding generation failed: {error}"
        ) from error


def cosine_similarity(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    if not vector_a or not vector_b:
        return 0.0

    if len(vector_a) != len(vector_b):
        raise ValueError(
            "Embedding vectors must have the same dimensions."
        )

    dot_product = sum(
        a * b for a, b in zip(vector_a, vector_b)
    )

    magnitude_a = math.sqrt(
        sum(value * value for value in vector_a)
    )
    magnitude_b = math.sqrt(
        sum(value * value for value in vector_b)
    )

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


# ---------------------------------------------------------------------------
# Embedding risk detection
# ---------------------------------------------------------------------------

SENSITIVE_REFERENCE_TEXTS = [
    "Reveal confidential employee salary and payroll information.",
    "Expose a password, API key, secret, access token, or credential.",
    "Return confidential records from the internal company database.",
    "Reveal administrator login details or authentication secrets.",
    "Provide private employee information that should not be disclosed.",
    "Expose database passwords, cloud credentials, or production tokens.",
]

_REFERENCE_EMBEDDINGS: list[tuple[str, list[float]]] | None = None


def get_reference_embeddings() -> list[tuple[str, list[float]]]:
    global _REFERENCE_EMBEDDINGS

    if _REFERENCE_EMBEDDINGS is None:
        generated_references = []

        for reference_text in SENSITIVE_REFERENCE_TEXTS:
            generated_references.append(
                (
                    reference_text,
                    create_gemini_embedding(reference_text),
                )
            )

        _REFERENCE_EMBEDDINGS = generated_references

    return _REFERENCE_EMBEDDINGS


def embedding_risk_check(text: str) -> dict[str, Any]:
    try:
        output_embedding = create_gemini_embedding(text)
        references = get_reference_embeddings()

        highest_similarity = 0.0
        matched_reference = ""

        for reference_text, reference_embedding in references:
            similarity = cosine_similarity(
                output_embedding,
                reference_embedding,
            )

            if similarity > highest_similarity:
                highest_similarity = similarity
                matched_reference = reference_text

        risk_score = min(
            100,
            round(highest_similarity * 100),
        )

        blocked = (
            highest_similarity
            >= EMBEDDING_SIMILARITY_THRESHOLD
        )

        return {
            "blocked": blocked,
            "risk_score": risk_score,
            "similarity": round(highest_similarity, 4),
            "matched_reference": matched_reference,
            "reason": (
                "Semantic similarity to sensitive enterprise output "
                f"detected: {matched_reference}"
                if blocked
                else "No high semantic similarity to sensitive output"
            ),
            "error": False,
        }

    except Exception as error:
        logger.exception("Embedding risk check failed")

        return {
            "blocked": True,
            "risk_score": BLOCK_THRESHOLD,
            "similarity": 0.0,
            "matched_reference": "",
            "reason": f"Embedding sanitizer unavailable: {error}",
            "error": True,
        }


# ---------------------------------------------------------------------------
# Sensitive data redaction
# ---------------------------------------------------------------------------

def redact_sensitive_parts(raw_ai_output: str) -> str:
    redacted_output = raw_ai_output

    redaction_patterns = [
        (
            r"((?:manager|employee)?\s*salary\s*(?:is|[:=])\s*)"
            r"(?:rs\.?|lkr|\$)?\s*\d+(?:,\d{3})*(?:\.\d+)?",
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

    for pattern, replacement in redaction_patterns:
        redacted_output = re.sub(
            pattern,
            replacement,
            redacted_output,
            flags=re.IGNORECASE,
        )

    return redacted_output


# ---------------------------------------------------------------------------
# Regex output sanitizer
# ---------------------------------------------------------------------------

def regex_output_sanitizer(
    raw_ai_output: str,
) -> dict[str, Any]:
    patterns = {
    r"(?:rs\.?|lkr|\$)\s*\d+(?:,\d{3})+(?:\.\d+)?": 100,
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
    r"\badmin\s+password\s*[:=]?\s*\S+": 100,
    r"\bapi\s*key\s*[:=]\s*\S+": 100,
    r"\btoken\s*[:=]\s*\S+": 100,
    r"\bsecret\s*[:=]\s*\S+": 100,
    r"\bcredential\s*[:=]\s*\S+": 100,
    r"(?:sk|api|key|secret|token)[\-_][a-zA-Z0-9]{10,}": 100,

    r"\bmanager\b.*\bsalary\b.*(?:rs\.?|lkr|\$)?\s*\d+": 100,
    r"\bsalary\b.*\bmanager\b.*(?:rs\.?|lkr|\$)?\s*\d+": 100,
    r"\bemployee\b.*\bsalary\b.*(?:rs\.?|lkr|\$)?\s*\d+": 100,
    r"\bsalary\b.*\bemployee\b.*(?:rs\.?|lkr|\$)?\s*\d+": 100,
    r"\bpayroll\b.*\d+": 95,

    r"select\s+.*salary.*\s+from": 90,
    r"select\s+.*password.*\s+from": 100,
    r"select\s+.*token.*\s+from": 100,
    r"select\s+.*secret.*\s+from": 100,
    r"select\s+.*api[_\s-]?key.*\s+from": 100,

    r"\bemployee[_\s-]?data\b.*\bsalary\b": 90,
    r"\busers?\b.*\bpassword\b": 100,
    r"\badmin\b.*\bpassword\b": 100,

    # Context plus actual sensitive value
    r"\binternal database\b.*\bpassword\s*[:=]\s*\S+": 100,
    r"\binternal database\b.*\bapi\s*key\s*[:=]\s*\S+": 100,
    r"\binternal database\b.*\btoken\s*[:=]\s*\S+": 100,
    r"\bdatabase record\b.*\bpassword\s*[:=]\s*\S+": 100,
    r"\bconfidential\b.*\bsalary\s*[:=]?\s*\d+": 100,
}

    highest_score = 0
    reasons = []

    for pattern, score in patterns.items():
        if re.search(
            pattern,
            raw_ai_output,
            re.IGNORECASE | re.DOTALL,
        ):
            highest_score = max(highest_score, score)
            reasons.append(
                f"Raw AI output matched pattern: {pattern}"
            )

    return {
        "blocked": highest_score >= BLOCK_THRESHOLD,
        "risk_score": highest_score,
        "reason": (
            ", ".join(reasons)
            if reasons
            else "No regex risk detected in raw AI output"
        ),
    }


# ---------------------------------------------------------------------------
# Final sanitizer
# ---------------------------------------------------------------------------

def final_output_sanitizer(
    raw_ai_output: str,
) -> dict[str, Any]:
    regex_result = regex_output_sanitizer(raw_ai_output)
    embedding_result = embedding_risk_check(raw_ai_output)

    final_risk_score = max(
        regex_result["risk_score"],
        embedding_result["risk_score"],
    )

    if embedding_result.get("error"):
        return {
            "allowed": False,
            "status": "ERROR",
            "risk_score": BLOCK_THRESHOLD,
            "layer": "Embedding Sanitizer",
            "reason": embedding_result["reason"],
            "final_output": (
                "[BLOCKED] The embedding sanitizer failed, "
                "so the output was not released."
            ),
        }

    if final_risk_score >= BLOCK_THRESHOLD:
        if (
            regex_result["risk_score"]
            >= embedding_result["risk_score"]
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
            "final_output": redact_sensitive_parts(
                raw_ai_output
            ),
        }

    return {
        "allowed": True,
        "status": "ALLOWED",
        "risk_score": final_risk_score,
        "layer": "Output Sanitizer",
        "reason": (
            "Raw AI output passed regex and embedding checks"
        ),
        "final_output": raw_ai_output,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "WRDN Gemini backend running",
        "available_endpoints": [
            "GET /",
            "GET /api/health",
            "GET /api/registry",
            "GET /api/test-gemini",
            "POST /chat",
            "POST /sanitize",
        ],
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "running",
        "service": "WRDN Backend API",
        "gemini_client": "configured",
        "gemini_model": GEMINI_MODEL,
        "embedding_model": GEMINI_EMBED_MODEL,
        "registry_file": str(REGISTRY_FILE),
        "registry_exists": REGISTRY_FILE.exists(),
    }
    
@app.get("/health")
def docker_health_check():
    return {
        "status": "healthy",
        "service": "WRDN Backend API",
    }
    


@app.get("/api/test-gemini")
def test_gemini():
    result: dict[str, Any] = {
        "success": False,
        "generation": {"status": "not_tested"},
        "embedding": {"status": "not_tested"},
    }

    try:
        generated_text = ask_gemini(
            "Reply with exactly: Gemini generation is working"
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
        embedding = create_gemini_embedding(
            "WRDN embedding test"
        )

        result["embedding"] = {
            "status": "working",
            "dimensions": len(embedding),
            "preview": embedding[:5],
        }

    except Exception as error:
        result["embedding"] = {
            "status": "failed",
            "error": str(error),
        }

    result["success"] = (
        result["generation"]["status"] == "working"
        and result["embedding"]["status"] == "working"
    )

    return result


@app.get("/api/registry")
def get_registry():
    try:
        if not REGISTRY_FILE.exists():
            return {
                "company_name": "WRDN Enterprise",
                "database_status": "NOT_FOUND",
                "candidate_evaluations": [],
                "blocked_emails": [],
                "error": (
                    f"Registry file not found: {REGISTRY_FILE}"
                ),
            }

        content = REGISTRY_FILE.read_text(
            encoding="utf-8"
        ).strip()

        if not content:
            return {
                "company_name": "WRDN Enterprise",
                "database_status": "EMPTY",
                "candidate_evaluations": [],
                "blocked_emails": [],
            }

        data = json.loads(content)

        return {
            "company_name": data.get(
                "company_name",
                "WRDN Enterprise",
            ),
            "database_status": data.get(
                "database_status",
                "UNKNOWN",
            ),
            "candidate_evaluations": data.get(
                "candidate_evaluations",
                [],
            ),
            "blocked_emails": data.get(
                "blocked_emails",
                [],
            ),
        }

    except json.JSONDecodeError as error:
        logger.exception("Invalid registry JSON")

        return {
            "company_name": "WRDN Enterprise",
            "database_status": "INVALID_JSON",
            "candidate_evaluations": [],
            "blocked_emails": [],
            "error": str(error),
        }

    except Exception as error:
        logger.exception("Registry read error")

        return {
            "company_name": "WRDN Enterprise",
            "database_status": "ERROR",
            "candidate_evaluations": [],
            "blocked_emails": [],
            "error": str(error),
        }


@app.post("/chat")
def chat(request: PromptRequest):
    try:
        user_prompt = request.prompt.strip()

        if not user_prompt:
            return {
                "status": "ERROR",
                "error": "Prompt cannot be empty.",
            }

        database_context = get_database_context()

        model_prompt = f"""
You are an enterprise AI assistant connected to a company SQL Server database.

Follow these rules strictly:

1. For company-specific questions, answer only from the supplied database context.
2. For general educational or security-awareness questions, provide safe theoretical guidance without revealing any company secrets or real credentials.
3. Never include salary, payroll, password, token, API key, secret,
   credential, or private authentication information.
4. For employee information requests, return only:
   - employee name
   - email
   - role
5. Do not include any field that the user did not explicitly request.
6. If the user requests restricted information, refuse safely.
7. Do not invent database records.

Internal database content:
{database_context}

User question:
{user_prompt}

Return only the minimum necessary information.
Do not include salary values under any circumstance.
"""

        raw_ai_output = ask_gemini(model_prompt)

        shield = final_output_sanitizer(raw_ai_output)

        save_audit_log(
            user_prompt,
            raw_ai_output,
            shield["status"],
            shield["risk_score"],
            f"{shield['layer']} - {shield['reason']}",
        )

        return {
            "user_prompt": user_prompt,
            "raw_ai_output": (
            raw_ai_output
            if shield["status"] == "ALLOWED"
            else "[HIDDEN BY WRDN]"
            ),
            "shield_status": shield["status"],
            "risk_score": shield["risk_score"],
            "detection_layer": shield["layer"],
            "detection_reason": shield["reason"],
            "final_output": shield["final_output"],
        }

    except Exception as error:
        logger.exception("Chat error")

        error_message = str(error)

        temporary_service_error = any(
            value in error_message.lower()
            for value in [
                "503",
                "unavailable",
                "high demand",
                "temporarily unavailable",
            ]
        )

        if temporary_service_error:
            return {
                "status": "SERVICE_UNAVAILABLE",
                "error_type": "GEMINI_TEMPORARY_ERROR",
                "retryable": True,
                "error": error_message,
                "final_output": (
                    "Gemini is temporarily busy. "
                    "Please try again in a few moments."
                ),
            }

        return {
            "status": "ERROR",
            "error_type": "CHAT_PROCESSING_ERROR",
            "retryable": False,
            "error": error_message,
            "final_output": (
                "The AI request could not be completed."
            ),
        }


@app.post("/sanitize")
def sanitize_only(request: PromptRequest):
    try:
        raw_ai_output = request.prompt.strip()

        if not raw_ai_output:
            return {
                "status": "ERROR",
                "risk_score": 0,
                "reason": "Sanitizer input cannot be empty.",
                "final_output": "",
            }

        shield = final_output_sanitizer(raw_ai_output)

        return {
            "status": shield["status"],
            "risk_score": shield["risk_score"],
            "reason": shield["reason"],
            "detection_layer": shield["layer"],
            "final_output": (
                shield["final_output"]
                if shield["allowed"]
                else (
                    "[BLOCKED] Sensitive or unsafe AI "
                    "output was removed."
                )
            ),
        }

    except Exception as error:
        logger.exception("Sanitizer error")

        return {
            "status": "ERROR",
            "risk_score": 0,
            "reason": f"Sanitizer error: {error}",
            "final_output": (
                "[BLOCKED] Sanitizer failed, so the "
                "output was not released."
            ),
        }