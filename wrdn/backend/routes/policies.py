import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    File,
    Header,
    HTTPException,
    UploadFile,
    Query,
)
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from wrdn.backend.database import get_connection
from wrdn.backend.services.auth_service import (
    get_user_from_token,
)
from wrdn.backend.services.policy_activation_service import (
    confirm_policy_activation,
    reject_policy_activation,
    request_policy_activation,
)
from wrdn.backend.services.policy_agent import (
    generate_policy,
)
from wrdn.backend.services.policy_validator import (
    validate_policy,
)
from wrdn.backend.services.requirement_parser import (
    extract_requirement_text,
)
from wrdn.config import FRONTEND_URL

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
    "/policies/{policy_id}/request-activation"
)
def request_activation(
    policy_id: int,
    request: PolicyActionRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    """
    Send email confirmation before the policy goes live.
    """
    client_id = normalize_client_id(
        request.client_id
    )

    requested_by = "admin"
    token = None

    if authorization and authorization.startswith(
        "Bearer "
    ):
        token = authorization.removeprefix(
            "Bearer "
        ).strip()

    user = get_user_from_token(token)

    if user is not None:
        requested_by = str(
            user.get("username", "admin")
        )

    connection = get_connection()

    try:
        row = read_policy_row(connection, policy_id)
        require_policy_owner(row, client_id)
    finally:
        connection.close()

    try:
        return request_policy_activation(
            policy_id=policy_id,
            client_id=client_id,
            requested_by=requested_by,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error


def format_display_datetime(value: str | None) -> str:
    """
    Format UTC ISO timestamps in Sri Lanka time (UTC+5:30).
    """
    if not value:
        return "—"

    try:
        normalized = value.replace("Z", "+00:00")
        moment = datetime.fromisoformat(normalized)

        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)

        sri_lanka = timezone(
            timedelta(hours=5, minutes=30)
        )
        local_time = moment.astimezone(sri_lanka)
        return local_time.strftime(
            "%d %b %Y, %I:%M:%S %p"
        )
    except ValueError:
        return value


def render_activation_result_page(
    *,
    title: str,
    subtitle: str,
    tone: str,
    rows: list[tuple[str, str]] | None = None,
) -> str:
    """
    Shared branded HTML page for email confirmation results.
    tone: success | warning | error
    """

    tones = {
        "success": {
            "accent": "#20e487",
            "badge_bg": "rgba(32, 228, 135, 0.12)",
            "badge_border": "rgba(32, 228, 135, 0.35)",
            "icon": "✓",
            "label": "Confirmed",
        },
        "warning": {
            "accent": "#fbbf24",
            "badge_bg": "rgba(251, 191, 36, 0.12)",
            "badge_border": "rgba(251, 191, 36, 0.35)",
            "icon": "!",
            "label": "Rejected",
        },
        "error": {
            "accent": "#ff6f86",
            "badge_bg": "rgba(255, 111, 134, 0.12)",
            "badge_border": "rgba(255, 111, 134, 0.35)",
            "icon": "×",
            "label": "Failed",
        },
    }

    style = tones.get(tone, tones["error"])
    policies_url = f"{FRONTEND_URL}/policies"

    detail_rows = ""
    if rows:
        items = "".join(
            f"""
            <div class="row">
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
            """
            for label, value in rows
        )
        detail_rows = f'<div class="details">{items}</div>'

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title} · WRDN</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      font-family: Arial, Helvetica, sans-serif;
      color: #f5f7fb;
      background:
        radial-gradient(circle at top left, rgba(32, 228, 135, 0.12), transparent 36%),
        radial-gradient(circle at bottom right, rgba(29, 161, 242, 0.08), transparent 40%),
        #05070c;
    }}
    .card {{
      width: min(480px, 100%);
      padding: 32px 28px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 22px;
      background: rgba(12, 15, 22, 0.92);
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
      text-align: center;
    }}
    .brand {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 22px;
      color: #9aa4b2;
      font-size: 13px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .logo {{
      width: 36px;
      height: 36px;
      display: grid;
      place-items: center;
      border-radius: 11px;
      color: #05070c;
      background: #20e487;
      font-weight: 900;
      box-shadow: 0 0 22px rgba(32, 228, 135, 0.28);
    }}
    .icon {{
      width: 64px;
      height: 64px;
      margin: 0 auto 18px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      color: {style["accent"]};
      background: {style["badge_bg"]};
      border: 1px solid {style["badge_border"]};
      font-size: 28px;
      font-weight: 900;
    }}
    .badge {{
      display: inline-block;
      margin-bottom: 12px;
      padding: 5px 10px;
      border-radius: 999px;
      color: {style["accent"]};
      background: {style["badge_bg"]};
      border: 1px solid {style["badge_border"]};
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0 0 10px;
      color: #ffffff;
      font-size: 24px;
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.25;
    }}
    .subtitle {{
      margin: 0 0 22px;
      color: #8d96a5;
      font-size: 14px;
      line-height: 1.55;
    }}
    .details {{
      display: grid;
      gap: 10px;
      margin: 0 0 24px;
      padding: 14px;
      border: 1px solid rgba(255, 255, 255, 0.07);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.03);
      text-align: left;
    }}
    .row {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      font-size: 13px;
    }}
    .row span {{
      color: #7d8590;
    }}
    .row strong {{
      color: #e8edf5;
      font-weight: 700;
      text-align: right;
      word-break: break-word;
    }}
    .cta {{
      display: inline-block;
      width: 100%;
      padding: 13px 18px;
      border: none;
      border-radius: 12px;
      color: #05070c;
      background: #20e487;
      text-decoration: none;
      font-size: 14px;
      font-weight: 800;
      cursor: pointer;
      transition: 0.15s ease;
    }}
    .cta:hover {{
      filter: brightness(1.05);
      transform: translateY(-1px);
    }}
    .footer {{
      margin: 18px 0 0;
      color: #565e69;
      font-size: 11px;
    }}
  </style>
</head>
<body>
  <main class="card">
    <div class="brand">
      <div class="logo">W</div>
      <span>WRDN Security</span>
    </div>
    <div class="icon">{style["icon"]}</div>
    <div class="badge">{style["label"]}</div>
    <h1>{title}</h1>
    <p class="subtitle">{subtitle}</p>
    {detail_rows}
    <button
      class="cta"
      type="button"
      id="return-button"
    >
      Return to Policy Upload
    </button>
    <p class="footer">
      Enterprise Prompt Shield · Times shown in Sri Lanka (UTC+5:30)
    </p>
  </main>
  <script>
    (function () {{
      var policiesUrl = {policies_url!r};

      document
        .getElementById("return-button")
        .addEventListener("click", function () {{
          // Prefer closing this tab if it was opened from the email,
          // and send the original Policy Upload tab back to the app.
          try {{
            if (window.opener && !window.opener.closed) {{
              window.opener.location.href = policiesUrl;
              window.opener.focus();
              window.close();
              return;
            }}
          }} catch (error) {{}}

          window.close();

          // If the browser blocks close, stay in THIS tab only.
          setTimeout(function () {{
            window.location.replace(policiesUrl);
          }}, 200);
        }});
    }})();
  </script>
</body>
</html>
""".strip()


@router.get("/policies/confirm-activation")
def confirm_activation_page(
    token: str = Query(...),
    response_format: str = Query(
        default="html",
        alias="format",
    ),
):
    try:
        result = confirm_policy_activation(token)

        if response_format == "json":
            return {
                **result,
                "confirmed_at_display": format_display_datetime(
                    result.get("confirmed_at")
                    or result.get("activated_at")
                ),
                "activated_at_display": format_display_datetime(
                    result.get("activated_at")
                ),
            }

        html = render_activation_result_page(
            title="Policy activated successfully",
            subtitle=(
                "This policy is now live and protecting "
                "AI output for the selected client."
            ),
            tone="success",
            rows=[
                ("Client", str(result["client_id"])),
                ("Policy ID", str(result["policy_id"])),
                ("Status", "ACTIVE"),
                (
                    "Confirmed at (SL)",
                    format_display_datetime(
                        result.get("confirmed_at")
                        or result.get("activated_at")
                    ),
                ),
                (
                    "Activated at (SL)",
                    format_display_datetime(
                        result.get("activated_at")
                    ),
                ),
            ],
        )
        return HTMLResponse(html)
    except ValueError as error:
        if response_format == "json":
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error

        html = render_activation_result_page(
            title="Activation failed",
            subtitle=str(error),
            tone="error",
            rows=[
                (
                    "Checked at (SL)",
                    format_display_datetime(
                        datetime.now(timezone.utc).isoformat()
                    ),
                ),
            ],
        )
        return HTMLResponse(html, status_code=400)


@router.get("/policies/reject-activation")
def reject_activation_page(
    token: str = Query(...),
    response_format: str = Query(
        default="html",
        alias="format",
    ),
):
    try:
        result = reject_policy_activation(token)

        if response_format == "json":
            return {
                **result,
                "rejected_at_display": format_display_datetime(
                    result.get("rejected_at")
                ),
            }

        html = render_activation_result_page(
            title="Activation rejected",
            subtitle=(
                "This policy was not activated. "
                "It remains validated and is not live."
            ),
            tone="warning",
            rows=[
                ("Client", str(result["client_id"])),
                ("Policy ID", str(result["policy_id"])),
                ("Status", "VALIDATED (not live)"),
                (
                    "Rejected at (SL)",
                    format_display_datetime(
                        result.get("rejected_at")
                    ),
                ),
            ],
        )
        return HTMLResponse(html)
    except ValueError as error:
        if response_format == "json":
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error

        html = render_activation_result_page(
            title="Rejection failed",
            subtitle=str(error),
            tone="error",
            rows=[
                (
                    "Checked at (SL)",
                    format_display_datetime(
                        datetime.now(timezone.utc).isoformat()
                    ),
                ),
            ],
        )
        return HTMLResponse(html, status_code=400)


@router.post(
    "/policies/{policy_id}/activate"
)
def activate_policy(
    policy_id: int,
    request: PolicyActionRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    """
    Kept for compatibility. Now starts email confirmation
    instead of activating immediately.
    """
    return request_activation(
        policy_id=policy_id,
        request=request,
        authorization=authorization,
    )


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