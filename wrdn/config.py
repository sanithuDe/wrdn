import os
from pathlib import Path

from dotenv import load_dotenv


# =========================================================
# PROJECT PATHS
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_FILE)


# =========================================================
# GEMINI CONFIGURATION
# =========================================================

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    "",
).strip()

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-flash-lite-latest",
).strip()

GEMINI_EMBED_MODEL = os.getenv(
    "GEMINI_EMBED_MODEL",
    "gemini-embedding-001",
).strip()


# =========================================================
# EMAIL CONFIGURATION
# =========================================================

MAIL_USERNAME = os.getenv(
    "MAIL_USERNAME",
    "",
).strip()

MAIL_APP_PASSWORD = os.getenv(
    "MAIL_APP_PASSWORD",
    "",
).replace(" ", "").strip()

MAIL_FROM_NAME = os.getenv(
    "MAIL_FROM_NAME",
    "WRDN Security",
).strip()

SMTP_HOST = os.getenv(
    "SMTP_HOST",
    "smtp.gmail.com",
).strip()

SMTP_PORT = int(
    os.getenv(
        "SMTP_PORT",
        "587",
    )
)


# =========================================================
# APPLICATION URLS
# =========================================================

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:3000",
).rstrip("/")


# =========================================================
# REQUIREMENT APPROVAL CONFIGURATION
# =========================================================

APPROVAL_EXPIRE_MINUTES = int(
    os.getenv(
        "APPROVAL_EXPIRE_MINUTES",
        "30",
    )
)

MAX_REQUIREMENT_FILE_SIZE_MB = int(
    os.getenv(
        "MAX_REQUIREMENT_FILE_SIZE_MB",
        "2",
    )
)

MAX_REQUIREMENT_FILE_SIZE_BYTES = (
    MAX_REQUIREMENT_FILE_SIZE_MB
    * 1024
    * 1024
)


# =========================================================
# POLICY ACTIVATION EMAIL CONFIRMATION
# =========================================================

POLICY_APPROVAL_EMAIL = os.getenv(
    "POLICY_APPROVAL_EMAIL",
    "",
).strip()

POLICY_APPROVAL_NAME = os.getenv(
    "POLICY_APPROVAL_NAME",
    "Admin",
).strip()

POLICY_ACTIVATION_EXPIRE_MINUTES = int(
    os.getenv(
        "POLICY_ACTIVATION_EXPIRE_MINUTES",
        "60",
    )
)