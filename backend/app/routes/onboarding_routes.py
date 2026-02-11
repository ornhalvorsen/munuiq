"""Onboarding wizard endpoints."""

import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth.dependencies import require_admin
from app.auth.models import UserInfo
from app import management_db
from app.services import onboarding_service

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class ConfirmEntitiesRequest(BaseModel):
    installations: list[dict]  # [{installation_id, selected, display_name, entity_type}]


class MappingUpdateRequest(BaseModel):
    updates: list[dict]  # [{id, status, final_value?}]


class IntegrationMapRequest(BaseModel):
    department_id: int
    installation_id: int


# ─── Status ──────────────────────────────────────────────────────────

@router.get("/{customer_id}/status")
def get_status(customer_id: int, user: UserInfo = Depends(require_admin)):
    state = management_db.get_onboarding_state(customer_id)
    if state is None:
        return {"started": False, "current_step": None, "completed_steps": []}
    completed = json.loads(state["completed_steps"]) if isinstance(state.get("completed_steps"), str) else state.get("completed_steps", [])
    return {
        "started": True,
        "current_step": state["current_step"],
        "completed_steps": completed,
        "started_at": str(state.get("started_at", "")),
        "updated_at": str(state.get("updated_at", "")),
    }


@router.post("/{customer_id}/start")
def start_onboarding(customer_id: int, user: UserInfo = Depends(require_admin)):
    existing = management_db.get_onboarding_state(customer_id)
    if existing:
        return {"message": "Onboarding already started", "state": existing}

    tenant_id = user.tenant_id or 0
    state = management_db.create_onboarding_state(customer_id, tenant_id)
    return {"message": "Onboarding started", "state": state}


# ─── Step 1: Entities ────────────────────────────────────────────────

@router.post("/{customer_id}/entities/scan")
def scan_entities(customer_id: int, user: UserInfo = Depends(require_admin)):
    entities = onboarding_service.scan_entities(customer_id)
    return entities


@router.post("/{customer_id}/entities/confirm")
def confirm_entities(
    customer_id: int,
    body: ConfirmEntitiesRequest,
    user: UserInfo = Depends(require_admin),
):
    # Save entity selections as mappings
    mappings = []
    for inst in body.installations:
        mappings.append({
            "customer_id": customer_id,
            "mapping_type": "location",
            "source_key": str(inst.get("installation_id", "")),
            "source_label": inst.get("display_name", ""),
            "proposed_value": json.dumps({
                "entity_type": inst.get("entity_type", "store"),
                "selected": inst.get("selected", True),
            }),
            "confidence": 1.0,
            "status": "approved",
        })

    management_db.create_mappings(mappings)

    # Update onboarding state
    state = management_db.get_onboarding_state(customer_id)
    if state:
        completed = json.loads(state["completed_steps"]) if isinstance(state.get("completed_steps"), str) else state.get("completed_steps", [])
        if "entities" not in completed:
            completed.append("entities")
        management_db.update_onboarding_state(customer_id, "categories", completed)

    return {"message": "Entities confirmed", "count": len(mappings)}


# ─── Step 2: Categories ──────────────────────────────────────────────

@router.post("/{customer_id}/categories/propose")
def propose_categories(customer_id: int, user: UserInfo = Depends(require_admin)):
    mappings = onboarding_service.propose_categories(customer_id)
    return {"mappings": mappings, "count": len(mappings)}


@router.get("/{customer_id}/categories")
def get_categories(customer_id: int, user: UserInfo = Depends(require_admin)):
    mappings = management_db.get_mappings(customer_id, "category")
    return {"mappings": mappings, "count": len(mappings)}


@router.patch("/{customer_id}/categories")
def update_categories(
    customer_id: int,
    body: MappingUpdateRequest,
    user: UserInfo = Depends(require_admin),
):
    for u in body.updates:
        u["approved_by"] = user.id
    management_db.bulk_update_mappings(body.updates)

    # Check if all reviewed
    remaining = management_db.get_mappings(customer_id, "category")
    pending = sum(1 for m in remaining if m["status"] == "proposed")

    if pending == 0:
        state = management_db.get_onboarding_state(customer_id)
        if state:
            completed = json.loads(state["completed_steps"]) if isinstance(state.get("completed_steps"), str) else state.get("completed_steps", [])
            if "categories" not in completed:
                completed.append("categories")
            management_db.update_onboarding_state(customer_id, "products", completed)

    return {"updated": len(body.updates), "pending": pending}


# ─── Step 3: Products ────────────────────────────────────────────────

@router.post("/{customer_id}/products/propose")
def propose_products(customer_id: int, user: UserInfo = Depends(require_admin)):
    mappings = onboarding_service.propose_products(customer_id)
    return {"mappings": mappings, "count": len(mappings)}


@router.get("/{customer_id}/products")
def get_products(customer_id: int, user: UserInfo = Depends(require_admin)):
    mappings = management_db.get_mappings(customer_id, "product")
    return {"mappings": mappings, "count": len(mappings)}


@router.patch("/{customer_id}/products")
def update_products(
    customer_id: int,
    body: MappingUpdateRequest,
    user: UserInfo = Depends(require_admin),
):
    for u in body.updates:
        u["approved_by"] = user.id
    management_db.bulk_update_mappings(body.updates)

    remaining = management_db.get_mappings(customer_id, "product")
    pending = sum(1 for m in remaining if m["status"] == "proposed")

    if pending == 0:
        state = management_db.get_onboarding_state(customer_id)
        if state:
            completed = json.loads(state["completed_steps"]) if isinstance(state.get("completed_steps"), str) else state.get("completed_steps", [])
            if "products" not in completed:
                completed.append("products")
            management_db.update_onboarding_state(customer_id, "integrations", completed)

    return {"updated": len(body.updates), "pending": pending}


# ─── Step 4: Integrations ────────────────────────────────────────────

@router.get("/{customer_id}/integrations")
def get_integrations(customer_id: int, user: UserInfo = Depends(require_admin)):
    return onboarding_service.scan_integrations(customer_id)


@router.post("/{customer_id}/integrations/{department_id}/map")
def map_integration(
    customer_id: int,
    department_id: int,
    body: IntegrationMapRequest,
    user: UserInfo = Depends(require_admin),
):
    mapping = {
        "customer_id": customer_id,
        "mapping_type": "integration",
        "source_key": str(department_id),
        "source_label": f"planday_dept_{department_id}",
        "proposed_value": str(body.installation_id),
        "confidence": 1.0,
        "status": "approved",
    }
    management_db.create_mappings([mapping])

    # Update state
    state = management_db.get_onboarding_state(customer_id)
    if state:
        completed = json.loads(state["completed_steps"]) if isinstance(state.get("completed_steps"), str) else state.get("completed_steps", [])
        if "integrations" not in completed:
            completed.append("integrations")
        management_db.update_onboarding_state(customer_id, "validation", completed)

    return {"ok": True}


# ─── Step 5: Validate & Approve ──────────────────────────────────────

@router.get("/{customer_id}/summary")
def get_summary(customer_id: int, user: UserInfo = Depends(require_admin)):
    return onboarding_service.get_summary(customer_id)


@router.post("/{customer_id}/approve")
def approve(customer_id: int, user: UserInfo = Depends(require_admin)):
    summary = onboarding_service.get_summary(customer_id)
    if not summary["ready"]:
        raise HTTPException(
            status_code=400,
            detail=f"Not ready for approval: {', '.join(summary['warnings'])}",
        )
    return onboarding_service.approve_onboarding(customer_id, user.id)
