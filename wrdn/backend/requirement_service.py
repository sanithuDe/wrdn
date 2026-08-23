import hashlib
import json
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from wrdn.backend.database import (
    create_requirement_request,
    create_security_alert,
    get_requirement_request_by_token,
    save_requirement_rules,
    update_requirement_request_status,
)

from wrdn.backend.email_service import (
    send_requirement_approval_email,
)

from wrdn.config import (
    APPROVAL_EXPIRE_MINUTES,
    BACKEND_URL,
    MAX_REQUIREMENT_FILE_SIZE_BYTES,
)


# UPLOAD FOLDERS

BASE_DIR = Path(__file__).resolve().parent

SECURE_UPLOADS_DIR = (
    BASE_DIR / "secure_uploads"
)

PENDING_DIR = (
    SECURE_UPLOADS_DIR / "pending"
)

APPROVED_DIR = (
    SECURE_UPLOADS_DIR / "approved"
)

REJECTED_DIR = (
    SECURE_UPLOADS_DIR / "rejected"
)

EXPIRED_DIR = (
    SECURE_UPLOADS_DIR / "expired"
)


# ALLOWED VALUES

ALLOWED_FILE_EXTENSIONS = {
    ".json",
}

ALLOWED_ACTIONS = {
    "ALLOW",
    "BLOCK",
    "REDACT",
}

ALLOWED_ROLES = {
    "HR_MANAGER",
    "EMPLOYEE",
    "ADMIN",
}


# CREATE UPLOAD DIRECTORIES

def initialize_requirement_directories() -> None:
    """
    Create all requirement upload directories.
    """

    for directory in [
        PENDING_DIR,
        APPROVED_DIR,
        REJECTED_DIR,
        EXPIRED_DIR,
    ]:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


# HASH HELPERS

def hash_text(
    value: str,
) -> str:
    """
    Return a SHA-256 hash for a string.
    """

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def calculate_file_hash(
    file_content: bytes,
) -> str:
    """
    Return a SHA-256 hash for uploaded file content.
    """

    return hashlib.sha256(
        file_content
    ).hexdigest()


# REQUEST CODE

def generate_request_code() -> str:
    """
    Generate a readable unique request code.
    """

    date_value = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d")

    random_value = secrets.token_hex(
        3
    ).upper()

    return (
        f"REQ-{date_value}-{random_value}"
    )


# FILE VALIDATION

def validate_requirement_file(
    original_filename: str,
    file_content: bytes,
) -> dict[str, Any]:
    """
    Validate the uploaded JSON requirement file.
    """

    if not original_filename:
        raise ValueError(
            "Requirement file name is missing."
        )

    extension = Path(
        original_filename
    ).suffix.lower()

    if extension not in ALLOWED_FILE_EXTENSIONS:
        raise ValueError(
            "Only JSON requirement files are allowed."
        )

    if not file_content:
        raise ValueError(
            "Requirement file is empty."
        )

    if (
        len(file_content)
        > MAX_REQUIREMENT_FILE_SIZE_BYTES
    ):
        raise ValueError(
            "Requirement file is too large."
        )

    try:
        decoded_content = (
            file_content.decode("utf-8")
        )
    except UnicodeDecodeError as error:
        raise ValueError(
            "Requirement file must use UTF-8 encoding."
        ) from error

    try:
        parsed_data = json.loads(
            decoded_content
        )
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON file: {error}"
        ) from error

    if not isinstance(
        parsed_data,
        dict,
    ):
        raise ValueError(
            "Requirement file must contain a JSON object."
        )

    company = parsed_data.get(
        "company"
    )

    requirements = parsed_data.get(
        "requirements"
    )

    if not isinstance(
        company,
        str,
    ) or not company.strip():
        raise ValueError(
            "The company field is required."
        )

    if not isinstance(
        requirements,
        list,
    ) or not requirements:
        raise ValueError(
            "The requirements field must contain at least one rule."
        )

    validated_requirements: list[
        dict[str, Any]
    ] = []

    for index, requirement in enumerate(
        requirements,
        start=1,
    ):
        if not isinstance(
            requirement,
            dict,
        ):
            raise ValueError(
                f"Requirement {index} must be a JSON object."
            )

        resource = requirement.get(
            "resource"
        )

        allowed_roles = requirement.get(
            "allowed_roles",
            [],
        )

        restricted_roles = requirement.get(
            "restricted_roles",
            [],
        )

        action = str(
            requirement.get(
                "action",
                "",
            )
        ).strip().upper()

        note = str(
            requirement.get(
                "note",
                "",
            )
        ).strip()

        if not isinstance(
            resource,
            str,
        ) or not resource.strip():
            raise ValueError(
                f"Requirement {index} has no valid resource."
            )

        if not isinstance(
            allowed_roles,
            list,
        ):
            raise ValueError(
                f"Requirement {index} allowed_roles must be a list."
            )

        if not isinstance(
            restricted_roles,
            list,
        ):
            raise ValueError(
                f"Requirement {index} restricted_roles must be a list."
            )

        normalized_allowed_roles = [
            str(role).strip().upper()
            for role in allowed_roles
            if str(role).strip()
        ]

        normalized_restricted_roles = [
            str(role).strip().upper()
            for role in restricted_roles
            if str(role).strip()
        ]

        invalid_allowed_roles = [
            role
            for role in normalized_allowed_roles
            if role not in ALLOWED_ROLES
        ]

        invalid_restricted_roles = [
            role
            for role in normalized_restricted_roles
            if role not in ALLOWED_ROLES
        ]

        if invalid_allowed_roles:
            raise ValueError(
                f"Requirement {index} contains invalid allowed roles: "
                f"{', '.join(invalid_allowed_roles)}"
            )

        if invalid_restricted_roles:
            raise ValueError(
                f"Requirement {index} contains invalid restricted roles: "
                f"{', '.join(invalid_restricted_roles)}"
            )

        if action not in ALLOWED_ACTIONS:
            raise ValueError(
                f"Requirement {index} has invalid action: {action}"
            )

        overlap = set(
            normalized_allowed_roles
        ).intersection(
            normalized_restricted_roles
        )

        if overlap:
            raise ValueError(
                f"Requirement {index} has the same role "
                "inside allowed_roles and restricted_roles."
            )

        validated_requirements.append(
            {
                "resource": (
                    resource.strip().lower()
                ),
                "allowed_roles": (
                    normalized_allowed_roles
                ),
                "restricted_roles": (
                    normalized_restricted_roles
                ),
                "action": action,
                "note": note,
            }
        )

    return {
        "company": company.strip(),
        "requirements": (
            validated_requirements
        ),
    }


# CREATE REQUIREMENT REQUEST

def create_pending_requirement(
    file_content: bytes,
    original_filename: str,
    uploaded_by: str,
    approval_email: str,
    receiver_name: str,
) -> dict[str, Any]:
    """
    Validate, store and email a pending requirement request.
    """

    initialize_requirement_directories()

    validated_data = (
        validate_requirement_file(
            original_filename=original_filename,
            file_content=file_content,
        )
    )

    request_code = (
        generate_request_code()
    )

    approve_token = (
        secrets.token_urlsafe(32)
    )

    reject_token = (
        secrets.token_urlsafe(32)
    )

    approve_token_hash = hash_text(
        approve_token
    )

    reject_token_hash = hash_text(
        reject_token
    )

    stored_filename = (
        f"{uuid4().hex}.json"
    )

    pending_path = (
        PENDING_DIR
        / stored_filename
    )

    pending_path.write_bytes(
        file_content
    )

    file_hash = calculate_file_hash(
        file_content
    )

    expires_at_datetime = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=(
                APPROVAL_EXPIRE_MINUTES
            )
        )
    )

    expires_at = (
        expires_at_datetime.isoformat()
    )

    try:
        request_id = (
            create_requirement_request(
                request_code=request_code,
                uploaded_by=uploaded_by,
                approval_email=approval_email,
                original_filename=(
                    original_filename
                ),
                stored_filename=(
                    stored_filename
                ),
                file_path=str(
                    pending_path
                ),
                file_hash=file_hash,
                approve_token_hash=(
                    approve_token_hash
                ),
                reject_token_hash=(
                    reject_token_hash
                ),
                expires_at=expires_at,
            )
        )

        approve_url = (
            f"{BACKEND_URL}"
            "/api/requirements/approve"
            f"?token={approve_token}"
        )

        reject_url = (
            f"{BACKEND_URL}"
            "/api/requirements/reject"
            f"?token={reject_token}"
        )

        send_requirement_approval_email(
            receiver_email=(
                approval_email
            ),
            receiver_name=(
                receiver_name
            ),
            request_code=(
                request_code
            ),
            original_filename=(
                original_filename
            ),
            approve_url=approve_url,
            reject_url=reject_url,
            expires_in_minutes=(
                APPROVAL_EXPIRE_MINUTES
            ),
        )

        return {
            "request_id": request_id,
            "request_code": (
                request_code
            ),
            "status": "PENDING",
            "company": (
                validated_data["company"]
            ),
            "approval_email": (
                approval_email
            ),
            "expires_at": (
                expires_at
            ),
            "message": (
                "Requirement file uploaded. "
                "Approval email was sent."
            ),
        }

    except Exception:
        if pending_path.exists():
            pending_path.unlink()

        raise


# EXPIRY CHECK

def is_request_expired(
    request: dict[str, Any],
) -> bool:
    """
    Check whether a request has passed its expiration time.
    """

    expires_at_text = str(
        request.get(
            "ExpiresAt",
            "",
        )
    )

    if not expires_at_text:
        return True

    expires_at = datetime.fromisoformat(
        expires_at_text
    )

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    return (
        datetime.now(timezone.utc)
        > expires_at
    )


# MOVE FILE

def move_requirement_file(
    current_path: str,
    destination_directory: Path,
) -> Path:
    """
    Move a requirement file into another secure folder.
    """

    initialize_requirement_directories()

    source_path = Path(
        current_path
    )

    if not source_path.exists():
        raise FileNotFoundError(
            "Requirement file was not found."
        )

    destination_path = (
        destination_directory
        / source_path.name
    )

    shutil.move(
        str(source_path),
        str(destination_path),
    )

    return destination_path


# APPROVE REQUIREMENT

def approve_requirement(
    token: str,
) -> dict[str, Any]:
    """
    Approve and activate a pending requirement request.
    """

    token_hash = hash_text(
        token
    )

    request = (
        get_requirement_request_by_token(
            token_hash=token_hash,
            token_type="approve",
        )
    )

    if request is None:
        raise ValueError(
            "Invalid approval link."
        )

    request_id = int(
        request["RequestID"]
    )

    current_status = str(
        request["Status"]
    ).upper()

    if current_status != "PENDING":
        raise ValueError(
            "This requirement request was already processed."
        )

    if is_request_expired(
        request
    ):
        expired_path = (
            move_requirement_file(
                current_path=(
                    request["FilePath"]
                ),
                destination_directory=(
                    EXPIRED_DIR
                ),
            )
        )

        update_requirement_request_status(
            request_id=request_id,
            status="EXPIRED",
            file_path=str(
                expired_path
            ),
            failure_reason=(
                "Approval link expired."
            ),
        )

        create_security_alert(
            request_id=request_id,
            alert_type=(
                "REQUIREMENT_EXPIRED"
            ),
            severity="HIGH",
            message=(
                f"Requirement "
                f"{request['RequestCode']} "
                "expired without approval."
            ),
        )

        raise ValueError(
            "Approval link has expired."
        )

    approved_path = (
        move_requirement_file(
            current_path=(
                request["FilePath"]
            ),
            destination_directory=(
                APPROVED_DIR
            ),
        )
    )

    update_requirement_request_status(
        request_id=request_id,
        status="APPROVED",
        file_path=str(
            approved_path
        ),
    )

    try:
        file_content = (
            approved_path.read_bytes()
        )

        validated_data = (
            validate_requirement_file(
                original_filename=(
                    request[
                        "OriginalFileName"
                    ]
                ),
                file_content=file_content,
            )
        )

        update_requirement_request_status(
            request_id=request_id,
            status="PROCESSING",
            file_path=str(
                approved_path
            ),
        )

        inserted_rules = (
            save_requirement_rules(
                request_id=request_id,
                requirements=(
                    validated_data[
                        "requirements"
                    ]
                ),
            )
        )

        update_requirement_request_status(
            request_id=request_id,
            status="ACTIVE",
            file_path=str(
                approved_path
            ),
        )

        return {
            "request_id": request_id,
            "request_code": (
                request["RequestCode"]
            ),
            "status": "ACTIVE",
            "rules_activated": (
                inserted_rules
            ),
            "message": (
                "Requirement approved and activated successfully."
            ),
        }

    except Exception as error:
        update_requirement_request_status(
            request_id=request_id,
            status="FAILED",
            file_path=str(
                approved_path
            ),
            failure_reason=str(
                error
            ),
        )

        create_security_alert(
            request_id=request_id,
            alert_type=(
                "PROCESSING_FAILED"
            ),
            severity="CRITICAL",
            message=(
                f"Requirement "
                f"{request['RequestCode']} "
                f"failed during processing: "
                f"{error}"
            ),
        )

        raise


# REJECT REQUIREMENT

def reject_requirement(
    token: str,
) -> dict[str, Any]:
    """
    Reject a pending requirement request.
    """

    token_hash = hash_text(
        token
    )

    request = (
        get_requirement_request_by_token(
            token_hash=token_hash,
            token_type="reject",
        )
    )

    if request is None:
        raise ValueError(
            "Invalid rejection link."
        )

    request_id = int(
        request["RequestID"]
    )

    current_status = str(
        request["Status"]
    ).upper()

    if current_status != "PENDING":
        raise ValueError(
            "This requirement request was already processed."
        )

    if is_request_expired(
        request
    ):
        expired_path = (
            move_requirement_file(
                current_path=(
                    request["FilePath"]
                ),
                destination_directory=(
                    EXPIRED_DIR
                ),
            )
        )

        update_requirement_request_status(
            request_id=request_id,
            status="EXPIRED",
            file_path=str(
                expired_path
            ),
            failure_reason=(
                "Rejection link expired."
            ),
        )

        create_security_alert(
            request_id=request_id,
            alert_type=(
                "REQUIREMENT_EXPIRED"
            ),
            severity="HIGH",
            message=(
                f"Requirement "
                f"{request['RequestCode']} "
                "expired without a decision."
            ),
        )

        raise ValueError(
            "Rejection link has expired."
        )

    rejected_path = (
        move_requirement_file(
            current_path=(
                request["FilePath"]
            ),
            destination_directory=(
                REJECTED_DIR
            ),
        )
    )

    update_requirement_request_status(
        request_id=request_id,
        status="REJECTED",
        file_path=str(
            rejected_path
        ),
    )

    return {
        "request_id": request_id,
        "request_code": (
            request["RequestCode"]
        ),
        "status": "REJECTED",
        "message": (
            "Requirement request was rejected. "
            "No rules were changed."
        ),
    }


initialize_requirement_directories()
