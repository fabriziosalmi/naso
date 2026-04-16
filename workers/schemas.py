from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# Tenant Schemas
class TenantBase(BaseModel):
    name: str
    description: Optional[str] = None

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
    full_name: Optional[str] = None
    role: str = "analyst"
    tenant_id: Optional[str] = None

class UserCreate(UserBase):
    password: str

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
    last_scanned: Optional[datetime] = None

    class Config:
        from_attributes = True

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    tenant_id: Optional[str] = None
    role: Optional[str] = None

# Yara Schemas (#25)
class YaraRuleBase(BaseModel):
    name: str
    content: str
    is_active: bool = True

class YaraRuleCreate(YaraRuleBase):
    tenant_id: Optional[str] = None

class YaraRule(YaraRuleBase):
    id: str
    tenant_id: Optional[str]
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
    master_identity_id: Optional[str] = None

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
    description: Optional[str] = None

class MitreTechnique(MitreTechniqueBase):
    class Config:
        from_attributes = True

class LeakHit(LeakHitBase):
    id: str
    tenant_id: str
    discovered_at: datetime
    content_snippet: Optional[str] = None
    storage_path: Optional[str] = None
    screenshot_path: Optional[str] = None
    mitre_techniques: List[MitreTechnique] = []

    class Config:
        from_attributes = True

# Identity Insights Schema (Q)
class IdentityInsights(BaseModel):
    identity: Identity
    leaks: List[LeakHit]
    merged_identities: List[Identity] = [] # Profile tree (Y)
    total_leaks: int
    highest_severity: int
    first_seen: datetime
    last_seen: datetime

    class Config:
        from_attributes = True
