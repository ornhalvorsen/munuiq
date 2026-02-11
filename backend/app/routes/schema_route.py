from fastapi import APIRouter
from app.schema import get_schema_dict

router = APIRouter()


@router.get("/api/schema")
def get_schema():
    return get_schema_dict()
