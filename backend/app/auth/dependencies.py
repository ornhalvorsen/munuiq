"""FastAPI dependencies for authentication and authorization."""

import json
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth.jwt_handler import decode_token
from app.auth.models import UserInfo
from app import management_db

security = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UserInfo:
    """Decode Supabase JWT and load user with tenant customer_ids."""
    token = None
    if credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    supabase_id = payload.get("sub")  # Supabase UUID string
    email = payload.get("email")

    if not supabase_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Lookup by supabase_id first
    user = management_db.get_user_by_supabase_id(supabase_id)

    # Auto-link: if no user found by supabase_id, try email match
    if user is None and email:
        user = management_db.get_user_by_email(email)
        if user is not None:
            # Link this Supabase account to the existing internal user
            management_db.link_supabase_id(user["id"], supabase_id)

    if user is None:
        raise HTTPException(
            status_code=403,
            detail="No internal account found. Contact your administrator.",
        )

    if not user["is_active"]:
        raise HTTPException(status_code=401, detail="Account is disabled")

    # Load tenant info
    tenant = management_db.get_user_tenant(user["id"])
    customer_ids = []
    tenant_id = None
    tenant_name = None
    if tenant:
        customer_ids = json.loads(tenant["customer_ids"])
        tenant_id = tenant["id"]
        tenant_name = tenant["name"]

    # Superadmins see all data (empty customer_ids = no filter)
    if user["role"] == "superadmin":
        customer_ids = []

    return UserInfo(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        is_active=user["is_active"],
        customer_ids=customer_ids,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
    )


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UserInfo | None:
    """Like get_current_user but returns None instead of raising."""
    try:
        return get_current_user(request, credentials)
    except HTTPException:
        return None


def require_admin(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """Require admin or superadmin role."""
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_superadmin(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """Require superadmin role."""
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user
