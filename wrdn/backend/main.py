from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import re

from database import get_database_context, save_audit_log

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PromptRequest(BaseModel):
    prompt: str

@app.get("/")
def home():
    return {"message": "WRDN Prompt Shield backend running with SQL Server"}


def output_sanitizer(ai_output):
    patterns = {
        r"admin@12345": "Admin password leaked",
        r"sk-test-company-secret-key-999": "API key leaked",
        r"db_pass_2026_secret": "Database password leaked",
        r"aws-root-secret-2026": "AWS root key leaked",
        r"vpn-company-pass": "VPN password leaked",
        r"jwt-prod-token-123456": "JWT token leaked",
        r"azure-access-secret-999": "Azure access token leaked",
        r"openai-company-token-777": "Internal token leaked",
        r"password": "Password keyword detected",
        r"api key": "API key keyword detected",
        r"secret": "Secret keyword detected",
        r"token": "Token keyword detected",
        r"confidential": "Confidential keyword detected",
        r"salary": "Salary data detected"
    }

    risk_score = 0
    reasons = []

    for pattern, reason in patterns.items():
        if re.search(pattern, ai_output, re.IGNORECASE):
            risk_score += 20
            reasons.append(reason)

    if risk_score >= 20:
        return {
            "allowed": False,
            "risk_score": risk_score,
            "reason": ", ".join(reasons),
            "final_output": "Blocked by WRDN Prompt Shield: Sensitive enterprise data was detected in the AI response."
        }

    return {
        "allowed": True,
        "risk_score": risk_score,
        "reason": "No sensitive output detected",
        "final_output": ai_output
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
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2",
                "prompt": model_prompt,
                "stream": False
            }
        )

        raw_ai_output = response.json().get("response", "")

        shield = output_sanitizer(raw_ai_output)

        shield_status = "ALLOWED" if shield["allowed"] else "BLOCKED"

        save_audit_log(
            request.prompt,
            raw_ai_output,
            shield_status,
            shield["risk_score"],
            shield["reason"]
        )

        return {
            "user_prompt": request.prompt,
            "raw_ai_output": raw_ai_output,
            "shield_status": shield_status,
            "risk_score": shield["risk_score"],
            "detection_reason": shield["reason"],
            "final_output": shield["final_output"]
        }

    except Exception as e:
        return {"error": str(e)}
    