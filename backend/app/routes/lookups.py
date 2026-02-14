"""Lookups endpoint — returns tenant-scoped locations and products for mention autocomplete."""

from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user
from app.auth.models import UserInfo
from app.context import entity_resolver

router = APIRouter()


@router.get("/api/lookups")
def get_lookups(user: UserInfo = Depends(get_current_user)):
    """Return all locations and products for the authenticated user's tenant.

    Data is served from in-memory indexes (loaded at startup) — no DB queries.
    Locations are filtered by customer_ids (tenant scoping). Superadmins see all.

    NOTE: We access _location_index / _product_index via the module (not import)
    because init_*_index() replaces these at startup after import time.
    """
    # --- Locations ---
    locations = []
    all_locs = entity_resolver._location_index.get_all_entities()
    for ruid, loc in all_locs.items():
        # Skip closed/inactive locations
        status = loc.get("status", "active")
        if status in ("closed", "inactive"):
            continue

        # Tenant scoping: filter by customer_ids (empty = superadmin, sees all)
        if user.customer_ids:
            loc_cid = loc.get("customer_id")
            if loc_cid and loc_cid not in user.customer_ids:
                continue

        display = loc.get("display_name", loc.get("db_name", ""))
        brand = loc.get("brand", "")
        region = loc.get("region", "")
        desc_parts = [p for p in [brand, region] if p]

        locations.append({
            "id": ruid,
            "label": display,
            "description": " / ".join(desc_parts) if desc_parts else None,
        })

    # --- Products ---
    products = []
    all_prods = entity_resolver._product_index.get_all_entities()
    for entity_id, prod in all_prods.items():
        products.append({
            "id": entity_id,
            "label": prod.get("product_name", entity_id),
            "description": prod.get("description", None),
        })

    return {"locations": locations, "products": products}
