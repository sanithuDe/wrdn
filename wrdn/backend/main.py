from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import re
import logging

from database import get_database_context, save_audit_log
from embedding_security import embedding_risk_check

app = FastAPI()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("wrdn.backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PromptRequest(BaseModel):
    prompt: str


class SanitizeRequest(BaseModel):
    raw_ai_output: str


@app.get("/")
def home():
    return {"message": "WRDN Output Sanitizer backend running"}


OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
MAIN_MODEL = "llama3.2"
BLOCK_THRESHOLD = 70


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
            flags=re.IGNORECASE
        )

    return redacted_output


def regex_output_sanitizer(raw_ai_output: str):
    patterns = {
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
        "reason": ", ".join(reasons) if reasons else "No regex risk detected in raw AI output"
    }


def final_output_sanitizer(raw_ai_output: str):
    regex_result = regex_output_sanitizer(raw_ai_output)
    embedding_result = embedding_risk_check(raw_ai_output)

    final_risk_score = max(
        regex_result["risk_score"],
        embedding_result["risk_score"]
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
            "final_output": safe_redacted_output
        }

    return {
        "allowed": True,
        "risk_score": final_risk_score,
        "layer": "Output Sanitizer",
        "reason": "Raw AI output passed regex and embedding checks",
        "final_output": raw_ai_output
    }


@app.post("/sanitize")
def sanitize(request: SanitizeRequest):
    try:
        shield = final_output_sanitizer(request.raw_ai_output)

        shield_status = "BLOCKED" if shield["risk_score"] >= BLOCK_THRESHOLD else "ALLOWED"

        return {
            "raw_ai_output": request.raw_ai_output,
            "shield_status": shield_status,
            "risk_score": shield["risk_score"],
            "detection_layer": shield["layer"],
            "detection_reason": shield["reason"],
            "final_output": shield["final_output"]
        }

    except Exception as e:
        logger.error("Sanitize error: %s", str(e))
        return {"error": str(e)}


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
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()

        raw_ai_output = response.json().get("response", "")

        logger.debug("RAW AI OUTPUT: %s", raw_ai_output)

        shield = final_output_sanitizer(raw_ai_output)

        shield_status = "BLOCKED" if shield["risk_score"] >= BLOCK_THRESHOLD else "ALLOWED"

        save_audit_log(
            request.prompt,
            raw_ai_output,
            shield_status,
            shield["risk_score"],
            f"{shield['layer']} - {shield['reason']}"
        )

        return {
            "user_prompt": request.prompt,
            "raw_ai_output": raw_ai_output,
            "shield_status": shield_status,
            "risk_score": shield["risk_score"],
            "detection_layer": shield["layer"],
            "detection_reason": shield["reason"],
            "final_output": shield["final_output"]
        }

    except Exception as e:
        logger.error("Error: %s", str(e))
        return {"error": str(e)}
    
    # ADD NEW ENDPOINT HERE
@app.post("/sanitize")
def sanitize_only(request: PromptRequest):
    raw_ai_output = request.prompt

    regex_result = regex_output_sanitizer(raw_ai_output)
    embedding_result = embedding_risk_check(raw_ai_output)

    final_risk_score = max(
        regex_result["risk_score"],
        embedding_result["risk_score"]
    )

    if final_risk_score >= BLOCK_THRESHOLD:
        return {
            "status": "BLOCKED",
            "risk_score": final_risk_score,
            "reason": "Output blocked by WRDN sanitizer",
            "final_output": "[BLOCKED] Sensitive or unsafe AI output was removed."
        }

    return {
        "status": "ALLOWED",
        "risk_score": final_risk_score,
        "reason": "Output passed sanitizer",
        "final_output": raw_ai_output
    }