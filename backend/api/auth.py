from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from backend.auth import create_access_token, hash_password, normalize_email, public_user, verify_access_token, verify_password
from backend.db.clickhouse import get_client
from backend.schemas import AuthLoginRequest, AuthResponse, AuthSignupRequest, AuthUser

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth header.")
    return token


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: AuthSignupRequest) -> AuthResponse:
    store = get_client()
    email = normalize_email(request.email)
    try:
        user = store.create_user(
            email=email,
            password_hash=hash_password(request.password),
            full_name=request.full_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.") from exc

    return AuthResponse(access_token=create_access_token(str(user["id"])), user=public_user(user))


@router.post("/login", response_model=AuthResponse)
async def login(request: AuthLoginRequest) -> AuthResponse:
    store = get_client()
    email = normalize_email(request.email)
    user = store.get_user_by_email(email)
    if user is None or not verify_password(request.password, str(user.get("password_hash") or "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    updated_user = store.update_user_login(str(user["id"])) or user
    return AuthResponse(access_token=create_access_token(str(user["id"])), user=public_user(updated_user))


@router.get("/me", response_model=AuthUser)
async def me(authorization: str | None = Header(default=None)) -> AuthUser:
    store = get_client()
    user_id = verify_access_token(_bearer_token(authorization))
    user = store.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return public_user(user)
