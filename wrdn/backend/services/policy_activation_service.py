import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from wrdn.backend.database import (
    get_connection,
    get_current_utc_time,
    get_policy_activation_by_token,
    update_policy_activation_request,
)
from wrdn.backend.email_service import (
    send_policy_activation_email,
)
from wrdn.config import (
    FRONTEND_URL,
    POLICY_ACTIVATION_EXPIRE_MINUTES,
    POLICY_APPROVAL_EMAIL,
    POLICY_APPROVAL_NAME,
)


def hash_text(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


SUPPORTED_CATEGORIES = (
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
)

CATEGORY_LABELS = {
    "credentials": "Credentials & secrets",
    "financial_records": "Financial records",
    "employee_information": "Employee information",
    "personal_information": "Personal data (PII)",
    "customer_information": "Customer information",
    "internal_documents": "Internal documents",
    "source_code": "Source code & IP",
    "malware": "Malware / exploit content",
    "violence": "Violence & harm",
    "illegal_activity": "Illegal activity",
}


def _format_list(items: list[str], limit: int = 12) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return "None"
    if len(cleaned) <= limit:
        return ", ".join(cleaned)
    shown = ", ".join(cleaned[:limit])
    return f"{shown}, +{len(cleaned) - limit} more"


def build_policy_summary(policy_json: str) -> str:
    try:
        policy = json.loads(policy_json)
    except json.JSONDecodeError:
        return "Policy details unavailable."

    blocked = [
        str(item).strip().lower()
        for item in (policy.get("blocked_categories") or [])
        if str(item).strip()
    ]
    blocked_set = set(blocked)
    allowed = [
        category
        for category in SUPPORTED_CATEGORIES
        if category not in blocked_set
    ]

    allowed_labels = [
        CATEGORY_LABELS.get(item, item) for item in allowed
    ]
    blocked_labels = [
        CATEGORY_LABELS.get(item, item) for item in blocked
    ]

    sensitive_patterns = policy.get("sensitive_pattern_ids") or []
    allowed_secrets = policy.get("allowed_secret_names") or []
    blocked_secrets = policy.get("blocked_secret_names") or []
    allowed_salaries = (
        policy.get("allowed_employee_salary_names") or []
    )
    blocked_salaries = (
        policy.get("blocked_employee_salary_names") or []
    )

    lines = [
        f"- Policy name: {policy.get('policy_name', 'N/A')}",
        f"- Allowed categories: {_format_list(allowed_labels)}",
        f"- Blocked categories: {_format_list(blocked_labels)}",
        f"- Sensitive patterns: {_format_list(sensitive_patterns)}",
        f"- Allowed secrets: {_format_list(allowed_secrets)}",
        f"- Blocked secrets: {_format_list(blocked_secrets)}",
        (
            "- Allowed salaries: "
            f"{_format_list(allowed_salaries)}"
        ),
        (
            "- Blocked salaries: "
            f"{_format_list(blocked_salaries)}"
        ),
    ]
    return "\n".join(lines)


def parse_expires_at(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    expires_at = datetime.fromisoformat(normalized)

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    return expires_at


def request_policy_activation(
    policy_id: int,
    client_id: str,
    requested_by: str,
) -> dict:
    if not POLICY_APPROVAL_EMAIL:
        raise ValueError(
            "POLICY_APPROVAL_EMAIL is missing in .env"
        )

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT *
            FROM ClientPolicies
            WHERE PolicyID = ?
              AND ClientID = ?
            """,
            (policy_id, client_id),
        ).fetchone()

        if row is None:
            raise ValueError("Policy was not found.")

        if row["Status"] not in {
            "VALIDATED",
            "REJECTED",
            "PENDING_ACTIVATION",
        }:
            raise ValueError(
                "Only VALIDATED or REJECTED policies "
                "can request activation."
            )

        connection.execute(
            """
            UPDATE PolicyActivationRequests
            SET
                Status = 'CANCELLED',
                ProcessedAt = ?
            WHERE PolicyID = ?
              AND Status = 'PENDING'
            """,
            (get_current_utc_time(), policy_id),
        )

        confirm_token = secrets.token_urlsafe(32)
        reject_token = secrets.token_urlsafe(32)

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(
                minutes=POLICY_ACTIVATION_EXPIRE_MINUTES
            )
        ).isoformat()

        connection.execute(
            """
            INSERT INTO PolicyActivationRequests (
                PolicyID,
                ClientID,
                RequestedBy,
                ApprovalEmail,
                ConfirmTokenHash,
                RejectTokenHash,
                Status,
                ExpiresAt,
                CreatedAt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy_id,
                client_id,
                requested_by,
                POLICY_APPROVAL_EMAIL,
                hash_text(confirm_token),
                hash_text(reject_token),
                "PENDING",
                expires_at,
                get_current_utc_time(),
            ),
        )

        connection.execute(
            """
            UPDATE ClientPolicies
            SET Status = 'PENDING_ACTIVATION'
            WHERE PolicyID = ?
              AND ClientID = ?
            """,
            (policy_id, client_id),
        )
        connection.commit()

        confirm_url = (
            f"{FRONTEND_URL}/policies/activation"
            f"?action=confirm&token={confirm_token}"
        )
        reject_url = (
            f"{FRONTEND_URL}/policies/activation"
            f"?action=reject&token={reject_token}"
        )

        send_policy_activation_email(
            receiver_email=POLICY_APPROVAL_EMAIL,
            receiver_name=POLICY_APPROVAL_NAME,
            client_id=client_id,
            policy_id=policy_id,
            policy_version=int(row["Version"]),
            requested_by=requested_by,
            confirm_url=confirm_url,
            reject_url=reject_url,
            expires_in_minutes=POLICY_ACTIVATION_EXPIRE_MINUTES,
            policy_summary=build_policy_summary(
                row["PolicyJSON"]
            ),
        )

        return {
            "policy_id": policy_id,
            "client_id": client_id,
            "status": "PENDING_ACTIVATION",
            "approval_email": POLICY_APPROVAL_EMAIL,
            "expires_at": expires_at,
            "message": (
                f"Confirmation email sent to {POLICY_APPROVAL_EMAIL}. "
                "Open that inbox (and Spam), then click Confirm Activation."
            ),
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def confirm_policy_activation(token: str) -> dict:
    token_hash = hash_text(token)
    request = get_policy_activation_by_token(
        token_hash,
        "confirm",
    )

    if request is None:
        raise ValueError(
            "Invalid or already used confirmation link."
        )

    if datetime.now(timezone.utc) > parse_expires_at(
        str(request["ExpiresAt"])
    ):
        update_policy_activation_request(
            int(request["RequestID"]),
            "EXPIRED",
        )
        raise ValueError("Confirmation link expired.")

    policy_id = int(request["PolicyID"])
    client_id = str(request["ClientID"])
    now = datetime.now(timezone.utc).isoformat()

    connection = get_connection()

    try:
        connection.execute(
            """
            UPDATE ClientPolicies
            SET Status = 'INACTIVE'
            WHERE ClientID = ?
              AND Status = 'ACTIVE'
            """,
            (client_id,),
        )

        connection.execute(
            """
            UPDATE ClientPolicies
            SET
                Status = 'ACTIVE',
                ActivatedAt = ?
            WHERE PolicyID = ?
              AND ClientID = ?
            """,
            (now, policy_id, client_id),
        )

        connection.execute(
            """
            UPDATE PolicyActivationRequests
            SET
                Status = 'CONFIRMED',
                ProcessedAt = ?
            WHERE RequestID = ?
            """,
            (get_current_utc_time(), int(request["RequestID"])),
        )

        connection.commit()

        return {
            "policy_id": policy_id,
            "client_id": client_id,
            "status": "ACTIVE",
            "activated_at": now,
            "confirmed_at": get_current_utc_time(),
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def reject_policy_activation(token: str) -> dict:
    token_hash = hash_text(token)
    request = get_policy_activation_by_token(
        token_hash,
        "reject",
    )

    if request is None:
        raise ValueError(
            "Invalid or already used rejection link."
        )

    policy_id = int(request["PolicyID"])
    client_id = str(request["ClientID"])

    connection = get_connection()

    try:
        connection.execute(
            """
            UPDATE ClientPolicies
            SET Status = 'REJECTED'
            WHERE PolicyID = ?
              AND ClientID = ?
            """,
            (policy_id, client_id),
        )

        processed_at = get_current_utc_time()

        connection.execute(
            """
            UPDATE PolicyActivationRequests
            SET
                Status = 'REJECTED',
                ProcessedAt = ?
            WHERE RequestID = ?
            """,
            (processed_at, int(request["RequestID"])),
        )

        connection.commit()

        return {
            "policy_id": policy_id,
            "client_id": client_id,
            "status": "REJECTED",
            "rejected_at": processed_at,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
