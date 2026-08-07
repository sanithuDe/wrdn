import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
    Query,
)
from pydantic import BaseModel

from wrdn.backend.database import get_connection
from wrdn.backend.services.policy_agent import (
    generate_policy,
)
from wrdn.backend.services.policy_validator import (
    validate_policy,
)
from wrdn.backend.services.requirement_parser import (
    extract_requirement_text,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["Client Policy Management"],
)

CLIENT_UPLOAD_DIR = (
    Path(__file__).resolve().parents[1]
    / "secure_uploads"
    / "client_requirements"
)

CLIENT_ID_PATTERN = re.compile(
    r"^[a-zA-Z0-9_-]{3,64}$"
)


class ClientCreateRequest(BaseModel):
    client_id: str
    client_name: str


class PolicyActionRequest(BaseModel):
    client_id: str


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def normalize_client_id(
    client_id: str,
) -> str:
    value = client_id.strip()

    if not CLIENT_ID_PATTERN.fullmatch(value):
        raise HTTPException(
            status_code=400,
            detail=(
                "Client ID must contain 3-64 "
                "letters, numbers, underscores "
                "or hyphens."
            ),
        )

    return value


def require_client(
    connection,
    client_id: str,
) -> None:
    row = connection.execute(
        """
        SELECT ClientID
        FROM Clients
        WHERE ClientID = ?
        """,
        (client_id,),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Client was not found.",
        )


def read_policy_row(
    connection,
    policy_id: int,
):
    row = connection.execute(
        """
        SELECT *
        FROM ClientPolicies
        WHERE PolicyID = ?
        """,
        (policy_id,),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Policy was not found.",
        )

    return row


def require_policy_owner(
    row,
    client_id: str,
) -> None:
    if row["ClientID"] != client_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "Admin cannot access another "
                "customer's policy."
            ),
        )


def serialize_policy_row(row) -> dict:
    result = dict(row)

    result["PolicyJSON"] = json.loads(
        result["PolicyJSON"]
    )

    result["ValidationErrors"] = json.loads(
        result["ValidationErrors"] or "[]"
    )

    return result


def deactivate_other_active_policies(
    connection,
    client_id: str,
    keep_policy_id: int,
) -> None:
    """
    One customer = one ACTIVE policy only.
    Older policies stay in history as INACTIVE.
    """
    connection.execute(
        """
        UPDATE ClientPolicies
        SET Status = 'INACTIVE'
        WHERE ClientID = ?
          AND Status = 'ACTIVE'
          AND PolicyID != ?
        """,
        (client_id, keep_policy_id),
    )


def repair_duplicate_active_for_client(
    connection,
    client_id: str,
) -> None:
    """
    If this customer somehow has more than one
    ACTIVE policy, keep newest PolicyID only.
    """
    row = connection.execute(
        """
        SELECT MAX(PolicyID) AS KeepID
        FROM ClientPolicies
        WHERE ClientID = ?
          AND Status = 'ACTIVE'
        """,
        (client_id,),
    ).fetchone()

    keep_id = row["KeepID"] if row else None

    if keep_id is None:
        return

    connection.execute(
        """
        UPDATE ClientPolicies
        SET Status = 'INACTIVE'
        WHERE ClientID = ?
          AND Status = 'ACTIVE'
          AND PolicyID != ?
        """,
        (client_id, keep_id),
    )


@router.post(
    "/clients",
    status_code=201,
)
def create_client(
    request: ClientCreateRequest,
) -> dict:
    client_id = normalize_client_id(
        request.client_id
    )

    client_name = request.client_name.strip()

    if not client_name:
        raise HTTPException(
            status_code=400,
            detail="Client name is required.",
        )

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO Clients (
                ClientID,
                ClientName,
                CreatedAt
            )
            VALUES (?, ?, ?)
            """,
            (
                client_id,
                client_name,
                utc_now(),
            ),
        )

        connection.commit()

    except Exception as error:
        connection.rollback()

        if "UNIQUE" in str(error).upper():
            raise HTTPException(
                status_code=409,
                detail=(
                    "Client ID already exists."
                ),
            ) from error

        raise

    finally:
        connection.close()

    return {
        "client_id": client_id,
        "client_name": client_name,
        "status": "CREATED",
    }


@router.get("/clients")
def list_clients(
    client_id: str | None = Query(default=None),
) -> list[dict]:
    """
    If client_id is given, return only that customer.
    Admin should pass their own client_id.
    """
    connection = get_connection()

    try:
        if client_id:
            safe_client_id = normalize_client_id(
                client_id
            )

            rows = connection.execute(
                """
                SELECT
                    ClientID,
                    ClientName,
                    CreatedAt
                FROM Clients
                WHERE ClientID = ?
                """,
                (safe_client_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT
                    ClientID,
                    ClientName,
                    CreatedAt
                FROM Clients
                ORDER BY ClientName
                """
            ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


@router.post(
    "/clients/{client_id}/requirements",
    status_code=201,
)
async def upload_requirement(
    client_id: str,
    file: UploadFile = File(...),
) -> dict:
    client_id = normalize_client_id(
        client_id
    )

    filename = Path(
        file.filename or ""
    ).name

    content = await file.read()

    try:
        parsed = extract_requirement_text(
            filename,
            content,
        )

    except (
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    connection = get_connection()
    stored_path: Path | None = None

    try:
        require_client(
            connection,
            client_id,
        )

        client_directory = (
            CLIENT_UPLOAD_DIR / client_id
        )

        client_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        extension = Path(
            filename
        ).suffix.lower()

        stored_path = (
            client_directory
            / f"{uuid4().hex}{extension}"
        )

        stored_path.write_bytes(content)

        cursor = connection.execute(
            """
            INSERT INTO ClientRequirementFiles (
                ClientID,
                OriginalFilename,
                StoredFilename,
                FileType,
                FileHash,
                ExtractedText,
                Status,
                UploadedAt
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                'LOADED', ?
            )
            """,
            (
                client_id,
                filename,
                stored_path.name,
                parsed["file_type"],
                hashlib.sha256(
                    content
                ).hexdigest(),
                parsed["extracted_text"],
                utc_now(),
            ),
        )

        connection.commit()

        requirement_id = int(
            cursor.lastrowid
        )

    except Exception:
        connection.rollback()

        if (
            stored_path
            and stored_path.exists()
        ):
            stored_path.unlink()

        raise

    finally:
        connection.close()

    return {
        "requirement_id": requirement_id,
        "client_id": client_id,
        "filename": filename,
        "file_type": parsed["file_type"],
        "status": "LOADED",
        "text_preview": (
            parsed["extracted_text"][:300]
        ),
    }


@router.post(
    "/requirements/{requirement_id}/analyze",
    status_code=201,
)
def analyze_requirement(
    requirement_id: int,
    client_id: str = Query(...),
) -> dict:
    """
    Generate policy only for this admin's customer.
    """
    client_id = normalize_client_id(client_id)

    connection = get_connection()

    try:
        requirement = connection.execute(
            """
            SELECT *
            FROM ClientRequirementFiles
            WHERE RequirementFileID = ?
            """,
            (requirement_id,),
        ).fetchone()

        if requirement is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Requirement file was "
                    "not found."
                ),
            )

        if requirement["ClientID"] != client_id:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Admin cannot analyze another "
                    "customer's requirement."
                ),
            )

        policy = generate_policy(
            requirement["ClientID"],
            requirement["ExtractedText"],
        )

        # Always bind policy to the admin's real client.
        # Gemini may invent a different client_id from the document text.
        policy["client_id"] = requirement["ClientID"]

        errors = validate_policy(
            policy,
            requirement["ClientID"],
        )

        version_row = connection.execute(
            """
            SELECT
                COALESCE(
                    MAX(Version),
                    0
                ) + 1 AS NextVersion
            FROM ClientPolicies
            WHERE ClientID = ?
            """,
            (requirement["ClientID"],),
        ).fetchone()

        version = int(
            version_row["NextVersion"]
        )

        cursor = connection.execute(
            """
            INSERT INTO ClientPolicies (
                ClientID,
                RequirementFileID,
                PolicyName,
                Version,
                PolicyJSON,
                Status,
                ValidationErrors,
                CreatedAt
            )
            VALUES (
                ?, ?, ?, ?, ?,
                'DRAFT', ?, ?
            )
            """,
            (
                requirement["ClientID"],
                requirement_id,
                policy.get(
                    "policy_name",
                    (
                        f"{requirement['ClientID']} "
                        "policy"
                    ),
                ),
                version,
                json.dumps(
                    policy,
                    ensure_ascii=False,
                ),
                json.dumps(errors),
                utc_now(),
            ),
        )

        connection.execute(
            """
            UPDATE ClientRequirementFiles
            SET Status = 'ANALYZED'
            WHERE RequirementFileID = ?
            """,
            (requirement_id,),
        )

        connection.commit()

        policy_id = int(
            cursor.lastrowid
        )

    except HTTPException:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return {
        "policy_id": policy_id,
        "client_id": policy["client_id"],
        "version": version,
        "status": "DRAFT",
        "validation_errors": errors,
        "policy": policy,
    }


@router.get(
    "/clients/{client_id}/policies"
)
def list_client_policies(
    client_id: str,
) -> list[dict]:
    client_id = normalize_client_id(
        client_id
    )

    connection = get_connection()

    try:
        require_client(
            connection,
            client_id,
        )

        repair_duplicate_active_for_client(
            connection,
            client_id,
        )
        connection.commit()

        rows = connection.execute(
            """
            SELECT
                PolicyID,
                ClientID,
                RequirementFileID,
                PolicyName,
                Version,
                Status,
                ValidationErrors,
                CreatedAt,
                ActivatedAt
            FROM ClientPolicies
            WHERE ClientID = ?
            ORDER BY Version DESC
            """,
            (client_id,),
        ).fetchall()

        result = []

        for row in rows:
            item = dict(row)

            item["ValidationErrors"] = (
                json.loads(
                    item["ValidationErrors"]
                    or "[]"
                )
            )

            result.append(item)

        return result

    finally:
        connection.close()


@router.get("/policy-history")
def list_policy_history(
    client_id: str = Query(
        ...,
        description=(
            "Required. Admin can only view "
            "their own customer policies."
        ),
    ),
) -> list[dict]:
    """
    History for ONE customer only.
    Admin cannot see other customers.
    One ACTIVE policy max for this customer.
    """
    client_id = normalize_client_id(client_id)

    connection = get_connection()

    try:
        require_client(
            connection,
            client_id,
        )

        repair_duplicate_active_for_client(
            connection,
            client_id,
        )
        connection.commit()

        rows = connection.execute(
            """
            SELECT
                PolicyID,
                ClientID,
                RequirementFileID,
                PolicyName,
                Version,
                PolicyJSON,
                Status,
                ValidationErrors,
                CreatedAt,
                ActivatedAt
            FROM ClientPolicies
            WHERE ClientID = ?
            ORDER BY CreatedAt DESC, PolicyID DESC
            """,
            (client_id,),
        ).fetchall()

        history = []

        for row in rows:
            policy = dict(row)

            policy["ValidationErrors"] = json.loads(
                policy["ValidationErrors"] or "[]"
            )

            policy["Policy"] = json.loads(
                policy.pop("PolicyJSON") or "{}"
            )

            history.append(policy)

        return history

    finally:
        connection.close()


@router.post(
    "/policies/{policy_id}/validate"
)
def validate_saved_policy(
    policy_id: int,
    request: PolicyActionRequest,
) -> dict:
    client_id = normalize_client_id(
        request.client_id
    )

    connection = get_connection()

    try:
        row = read_policy_row(
            connection,
            policy_id,
        )

        require_policy_owner(
            row,
            client_id,
        )

        policy = json.loads(
            row["PolicyJSON"]
        )

        # Force the real owner client_id before validation.
        policy["client_id"] = client_id

        errors = validate_policy(
            policy,
            client_id,
        )

        status = (
            "REJECTED"
            if errors
            else "VALIDATED"
        )

        connection.execute(
            """
            UPDATE ClientPolicies
            SET
                Status = ?,
                PolicyJSON = ?,
                ValidationErrors = ?
            WHERE PolicyID = ?
            """,
            (
                status,
                json.dumps(
                    policy,
                    ensure_ascii=False,
                ),
                json.dumps(errors),
                policy_id,
            ),
        )

        connection.commit()

        return {
            "policy_id": policy_id,
            "status": status,
            "validation_errors": errors,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@router.post(
    "/policies/{policy_id}/activate"
)
def activate_policy(
    policy_id: int,
    request: PolicyActionRequest,
) -> dict:
    client_id = normalize_client_id(
        request.client_id
    )

    connection = get_connection()

    try:
        row = read_policy_row(
            connection,
            policy_id,
        )

        require_policy_owner(
            row,
            client_id,
        )

        if row["Status"] != "VALIDATED":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Validate the policy "
                    "before activation."
                ),
            )

    
        #inactive customer part 
        deactivate_other_active_policies(
            connection,
            client_id,
            policy_id,
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
            (
                utc_now(),
                policy_id,
                client_id,
            ),
        )

        connection.commit()

        return {
            "policy_id": policy_id,
            "client_id": client_id,
            "status": "ACTIVE",
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@router.post(
    "/policies/{policy_id}/rollback"
)
def rollback_policy(
    policy_id: int,
    request: PolicyActionRequest,
) -> dict:
    """
    Restore an older policy as the only ACTIVE
    policy for this customer.
    """
    client_id = normalize_client_id(
        request.client_id
    )

    connection = get_connection()

    try:
        row = read_policy_row(
            connection,
            policy_id,
        )

        require_policy_owner(
            row,
            client_id,
        )

        if row["Status"] not in {
            "INACTIVE",
            "ACTIVE",
        }:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Only a previously active "
                    "policy can be restored."
                ),
            )

        deactivate_other_active_policies(
            connection,
            client_id,
            policy_id,
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
            (
                utc_now(),
                policy_id,
                client_id,
            ),
        )

        connection.commit()

        return {
            "policy_id": policy_id,
            "client_id": client_id,
            "status": "ACTIVE",
            "rolled_back": True,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@router.delete(
    "/policies/{policy_id}"
)
def delete_policy(
    policy_id: int,
    request: PolicyActionRequest,
) -> dict:
    """
    Delete one policy from history for this customer.
    ACTIVE policy cannot be deleted.
    """
    client_id = normalize_client_id(
        request.client_id
    )

    connection = get_connection()

    try:
        row = read_policy_row(
            connection,
            policy_id,
        )

        require_policy_owner(
            row,
            client_id,
        )

        if row["Status"] == "ACTIVE":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cannot delete the ACTIVE policy. "
                    "Activate another policy first, "
                    "then delete this one."
                ),
            )

        connection.execute(
            """
            DELETE FROM ClientPolicies
            WHERE PolicyID = ?
              AND ClientID = ?
            """,
            (policy_id, client_id),
        )

        connection.commit()

        return {
            "policy_id": policy_id,
            "client_id": client_id,
            "status": "DELETED",
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()