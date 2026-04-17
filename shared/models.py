import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    users = relationship("User", back_populates="tenant")
    leak_hits = relationship("LeakHit", back_populates="tenant")
    keywords = relationship("Keyword", back_populates="tenant")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, default="analyst")  # admin, analyst
    tenant_id = Column(String, ForeignKey("tenants.id"))
    is_active = Column(Boolean, default=True)

    tenant = relationship("Tenant", back_populates="users")


class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    value = Column(String, nullable=False)
    type = Column(String, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_scanned = Column(DateTime(timezone=True))

    tenant = relationship("Tenant", back_populates="keywords")


# Tabella di associazione per l'Identity Graph
identity_leaks = Table(
    "identity_leaks",
    Base.metadata,
    Column("identity_id", String, ForeignKey("identities.id"), primary_key=True),
    Column("leak_id", String, ForeignKey("leak_hits.id"), primary_key=True),
)

# Tabella di associazione per Mitre ATT&CK (CC)
mitre_leaks = Table(
    "mitre_leaks",
    Base.metadata,
    Column("mitre_id", String, ForeignKey("mitre_techniques.id"), primary_key=True),
    Column("leak_id", String, ForeignKey("leak_hits.id"), primary_key=True),
)


class MitreTechnique(Base):
    __tablename__ = "mitre_techniques"
    id = Column(String, primary_key=True)  # e.g. T1566
    name = Column(String, nullable=False)
    tactic = Column(String)  # e.g. Initial Access
    description = Column(Text)


class LeakHit(Base):
    __tablename__ = "leak_hits"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    source = Column(String, nullable=False, index=True)
    content_snippet = Column(Text)
    raw_data_url = Column(String)
    metadata_json = Column(JSON)
    severity_score = Column(Integer, default=0, index=True)
    status = Column(String, default="new", index=True)
    screenshot_path = Column(String)
    discovered_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String, ForeignKey("users.id"), nullable=True)

    tenant = relationship("Tenant", back_populates="leak_hits")
    identities = relationship("Identity", secondary=identity_leaks, back_populates="leaks")
    mitre_techniques = relationship("MitreTechnique", secondary=mitre_leaks)


class Identity(Base):
    __tablename__ = "identities"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    identifier = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)  # e.g., "email", "username"
    risk_score = Column(Integer, default=0, index=True)
    is_protected = Column(Boolean, default=False)
    master_identity_id = Column(String, ForeignKey("identities.id"), nullable=True, index=True)  # Identity Merging (V)

    leaks = relationship("LeakHit", secondary=identity_leaks, back_populates="identities")


class Webhook(Base):
    """Real-time integrations for Slack/Teams/Discord (U)"""

    __tablename__ = "webhooks"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    url = Column(String, nullable=False)
    platform = Column(String, default="generic")  # slack, discord, teams
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String)
    resource_id = Column(String)
    details = Column(JSON)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ip_address = Column(String)


class YaraRule(Base):
    __tablename__ = "yara_rules"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    content = Column(Text, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True)  # Null = Global rule
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)


class InvestigationPlan(Base):
    """AI Co-Analyst: collaborative investigation plan between user and LLM."""

    __tablename__ = "investigation_plans"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="active", index=True)  # active, completed, archived
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    tasks = relationship(
        "InvestigationTask",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="InvestigationTask.created_at",
    )


class InvestigationTask(Base):
    """A single task within an investigation plan, optionally created by the AI."""

    __tablename__ = "investigation_tasks"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String, ForeignKey("investigation_plans.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, in_progress, completed, failed
    tool_used = Column(String)  # e.g. "search_identities"
    tool_result = Column(JSON)  # raw result from tool execution
    created_by = Column(String, default="user")  # "user" | "ai"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan = relationship("InvestigationPlan", back_populates="tasks")
