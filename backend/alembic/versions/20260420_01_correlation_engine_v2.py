"""correlation engine v2 — normalized identifiers, merge ledger, hash chain, simhash

Revision ID: 20260420_01_corr_v2
Revises:
Create Date: 2026-04-20

This is the first real Alembic migration of the project; prior schema was
created with ``Base.metadata.create_all()`` and has no version stamp. To keep
existing deployments working we use a two-step strategy:

  1. Create every new column/table with ``IF NOT EXISTS``-equivalent logic so
     the migration is idempotent against databases that already had the base
     schema materialised by ``init_db.py``.
  2. Backfill ``identities.normalized_identifier`` for pre-existing rows using
     the same normalization the Python helper produces (lowercase + whitespace
     strip; the helper handles Gmail alias collapsing on NEW rows).

The new surface:

  * ``identities.normalized_identifier`` + unique ``(tenant_id, type, normalized_identifier)``
  * ``identities.confidence``, ``first_seen``, ``last_seen``, ``risk_score_dirty``
  * ``leak_hits.normalized_content``, ``leak_hits.simhash64``
  * ``audit_logs.prev_hash``, ``audit_logs.self_hash`` + composite index
  * ``merge_events`` table (append-only ledger with hash chain)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260420_01_corr_v2"
down_revision = None
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table)}


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in set(inspector.get_table_names())


def _has_index(table: str, index: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index in {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    # ── identities: new columns ────────────────────────────────────────────────
    with op.batch_alter_table("identities") as batch:
        if not _has_column("identities", "normalized_identifier"):
            batch.add_column(sa.Column("normalized_identifier", sa.String(), nullable=True))
        if not _has_column("identities", "confidence"):
            batch.add_column(sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"))
        if not _has_column("identities", "first_seen"):
            batch.add_column(sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now()))
        if not _has_column("identities", "last_seen"):
            batch.add_column(sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now()))
        if not _has_column("identities", "risk_score_dirty"):
            batch.add_column(
                sa.Column("risk_score_dirty", sa.Boolean(), nullable=False, server_default=sa.false())
            )

    # Backfill normalized_identifier for legacy rows using the SAME rule the
    # Python helper uses (lower + strip). Gmail alias collapsing only kicks in
    # on new writes; legacy rows keep their historical form.
    op.execute(
        """
        UPDATE identities
           SET normalized_identifier = lower(trim(identifier))
         WHERE normalized_identifier IS NULL
        """
    )

    if not _has_index("identities", "ix_identities_normalized_identifier"):
        op.create_index(
            "ix_identities_normalized_identifier",
            "identities",
            ["normalized_identifier"],
        )
    if not _has_index("identities", "ix_identities_risk_score_dirty"):
        op.create_index(
            "ix_identities_risk_score_dirty",
            "identities",
            ["risk_score_dirty"],
        )

    # Unique constraint — created after backfill so we don't violate it.
    # Use batch_alter_table because SQLite needs a table rebuild to add UNIQUE.
    existing_uqs = {
        c["name"] for c in sa.inspect(op.get_bind()).get_unique_constraints("identities")
    }
    if "uq_identities_normalized" not in existing_uqs:
        with op.batch_alter_table("identities") as batch:
            batch.create_unique_constraint(
                "uq_identities_normalized",
                ["tenant_id", "type", "normalized_identifier"],
            )

    # ── leak_hits: fuzzy-dedup columns ────────────────────────────────────────
    with op.batch_alter_table("leak_hits") as batch:
        if not _has_column("leak_hits", "normalized_content"):
            batch.add_column(sa.Column("normalized_content", sa.Text(), nullable=True))
        if not _has_column("leak_hits", "simhash64"):
            batch.add_column(sa.Column("simhash64", sa.BigInteger(), nullable=True))

    if not _has_index("leak_hits", "ix_leak_hits_simhash64"):
        op.create_index("ix_leak_hits_simhash64", "leak_hits", ["simhash64"])

    # ── audit_logs: hash chain ────────────────────────────────────────────────
    with op.batch_alter_table("audit_logs") as batch:
        if not _has_column("audit_logs", "prev_hash"):
            batch.add_column(sa.Column("prev_hash", sa.String(), nullable=True))
        if not _has_column("audit_logs", "self_hash"):
            batch.add_column(sa.Column("self_hash", sa.String(), nullable=True))

    if not _has_index("audit_logs", "ix_audit_logs_self_hash"):
        op.create_index("ix_audit_logs_self_hash", "audit_logs", ["self_hash"])
    if not _has_index("audit_logs", "ix_audit_tenant_time"):
        op.create_index("ix_audit_tenant_time", "audit_logs", ["tenant_id", "timestamp"])

    # ── merge_events: append-only ledger ──────────────────────────────────────
    if not _has_table("merge_events"):
        op.create_table(
            "merge_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("master_id", sa.String(), sa.ForeignKey("identities.id"), nullable=False),
            sa.Column("slave_id", sa.String(), sa.ForeignKey("identities.id"), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("performed_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column(
                "performed_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reversed_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("reverse_reason", sa.Text(), nullable=True),
            sa.Column("prev_hash", sa.String(), nullable=True),
            sa.Column("self_hash", sa.String(), nullable=False),
        )
        op.create_index("ix_merge_events_tenant_id", "merge_events", ["tenant_id"])
        op.create_index("ix_merge_events_master_id", "merge_events", ["master_id"])
        op.create_index("ix_merge_events_slave_id", "merge_events", ["slave_id"])
        op.create_index("ix_merge_events_performed_at", "merge_events", ["performed_at"])
        op.create_index(
            "ix_merge_events_pair", "merge_events", ["tenant_id", "master_id", "slave_id"]
        )
        op.create_index(
            "ix_merge_events_active_slave",
            "merge_events",
            ["tenant_id", "slave_id", "reversed_at"],
        )


def downgrade() -> None:
    # Drop merge_events first (FKs to identities/users).
    if _has_table("merge_events"):
        op.drop_table("merge_events")

    with op.batch_alter_table("audit_logs") as batch:
        if _has_index("audit_logs", "ix_audit_tenant_time"):
            batch.drop_index("ix_audit_tenant_time")
        if _has_index("audit_logs", "ix_audit_logs_self_hash"):
            batch.drop_index("ix_audit_logs_self_hash")
        if _has_column("audit_logs", "self_hash"):
            batch.drop_column("self_hash")
        if _has_column("audit_logs", "prev_hash"):
            batch.drop_column("prev_hash")

    with op.batch_alter_table("leak_hits") as batch:
        if _has_index("leak_hits", "ix_leak_hits_simhash64"):
            batch.drop_index("ix_leak_hits_simhash64")
        if _has_column("leak_hits", "simhash64"):
            batch.drop_column("simhash64")
        if _has_column("leak_hits", "normalized_content"):
            batch.drop_column("normalized_content")

    with op.batch_alter_table("identities") as batch:
        existing_uqs = {
            c["name"] for c in sa.inspect(op.get_bind()).get_unique_constraints("identities")
        }
        if "uq_identities_normalized" in existing_uqs:
            batch.drop_constraint("uq_identities_normalized", type_="unique")
        if _has_index("identities", "ix_identities_risk_score_dirty"):
            batch.drop_index("ix_identities_risk_score_dirty")
        if _has_index("identities", "ix_identities_normalized_identifier"):
            batch.drop_index("ix_identities_normalized_identifier")
        if _has_column("identities", "risk_score_dirty"):
            batch.drop_column("risk_score_dirty")
        if _has_column("identities", "last_seen"):
            batch.drop_column("last_seen")
        if _has_column("identities", "first_seen"):
            batch.drop_column("first_seen")
        if _has_column("identities", "confidence"):
            batch.drop_column("confidence")
        if _has_column("identities", "normalized_identifier"):
            batch.drop_column("normalized_identifier")
