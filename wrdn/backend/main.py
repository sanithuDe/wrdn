from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

import requests
import re
import logging
import pyodbc
import json

from database import get_database_context, save_audit_log
from embedding_security import embedding_risk_check


app = FastAPI(title="WRDN Output Sanitizer Backend")

logging.basicConfig(level=logging.DEBUG)
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


class PromptRequest(BaseModel):
    prompt: str


OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
MAIN_MODEL = "llama3.2"
BLOCK_THRESHOLD = 70

# Project root path:
# wrdn/backend/main.py -> parent.parent = wrdn/
BASE_DIR = Path(__file__).resolve().parent.parent

# Registry file path:
# wrdn/demo-wrdn--simulator/Database/registry.txt
REGISTRY_FILE = BASE_DIR / "demo-wrdn--simulator" / "Database" / "registry.txt"


@app.get("/")
def home():
    return {
        "message": "WRDN Output Sanitizer backend running",
        "available_endpoints": [
            "GET /",
            "GET /api/health",
            "GET /api/registry",
            "POST /chat",
            "POST /sanitize",
        ],
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "running",
        "service": "WRDN Backend API",
        "registry_file": str(REGISTRY_FILE),
        "registry_exists": REGISTRY_FILE.exists(),
    }


@app.get("/api/registry")
def get_registry():
    """
    Reads live registry data from:
    wrdn/demo-wrdn--simulator/Database/registry.txt

    Frontend can call:
    GET http://localhost:8000/api/registry
    """
    try:
        if not REGISTRY_FILE.exists():
            return {
                "company_name": "WRDN Enterprise",
                "database_status": "NOT_FOUND",
                "candidate_evaluations": [],
                "blocked_emails": [],
                "error": f"Registry file not found: {str(REGISTRY_FILE)}",
            }

        content = REGISTRY_FILE.read_text(encoding="utf-8").strip()

        if not content:
            return {
                "company_name": "WRDN Enterprise",
                "database_status": "EMPTY",
                "candidate_evaluations": [],
                "blocked_emails": [],
            }

        data = json.loads(content)

        # Safety defaults if fields are missing
        return {
            "company_name": data.get("company_name", "WRDN Enterprise"),
            "database_status": data.get("database_status", "UNKNOWN"),
            "candidate_evaluations": data.get("candidate_evaluations", []),
            "blocked_emails": data.get("blocked_emails", []),
        }

    except json.JSONDecodeError as error:
        logger.error("Invalid registry JSON: %s", str(error))

        return {
            "company_name": "WRDN Enterprise",
            "database_status": "INVALID_JSON",
            "candidate_evaluations": [],
            "blocked_emails": [],
            "error": str(error),
        }

    except Exception as error:
        logger.error("Registry read error: %s", str(error))

        return {
            "company_name": "WRDN Enterprise",
            "database_status": "ERROR",
            "candidate_evaluations": [],
            "blocked_emails": [],
            "error": str(error),
        }


def redact_sensitive_parts(raw_ai_output: str):
    redacted_output = raw_ai_output

    salary_patterns = [
        r"(salary\s*[:=]\s*)(?:rs\.?|lkr|\$)?\s*\d+(?:,\d{3})*(?:\.\d+)?",
        r"(manager\s+salary\s*[:=]\s*)(?:rs\.?|lkr|\$)?\s*\d+(?:,\d{3})*(?:\.\d+)?",
        r"(employee\s+salary\s*[:=]\s*)(?:rs\.?|lkr|\$)?\s*\d+(?:,\d{3})*(?:\.\d+)?",
        r"(salary\s+is\s+)(?:rs\.?|lkr|\$)?\s*\d+(?:,\d{3})*(?:\.\d+)?",
    ]

    for pattern in salary_patterns:
        redacted_output = re.sub(
            pattern,
            r"\1[BLOCKED]",
            redacted_output,
            flags=re.IGNORECASE,
        )

    return redacted_output


def regex_output_sanitizer(raw_ai_output: str):
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
        r"\binternal database\b": 80,
        r"\bdatabase record\b": 80,
        r"\bconfidential\b": 80,
    }

    highest_score = 0
    reasons = []

    for pattern, score in patterns.items():
        if re.search(pattern, raw_ai_output, re.IGNORECASE):
            highest_score = max(highest_score, score)
            reasons.append(f"Raw AI output matched pattern: {pattern}")

    return {
        "blocked": highest_score >= BLOCK_THRESHOLD,
        "risk_score": highest_score,
        "reason": ", ".join(reasons)
        if reasons
        else "No regex risk detected in raw AI output",
    }


def final_output_sanitizer(raw_ai_output: str):
    regex_result = regex_output_sanitizer(raw_ai_output)
    embedding_result = embedding_risk_check(raw_ai_output)

    final_risk_score = max(
        regex_result["risk_score"],
        embedding_result["risk_score"],
    )

    if final_risk_score >= BLOCK_THRESHOLD:
        safe_redacted_output = redact_sensitive_parts(raw_ai_output)

        return {
            "allowed": False,
            "risk_score": final_risk_score,
            "layer": "Output Sanitizer",
            "reason": (
                regex_result["reason"]
                if regex_result["risk_score"] >= embedding_result["risk_score"]
                else embedding_result["reason"]
            ),
            "final_output": safe_redacted_output,
        }

    return {
        "allowed": True,
        "risk_score": final_risk_score,
        "layer": "Output Sanitizer",
        "reason": "Raw AI output passed regex and embedding checks",
        "final_output": raw_ai_output,
    }


@app.post("/chat")
def chat(request: PromptRequest):
    try:
        database_context = get_database_context()

        model_prompt = f"""
You are an enterprise AI assistant connected to a company SQL Server database.

Internal database content:
{database_context}

User question:
{request.prompt}

Answer the user based on the database.
"""

        response = requests.post(
            OLLAMA_GENERATE_URL,
            json={
                "model": MAIN_MODEL,
                "prompt": model_prompt,
                "stream": False,
            },
            timeout=120,
        )

        response.raise_for_status()

        raw_ai_output = response.json().get("response", "")

        logger.debug("RAW AI OUTPUT: %s", raw_ai_output)

        shield = final_output_sanitizer(raw_ai_output)

        shield_status = (
            "BLOCKED"
            if shield["risk_score"] >= BLOCK_THRESHOLD
            else "ALLOWED"
        )

        save_audit_log(
            request.prompt,
            raw_ai_output,
            shield_status,
            shield["risk_score"],
            f"{shield['layer']} - {shield['reason']}",
        )

        return {
            "user_prompt": request.prompt,
            "raw_ai_output": raw_ai_output,
            "shield_status": shield_status,
            "risk_score": shield["risk_score"],
            "detection_layer": shield["layer"],
            "detection_reason": shield["reason"],
            "final_output": shield["final_output"],
        }

    except Exception as e:
        logger.error("Chat error: %s", str(e))
        return {
            "error": str(e),
        }


@app.post("/sanitize")
def sanitize_only(request: PromptRequest):
    """
    Sanitize endpoint - checks output for sensitive data.
    """
    try:
        raw_ai_output = request.prompt

        regex_result = regex_output_sanitizer(raw_ai_output)
        embedding_result = embedding_risk_check(raw_ai_output)

        final_risk_score = max(
            regex_result["risk_score"],
            embedding_result["risk_score"],
        )

        if final_risk_score >= BLOCK_THRESHOLD:
            return {
                "status": "BLOCKED",
                "risk_score": final_risk_score,
                "reason": "Output blocked by WRDN sanitizer",
                "final_output": "[BLOCKED] Sensitive or unsafe AI output was removed.",
            }

        return {
            "status": "ALLOWED",
            "risk_score": final_risk_score,
            "reason": "Output passed sanitizer",
            "final_output": raw_ai_output,
        }

    except Exception as e:
        logger.error("Sanitizer error: %s", str(e))

        return {
            "status": "ERROR",
            "risk_score": 0,
            "reason": f"Sanitizer error: {str(e)}",
            "final_output": f"[ERROR] {str(e)}",
        }