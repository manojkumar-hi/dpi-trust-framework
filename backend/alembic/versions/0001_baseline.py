"""baseline existing Module 8.3 schema

Revision ID: 0001_baseline
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain"),
    )
    op.create_index("ix_organizations_domain", "organizations", ["domain"], unique=False)

    op.create_table(
        "organization_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("did", sa.String(length=500), nullable=False),
        sa.Column("public_key", sa.String(length=500), nullable=False),
        sa.Column("key_algorithm", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("did"),
        sa.UniqueConstraint("organization_id", name="uq_organization_identities_organization_id"),
    )
    op.create_index("ix_organization_identities_did", "organization_identities", ["did"], unique=False)

    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("agent_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agents_organization_id", "agents", ["organization_id"], unique=False)

    op.create_table(
        "agent_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("did", sa.String(length=500), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("key_algorithm", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("did"),
        sa.UniqueConstraint("agent_id", name="uq_agent_identities_agent_id"),
    )
    op.create_index("ix_agent_identities_did", "agent_identities", ["did"], unique=False)

    op.create_table(
        "verifiable_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuer_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_type", sa.String(length=150), nullable=False),
        sa.Column("credential_data", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("proof_type", sa.String(length=100), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["issuer_organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["subject_agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_verifiable_credentials_issuer_organization_id", "verifiable_credentials", ["issuer_organization_id"], unique=False)
    op.create_index("ix_verifiable_credentials_subject_agent_id", "verifiable_credentials", ["subject_agent_id"], unique=False)
    op.create_index("ix_verifiable_credentials_credential_type", "verifiable_credentials", ["credential_type"], unique=False)
    op.create_index("ix_verifiable_credentials_status", "verifiable_credentials", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("verifiable_credentials")
    op.drop_index("ix_agent_identities_did", table_name="agent_identities")
    op.drop_table("agent_identities")
    op.drop_index("ix_agents_organization_id", table_name="agents")
    op.drop_table("agents")
    op.drop_index("ix_organization_identities_did", table_name="organization_identities")
    op.drop_table("organization_identities")
    op.drop_index("ix_organizations_domain", table_name="organizations")
    op.drop_table("organizations")