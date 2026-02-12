"""Admin endpoints: user and tenant management."""

from fastapi import APIRouter, Depends, HTTPException
from app.auth.models import (
    UserInfo, CreateUserRequest, UpdateUserRequest,
    CreateTenantRequest, UpdateTenantRequest, AssignTenantRequest,
)
from app.auth.dependencies import require_admin, require_superadmin
from app import management_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ─── User Management ────────────────────────────────────────────────

@router.get("/users")
def list_users(user: UserInfo = Depends(require_admin)):
    users = management_db.list_users()
    # Enrich with tenant info
    for u in users:
        tenant = management_db.get_user_tenant(u["id"])
        u["tenant_id"] = tenant["id"] if tenant else None
        u["tenant_name"] = tenant["name"] if tenant else None
    return users


@router.post("/users")
def create_user(body: CreateUserRequest, user: UserInfo = Depends(require_admin)):
    if body.role == "superadmin" and user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmins can create superadmins")

    existing = management_db.get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use")

    created = management_db.create_user(
        email=body.email,
        name=body.name,
        role=body.role,
    )
    if created is None:
        raise HTTPException(status_code=500, detail="Failed to create user")

    return {"id": created["id"], "email": created["email"], "name": created["name"], "role": created["role"]}


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UpdateUserRequest, user: UserInfo = Depends(require_admin)):
    target = management_db.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if target["role"] == "superadmin" and user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmins can modify superadmins")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return {"ok": True}

    management_db.update_user(user_id, **updates)
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, user: UserInfo = Depends(require_superadmin)):
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    target = management_db.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    management_db.delete_user(user_id)
    return {"ok": True}


# ─── Tenant Management ──────────────────────────────────────────────

@router.get("/tenants")
def list_tenants(user: UserInfo = Depends(require_admin)):
    tenants = management_db.list_tenants()
    for t in tenants:
        import json
        t["customer_ids"] = json.loads(t["customer_ids"]) if isinstance(t["customer_ids"], str) else t["customer_ids"]
        t["settings"] = json.loads(t["settings"]) if isinstance(t["settings"], str) else t["settings"]
        t["users"] = management_db.get_tenant_users(t["id"])
    return tenants


@router.post("/tenants")
def create_tenant(body: CreateTenantRequest, user: UserInfo = Depends(require_admin)):
    tenant = management_db.create_tenant(
        name=body.name,
        customer_ids=body.customer_ids,
        tenant_settings=body.settings,
    )
    if tenant is None:
        raise HTTPException(status_code=500, detail="Failed to create tenant")
    import json
    tenant["customer_ids"] = json.loads(tenant["customer_ids"]) if isinstance(tenant["customer_ids"], str) else tenant["customer_ids"]
    return tenant


@router.patch("/tenants/{tenant_id}")
def update_tenant(tenant_id: int, body: UpdateTenantRequest, user: UserInfo = Depends(require_admin)):
    target = management_db.get_tenant_by_id(tenant_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return {"ok": True}

    management_db.update_tenant(tenant_id, **updates)
    return {"ok": True}


@router.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: int, user: UserInfo = Depends(require_superadmin)):
    target = management_db.get_tenant_by_id(tenant_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    management_db.delete_tenant(tenant_id)
    return {"ok": True}


# ─── Tenant-User Assignment ─────────────────────────────────────────

@router.post("/assign-tenant")
def assign_tenant(body: AssignTenantRequest, user: UserInfo = Depends(require_admin)):
    target_user = management_db.get_user_by_id(body.user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    tenant = management_db.get_tenant_by_id(body.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    management_db.assign_user_to_tenant(body.user_id, body.tenant_id)
    return {"ok": True}
