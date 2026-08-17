"""notification acknowledgement — leak_hits.acknowledged_at / acknowledged_by

Revision ID: 20260817_02_ack
Revises: 20260420_01_corr_v2
Create Date: 2026-08-17

The columns behind the end-to-end notification ack (b8826d8) were added to
``shared/models.py`` and never to a migration. Fresh installs did not notice:
``init_db.py`` builds the schema with ``Base.metadata.create_all()``, which
materialises whatever the models currently say. Any database that already
existed kept the old ``leak_hits``, and the first insert against the current
models died with

    column "acknowledged_at" of relation "leak_hits" does not exist

which is what `make demo` did here, on a database created in April, once the
correlation-engine migration had been applied and got it that far.

The drift was found with ``alembic.autogenerate.compare_metadata`` against a
real Postgres, and it is exactly these two columns plus the foreign key.

Idempotent in the same style as the baseline revision, because it has to run
against databases where ``create_all`` has already produced these columns.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260817_02_ack"
down_revision = "20260420_01_corr_v2"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def _has_fk(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return name in {fk.get("name") for fk in inspector.get_foreign_keys(table)}


def upgrade() -> None:
    with op.batch_alter_table("leak_hits") as batch:
        if not _has_column("leak_hits", "acknowledged_at"):
            batch.add_column(sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
        if not _has_column("leak_hits", "acknowledged_by"):
            batch.add_column(sa.Column("acknowledged_by", sa.String(), nullable=True))

    # Named explicitly: an unnamed constraint cannot be inspected for
    # idempotence here, and cannot be dropped by name on downgrade.
    if not _has_fk("leak_hits", "fk_leak_hits_acknowledged_by_users"):
        with op.batch_alter_table("leak_hits") as batch:
            batch.create_foreign_key(
                "fk_leak_hits_acknowledged_by_users",
                "users",
                ["acknowledged_by"],
                ["id"],
            )


def downgrade() -> None:
    with op.batch_alter_table("leak_hits") as batch:
        if _has_fk("leak_hits", "fk_leak_hits_acknowledged_by_users"):
            batch.drop_constraint("fk_leak_hits_acknowledged_by_users", type_="foreignkey")
        if _has_column("leak_hits", "acknowledged_by"):
            batch.drop_column("acknowledged_by")
        if _has_column("leak_hits", "acknowledged_at"):
            batch.drop_column("acknowledged_at")
