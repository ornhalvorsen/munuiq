from fastapi import APIRouter
from app import logging_db

router = APIRouter()


@router.get("/api/interactions/export")
def export_interactions():
    pairs = logging_db.export_training_pairs()
    return pairs


@router.get("/api/interactions/sql-fixes")
def export_sql_fixes():
    """Return all logged SQL corrections for pattern analysis."""
    fixes = logging_db.export_sql_fixes()
    return fixes
