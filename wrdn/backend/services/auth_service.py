import hashlib
import hmac
import secrets
from typing import Any

from wrdn.backend.database import (
    count_all_users,
    count_users_by_role,
    create_user,
    delete_user_by_username,
    ensure_client_exists,
    get_connection,
    get_current_utc_time,
    get_user_by_username,
    list_users,
    update_user_password,
)


# Temporary in-memory sessions for demo.
# Key = token, value = user info
ACTIVE_SESSIONS: dict[str, dict[str, Any]] = {}


def hash_password(password: str) -> str:
    """
    Create a salted password hash.
    """

    salt = secrets.token_hex(16)
    digest = hashlib.sha256(
        f"{salt}:{password}".encode("utf-8")
    ).hexdigest()

    return f"{salt}${digest}"


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """
    Check password against stored hash.
    """

    try:
        salt, stored_digest = password_hash.split(
            "$",
            1,
        )
    except ValueError:
        return False

    digest = hashlib.sha256(
        f"{salt}:{password}".encode("utf-8")
    ).hexdigest()

    return hmac.compare_digest(
        digest,
        stored_digest,
    )


# Common demo typos → real seeded usernames.
DEMO_USERNAME_ALIASES = {
    "admin": "adminA",
    "employee": "employeeA",
    "admina": "adminA",
    "employeea": "employeeA",
}


def resolve_login_username(username: str) -> str:
    cleaned = username.strip()
    alias = DEMO_USERNAME_ALIASES.get(
        cleaned.lower()
    )
    return alias or cleaned


def login_user(
    username: str,
    password: str,
) -> dict[str, Any]:
    """
    Validate user and create a session token.
    """

    resolved_username = resolve_login_username(
        username
    )
    user = get_user_by_username(resolved_username)

    if user is None:
        raise ValueError(
            "Invalid username or password."
        )

    if not verify_password(
        password,
        user["PasswordHash"],
    ):
        raise ValueError(
            "Invalid username or password."
        )

    token = secrets.token_urlsafe(32)

    session_user = {
        "user_id": user["UserID"],
        "username": user["Username"],
        "role": user["Role"],
        "client_id": user["ClientID"],
    }

    ACTIVE_SESSIONS[token] = session_user

    return {
        "token": token,
        "user": session_user,
    }


def logout_user(token: str) -> None:
    ACTIVE_SESSIONS.pop(token, None)


def get_user_from_token(
    token: str | None,
) -> dict[str, Any] | None:
    if not token:
        return None

    return ACTIVE_SESSIONS.get(token)


def ensure_demo_users() -> list[dict[str, str]]:
    """
    Ensure demo clients and users exist.

    Demo passwords are updated if they changed in code,
    so Docker volumes do not keep old weak passwords.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        for client_id, client_name in (
            ("clientA", "Client A"),
            ("clientB", "Client B"),
        ):
            existing = cursor.execute(
                """
                SELECT ClientID
                FROM Clients
                WHERE ClientID = ?
                LIMIT 1
                """,
                (client_id,),
            ).fetchone()

            if existing is None:
                cursor.execute(
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
                        get_current_utc_time(),
                    ),
                )

        connection.commit()

    finally:
        connection.close()

    demo_accounts = [
        {
            "username": "adminA",
            "password": "AdminA@2026!",
            "role": "ADMIN",
            "client_id": "clientA",
        },
        {
            "username": "employeeA",
            "password": "EmpA@2026!",
            "role": "EMPLOYEE",
            "client_id": "clientA",
        },
        {
            "username": "adminB",
            "password": "AdminB@2026!",
            "role": "ADMIN",
            "client_id": "clientB",
        },
        {
            "username": "employeeB",
            "password": "EmpB@2026!",
            "role": "EMPLOYEE",
            "client_id": "clientB",
        },
    ]

    created: list[dict[str, str]] = []

    for account in demo_accounts:
        existing_user = get_user_by_username(
            account["username"]
        )
        password_hash = hash_password(
            account["password"]
        )

        if existing_user is not None:
            if not verify_password(
                account["password"],
                str(existing_user["PasswordHash"]),
            ):
                update_user_password(
                    account["username"],
                    password_hash,
                )

            created.append(
                {
                    "username": account["username"],
                    "role": account["role"],
                    "client_id": account["client_id"],
                    "status": "UPDATED",
                    "password": account["password"],
                }
            )
            continue

        create_user(
            username=account["username"],
            password_hash=password_hash,
            role=account["role"],
            client_id=account["client_id"],
        )

        created.append(
            {
                "username": account["username"],
                "role": account["role"],
                "client_id": account["client_id"],
                "status": "CREATED",
                "password": account["password"],
            }
        )

    return created


def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ValueError(
            "Password must be at least 8 characters."
        )
    if not any(c.isupper() for c in password):
        raise ValueError(
            "Password must include at least one uppercase letter."
        )
    if not any(c.islower() for c in password):
        raise ValueError(
            "Password must include at least one lowercase letter."
        )
    if not any(c.isdigit() for c in password):
        raise ValueError(
            "Password must include at least one number."
        )
    if password.isalnum():
        raise ValueError(
            "Password must include at least one special character."
        )


def _slugify_client_id(value: str) -> str:
    cleaned = "".join(
        ch.lower()
        if ch.isalnum()
        else "-"
        for ch in value.strip()
    )
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-")
    return cleaned or "client"


def resolve_organisation_client(
    organisation: str,
) -> tuple[str, str]:
    """
    Map organisation text to (client_id, client_name).
    """

    raw = organisation.strip()
    if not raw:
        raise ValueError(
            "Organisation is required."
        )

    lowered = raw.lower().replace(" ", "")
    aliases = {
        "clienta": ("clientA", "Client A"),
        "clientb": ("clientB", "Client B"),
        "client a": ("clientA", "Client A"),
        "client b": ("clientB", "Client B"),
        "wrdncorp": ("clientA", "Client A"),
        "wrdn": ("clientA", "Client A"),
    }

    for key, mapped in aliases.items():
        if lowered == key.replace(" ", ""):
            return mapped

    if raw.lower() in {"client a", "client b"}:
        return aliases[raw.lower()]

    client_id = _slugify_client_id(raw)
    return client_id, raw


def public_signup_is_empty() -> bool:
    return count_all_users() == 0


def register_user(
    username: str,
    password: str,
    organisation: str,
    role: str = "EMPLOYEE",
    full_name: str = "",
    email: str = "",
) -> dict[str, Any]:
    """
    Public signup.

    First user in an empty database may become ADMIN.
    After that, public signup is always EMPLOYEE.
    Requested role from the client is ignored except
    for that first-user bootstrap.
    """

    cleaned_username = username.strip()
    if len(cleaned_username) < 3:
        raise ValueError(
            "Username must be at least 3 characters."
        )
    if " " in cleaned_username:
        raise ValueError(
            "Username cannot contain spaces."
        )

    cleaned_name = full_name.strip()
    if len(cleaned_name) < 2:
        raise ValueError(
            "Full name is required."
        )

    cleaned_email = email.strip()
    if not cleaned_email or "@" not in cleaned_email:
        raise ValueError(
            "A valid work email is required."
        )

    validate_password_strength(password)

    if get_user_by_username(cleaned_username):
        raise ValueError(
            "Username is already taken."
        )

    # Security: never trust public role after bootstrap.
    if count_all_users() == 0:
        normalized_role = "ADMIN"
    else:
        requested = (role or "EMPLOYEE").strip().upper()
        if requested == "ADMIN":
            raise ValueError(
                "Admin accounts can only be created by an existing admin."
            )
        normalized_role = "EMPLOYEE"

    client_id, client_name = resolve_organisation_client(
        organisation
    )
    ensure_client_exists(client_id, client_name)

    user_id = create_user(
        username=cleaned_username,
        password_hash=hash_password(password),
        role=normalized_role,
        client_id=client_id,
    )

    return {
        "user_id": user_id,
        "username": cleaned_username,
        "role": normalized_role,
        "client_id": client_id,
        "full_name": cleaned_name,
        "email": cleaned_email,
    }


# Keep old name for any older imports.
def register_employee(
    username: str,
    password: str,
    organisation: str,
    full_name: str = "",
    email: str = "",
) -> dict[str, Any]:
    return register_user(
        username=username,
        password=password,
        organisation=organisation,
        role="EMPLOYEE",
        full_name=full_name,
        email=email,
    )


def create_managed_user(
    *,
    actor: dict[str, Any],
    username: str,
    password: str,
    role: str,
    client_id: str | None = None,
) -> dict[str, Any]:
    """
    Admin creates a user in their organisation.
    """

    if str(actor.get("role", "")).upper() != "ADMIN":
        raise PermissionError(
            "Only admins can create users."
        )

    cleaned_username = username.strip()
    if len(cleaned_username) < 3:
        raise ValueError(
            "Username must be at least 3 characters."
        )
    if " " in cleaned_username:
        raise ValueError(
            "Username cannot contain spaces."
        )

    validate_password_strength(password)

    if get_user_by_username(cleaned_username):
        raise ValueError(
            "Username is already taken."
        )

    target_client = (
        client_id.strip()
        if client_id and client_id.strip()
        else str(actor["client_id"])
    )
    ensure_client_exists(target_client)

    normalized_role = role.strip().upper()
    if normalized_role not in {"ADMIN", "EMPLOYEE"}:
        raise ValueError(
            "Role must be ADMIN or EMPLOYEE."
        )

    user_id = create_user(
        username=cleaned_username,
        password_hash=hash_password(password),
        role=normalized_role,
        client_id=target_client,
    )

    return {
        "user_id": user_id,
        "username": cleaned_username,
        "role": normalized_role,
        "client_id": target_client,
    }


def list_managed_users(
    actor: dict[str, Any],
) -> list[dict[str, Any]]:
    if str(actor.get("role", "")).upper() != "ADMIN":
        raise PermissionError(
            "Only admins can list users."
        )

    rows = list_users(str(actor["client_id"]))
    return [
        {
            "user_id": int(row["UserID"]),
            "username": row["Username"],
            "role": row["Role"],
            "client_id": row["ClientID"],
            "created_at": row["CreatedAt"],
        }
        for row in rows
    ]


def delete_managed_user(
    *,
    actor: dict[str, Any],
    username: str,
) -> None:
    if str(actor.get("role", "")).upper() != "ADMIN":
        raise PermissionError(
            "Only admins can delete users."
        )

    target_name = username.strip()
    if not target_name:
        raise ValueError("Username is required.")

    if target_name == actor.get("username"):
        raise ValueError(
            "You cannot delete your own account."
        )

    target = get_user_by_username(target_name)
    if target is None:
        raise ValueError("User not found.")

    if target["ClientID"] != actor.get("client_id"):
        raise PermissionError(
            "You can only delete users in your organisation."
        )

    if (
        str(target["Role"]).upper() == "ADMIN"
        and count_users_by_role(
            str(target["ClientID"]),
            "ADMIN",
        )
        <= 1
    ):
        raise ValueError(
            "Cannot delete the last admin for this organisation."
        )

    deleted = delete_user_by_username(target_name)
    if not deleted:
        raise ValueError("User not found.")

    # Drop any live sessions for the deleted user.
    stale_tokens = [
        token
        for token, session in ACTIVE_SESSIONS.items()
        if session.get("username") == target_name
    ]
    for token in stale_tokens:
        ACTIVE_SESSIONS.pop(token, None)
