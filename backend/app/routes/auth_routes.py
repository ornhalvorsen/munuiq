"""Authentication endpoints: login and current user info."""

from fastapi import APIRouter, Depends, HTTPException
from app.auth.models import LoginRequest, TokenResponse, UserInfo
from app.auth.passwords import verify_password
from app.auth.jwt_handler import create_token
from app.auth.dependencies import get_current_user
from app import management_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = management_db.get_user_by_email(body.email)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user["is_active"]:
        raise HTTPException(status_code=401, detail="Account is disabled")

    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user["id"], user["email"], user["role"])

    # Build user info with tenant data
    tenant = management_db.get_user_tenant(user["id"])
    customer_ids = []
    tenant_id = None
    tenant_name = None
    if tenant:
        import json
        customer_ids = json.loads(tenant["customer_ids"])
        tenant_id = tenant["id"]
        tenant_name = tenant["name"]

    if user["role"] == "superadmin":
        customer_ids = []

    user_info = UserInfo(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        is_active=user["is_active"],
        customer_ids=customer_ids,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
    )

    return TokenResponse(access_token=token, user=user_info)


@router.get("/me", response_model=UserInfo)
def me(user: UserInfo = Depends(get_current_user)):
    return user
