"""Authentication endpoints: current user info."""

from fastapi import APIRouter, Depends
from app.auth.models import UserInfo
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=UserInfo)
def me(user: UserInfo = Depends(get_current_user)):
    return user
