from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

# Closed set of values the LeakHit.status column can hold. Anything else
# is rejected with a 422 at the API boundary instead of silently being
# stored. Add to this list when introducing a new workflow state.
LeakStatus = Literal["new", "reviewing", "resolved", "escalated", "false_positive"]


# Tenant Schemas
class TenantBase(BaseModel):
    name: str
    description: str | None = None


class TenantCreate(TenantBase):
    pass


class Tenant(TenantBase):
    id: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    role: str = "analyst"
    tenant_id: str | None = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    # Richiesta per cambiare l'email — previene account-takeover con token temporaneamente rubati
    current_password: str | None = None


class User(UserBase):
    id: str
    is_active: bool

    class Config:
        from_attributes = True


# Keyword Schemas
class KeywordBase(BaseModel):
    value: str
    type: str


class KeywordCreate(KeywordBase):
    tenant_id: str


class Keyword(KeywordBase):
    id: str
    created_at: datetime
    last_scanned: datetime | None = None

    class Config:
        from_attributes = True


# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None
    tenant_id: str | None = None
    role: str | None = None


# Yara Schemas (#25)
class YaraRuleBase(BaseModel):
    name: str
    content: str
    is_active: bool = True


class YaraRuleCreate(YaraRuleBase):
    tenant_id: str | None = None


class YaraRule(YaraRuleBase):
    id: str
    tenant_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# Identity Schemas (#11)
class IdentityBase(BaseModel):
    identifier: str
    type: str
    is_protected: bool = False


class IdentityUpdate(BaseModel):
    is_protected: bool


class Identity(IdentityBase):
    id: str
    tenant_id: str
    risk_score: int
    master_identity_id: str | None = None

    class Config:
        from_attributes = True


# Leak Schemas
class LeakHitBase(BaseModel):
    source: str
    severity_score: int
    status: str = "new"
    metadata_json: dict = {}


# Mitre ATT&CK Schemas (CC)
class MitreTechniqueBase(BaseModel):
    id: str
    name: str
    tactic: str
    description: str | None = None


class MitreTechnique(MitreTechniqueBase):
    class Config:
        from_attributes = True


class LeakHit(LeakHitBase):
    id: str
    tenant_id: str
    discovered_at: datetime
    content_snippet: str | None = None
    storage_path: str | None = None
    screenshot_path: str | None = None
    mitre_techniques: list[MitreTechnique] = []

    class Config:
        from_attributes = True


# Identity Insights Schema (Q)
class IdentityInsights(BaseModel):
    identity: Identity
    leaks: list[LeakHit]
    merged_identities: list[Identity] = []  # Profile tree (Y)
    total_leaks: int
    highest_severity: int
    first_seen: datetime
    last_seen: datetime

    class Config:
        from_attributes = True
