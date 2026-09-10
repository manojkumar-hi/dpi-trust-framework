"""add Module 9 delegation foundation

Revision ID: 0002_module9
Revises: 0001_baseline
"""
from uuid import uuid4

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_module9"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_identity_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verification_method", sa.String(length=500), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("key_algorithm", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'retired')",
            name="ck_organization_identity_keys_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_identity_id"],
            ["organization_identities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("verification_method"),
    )
    op.create_index(
        "ix_organization_identity_keys_organization_identity_id",
        "organization_identity_keys",
        ["organization_identity_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_identity_keys_status",
        "organization_identity_keys",
        ["status"],
        unique=False,
    )
    op.create_index(
        "uq_organization_identity_keys_active",
        "organization_identity_keys",
        ["organization_identity_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    if not context.is_offline_mode():
        connection = op.get_bind()
        key_table = sa.table(
            "organization_identity_keys",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("organization_identity_id", postgresql.UUID(as_uuid=True)),
            sa.column("verification_method", sa.String()),
            sa.column("public_key", sa.Text()),
            sa.column("key_algorithm", sa.String()),
            sa.column("status", sa.String()),
            sa.column("valid_from", sa.DateTime(timezone=True)),
        )
        existing_identities = connection.execute(
            sa.text(
                "SELECT id, did, public_key, key_algorithm, created_at "
                "FROM organization_identities"
            )
        ).mappings()
        connection.execute(
            key_table.insert(),
            [
                {
                    "id": uuid4(),
                    "organization_identity_id": identity["id"],
                    "verification_method": f"{identity['did']}#key-1",
                    "public_key": identity["public_key"],
                    "key_algorithm": identity["key_algorithm"],
                    "status": "active",
                    "valid_from": identity["created_at"],
                }
                for identity in existing_identities
            ],
        )

    op.create_table(
        "delegations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegator_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegatee_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegator_did", sa.String(length=500), nullable=False),
        sa.Column("delegatee_did", sa.String(length=500), nullable=False),
        sa.Column("parent_delegation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("root_delegation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("proof_type", sa.String(length=100), nullable=False),
        sa.Column("verification_method", sa.String(length=500), nullable=False),
        sa.Column("signing_public_key", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_hash", sa.String(length=64), nullable=False),
        sa.Column("fabric_transaction_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("starts_at < expires_at", name="ck_delegations_start_before_expiry"),
        sa.CheckConstraint("depth >= 0", name="ck_delegations_non_negative_depth"),
        sa.CheckConstraint(
            "status IN ('active', 'revoked', 'expired')",
            name="ck_delegations_valid_status",
        ),
        sa.CheckConstraint(
            "(status = 'revoked' AND revoked_at IS NOT NULL AND revocation_reason IS NOT NULL AND length(trim(revocation_reason)) > 0) OR (status <> 'revoked' AND revoked_at IS NULL)",
            name="ck_delegations_revocation_fields",
        ),
        sa.ForeignKeyConstraint(["delegator_organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["delegatee_agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["parent_delegation_id"], ["delegations.id"]),
        sa.ForeignKeyConstraint(["root_delegation_id"], ["delegations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_hash"),
    )
    op.create_index("ix_delegations_delegator_organization_id", "delegations", ["delegator_organization_id"], unique=False)
    op.create_index("ix_delegations_delegatee_agent_id", "delegations", ["delegatee_agent_id"], unique=False)
    op.create_index("ix_delegations_parent_delegation_id", "delegations", ["parent_delegation_id"], unique=False)
    op.create_index("ix_delegations_root_delegation_id", "delegations", ["root_delegation_id"], unique=False)
    op.create_index("ix_delegations_status", "delegations", ["status"], unique=False)
    op.create_index("ix_delegations_expires_at", "delegations", ["expires_at"], unique=False)

    op.create_table(
        "delegation_capabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability_code", sa.String(length=100), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["delegation_id"], ["delegations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_delegation_capabilities_delegation_id", "delegation_capabilities", ["delegation_id"], unique=False)
    op.create_index("ix_delegation_capabilities_code", "delegation_capabilities", ["capability_code"], unique=False)

    op.create_table(
        "delegation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=True),
        sa.Column("actor_did", sa.String(length=500), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("fabric_transaction_id", sa.String(length=255), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["delegation_id"], ["delegations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_delegation_events_delegation_id", "delegation_events", ["delegation_id"], unique=False)
    op.create_index(
        "ix_delegation_events_delegation_occurred",
        "delegation_events",
        ["delegation_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("delegation_events")
    op.drop_table("delegation_capabilities")
    op.drop_table("delegations")
    op.drop_index("uq_organization_identity_keys_active", table_name="organization_identity_keys")
    op.drop_index("ix_organization_identity_keys_status", table_name="organization_identity_keys")
    op.drop_index("ix_organization_identity_keys_organization_identity_id", table_name="organization_identity_keys")
    op.drop_table("organization_identity_keys")