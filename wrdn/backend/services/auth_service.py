import hashlib
import hmac
import secrets
from typing import Any

from wrdn.backend.database import (
    create_user,
    get_connection,
    get_current_utc_time,
    get_user_by_username,
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


def login_user(
    username: str,
    password: str,
) -> dict[str, Any]:
    """
    Validate user and create a session token.
    """

    user = get_user_by_username(username)

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
    """
    Remove session token.
    """

    ACTIVE_SESSIONS.pop(token, None)


def get_user_from_token(
    token: str | None,
) -> dict[str, Any] | None:
    """
    Return logged-in user from token.
    """

    if not token:
        return None

    return ACTIVE_SESSIONS.get(token)


def ensure_demo_users() -> list[dict[str, str]]:
    """
    Create demo client + admin/employee users
    if they do not already exist.
    """

    connection = get_connection()

    try:
        # Ensure demo clients exist.
        for client_id, client_name in [
            ("clientA", "Client A Company"),
            ("clientB", "Client B Company"),
        ]:
            existing = connection.execute(
                """
                SELECT ClientID
                FROM Clients
                WHERE ClientID = ?
                """,
                (client_id,),
            ).fetchone()

            if existing is None:
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
                        get_current_utc_time(),
                    ),
                )

        connection.commit()

    finally:
        connection.close()

    demo_accounts = [
        {
            "username": "adminA",
            "password": "admin123",
            "role": "ADMIN",
            "client_id": "clientA",
        },
        {
            "username": "employeeA",
            "password": "employee123",
            "role": "EMPLOYEE",
            "client_id": "clientA",
        },
        {
            "username": "adminB",
            "password": "admin123",
            "role": "ADMIN",
            "client_id": "clientB",
        },
        {
            "username": "employeeB",
            "password": "employee123",
            "role": "EMPLOYEE",
            "client_id": "clientB",
        },
    ]

    created: list[dict[str, str]] = []

    for account in demo_accounts:
        existing_user = get_user_by_username(
            account["username"]
        )

        if existing_user is not None:
            created.append(
                {
                    "username": account["username"],
                    "role": account["role"],
                    "client_id": account["client_id"],
                    "status": "EXISTS",
                }
            )
            continue

        create_user(
            username=account["username"],
            password_hash=hash_password(
                account["password"]
            ),
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