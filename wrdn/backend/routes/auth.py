from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from wrdn.backend.services.auth_service import (
    ensure_demo_users,
    get_user_from_token,
    login_user,
    logout_user,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


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
            "Use adminA/admin123 or "
            "employeeA/employee123"
        ),
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
    token = None

    if authorization and authorization.startswith(
        "Bearer "
    ):
        token = authorization.replace(
            "Bearer ",
            "",
            1,
        ).strip()

    user = get_user_from_token(token)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Not logged in.",
        )

    return {
        "status": "ok",
        "user": user,
    }


@router.post("/logout")
def logout(
    authorization: str | None = Header(
        default=None
    ),
) -> dict:
    token = None

    if authorization and authorization.startswith(
        "Bearer "
    ):
        token = authorization.replace(
            "Bearer ",
            "",
            1,
        ).strip()

    if token:
        logout_user(token)

    return {
        "status": "ok",
        "message": "Logged out.",
    }