"""Pydantic models for authentication."""

from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserInfo"


class UserInfo(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    customer_ids: list[int] = []
    tenant_id: Optional[int] = None
    tenant_name: Optional[str] = None


class CreateUserRequest(BaseModel):
    email: str
    password: str
    name: str
    role: str = "viewer"


class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class CreateTenantRequest(BaseModel):
    name: str
    customer_ids: list[int]
    settings: dict = {}


class UpdateTenantRequest(BaseModel):
    name: Optional[str] = None
    customer_ids: Optional[list[int]] = None
    settings: Optional[dict] = None
    is_active: Optional[bool] = None


class AssignTenantRequest(BaseModel):
    user_id: int
    tenant_id: int
