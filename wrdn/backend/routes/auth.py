from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from wrdn.backend.services.auth_service import (
    ACTIVE_SESSIONS,
    create_managed_user,
    delete_managed_user,
    ensure_demo_users,
    get_user_from_token,
    list_managed_users,
    login_user,
    logout_user,
    public_signup_is_empty,
    register_user,
)
from wrdn.backend.database import delete_all_users


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    username: str
    password: str
    organisation: str
    full_name: str
    email: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = Field(default="EMPLOYEE")
    client_id: str | None = None


def _bearer_token(
    authorization: str | None,
) -> str | None:
    if authorization and authorization.startswith(
        "Bearer "
    ):
        return authorization.replace(
            "Bearer ",
            "",
            1,
        ).strip()
    return None


def _require_user(
    authorization: str | None,
) -> dict:
    user = get_user_from_token(
        _bearer_token(authorization)
    )
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Not logged in.",
        )
    return user


@router.api_route(
    "/seed-demo",
    methods=["GET", "POST"],
)
def seed_demo_users() -> dict:
    """
    Create demo Admin/Employee users for testing.
    """

    users = ensure_demo_users()

    return {
        "status": "ok",
        "users": users,
        "note": (
            "Use adminA/AdminA@2026! or "
            "employeeA/EmpA@2026!"
        ),
    }


@router.api_route(
    "/clear-users",
    methods=["GET", "POST"],
)
def clear_users() -> dict:
    """
    Delete all auth users (demo reset for local testing).
    """

    deleted = delete_all_users()
    ACTIVE_SESSIONS.clear()

    return {
        "status": "ok",
        "deleted": deleted,
        "message": (
            "All user records removed. "
            "Create new accounts on /signup."
        ),
    }


@router.get("/signup-status")
def signup_status() -> dict:
    empty = public_signup_is_empty()
    return {
        "status": "ok",
        "first_admin_available": empty,
        "public_role": "ADMIN" if empty else "EMPLOYEE",
    }


@router.post("/signup")
def signup(request: SignupRequest) -> dict:
    try:
        user = register_user(
            username=request.username,
            password=request.password,
            organisation=request.organisation,
            full_name=request.full_name,
            email=request.email,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return {
        "status": "ok",
        "message": (
            f"{user['role'].title()} account created. "
            "Go to Sign in and enter the same username and password."
        ),
        "user": user,
    }


@router.post("/login")
def login(request: LoginRequest) -> dict:
    username = request.username.strip()
    password = request.password

    if not username or not password:
        raise HTTPException(
            status_code=400,
            detail="Username and password are required.",
        )

    try:
        result = login_user(
            username,
            password,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=401,
            detail=str(error),
        ) from error

    return {
        "status": "ok",
        "token": result["token"],
        "user": result["user"],
    }


@router.get("/me")
def me(
    authorization: str | None = Header(
        default=None
    ),
) -> dict:
    user = _require_user(authorization)
    return {
        "status": "ok",
        "user": user,
    }


@router.get("/users")
def get_users(
    authorization: str | None = Header(
        default=None
    ),
) -> dict:
    actor = _require_user(authorization)
    try:
        users = list_managed_users(actor)
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error

    return {
        "status": "ok",
        "users": users,
    }


@router.post("/users")
def post_user(
    request: CreateUserRequest,
    authorization: str | None = Header(
        default=None
    ),
) -> dict:
    actor = _require_user(authorization)
    try:
        user = create_managed_user(
            actor=actor,
            username=request.username,
            password=request.password,
            role=request.role,
            client_id=request.client_id,
        )
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return {
        "status": "ok",
        "message": "User created.",
        "user": user,
    }


@router.delete("/users/{username}")
def remove_user(
    username: str,
    authorization: str | None = Header(
        default=None
    ),
) -> dict:
    actor = _require_user(authorization)
    try:
        delete_managed_user(
            actor=actor,
            username=username,
        )
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return {
        "status": "ok",
        "message": f"Deleted user '{username}'.",
    }


@router.post("/logout")
def logout(
    authorization: str | None = Header(
        default=None
    ),
) -> dict:
    token = _bearer_token(authorization)

    if token:
        logout_user(token)

    return {
        "status": "ok",
        "message": "Logged out.",
    }
