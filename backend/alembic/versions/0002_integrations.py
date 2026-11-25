"""Add integration_connections table for external DMS providers."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("access_token", sa.String(length=2048), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=True),
        sa.Column("refresh_token", sa.String(length=2048), nullable=True),
        sa.Column("sync_cursor", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_integrations_tenant_provider",
        "integration_connections",
        ["tenant_id", "provider"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_integrations_tenant_provider", table_name="integration_connections"
    )
    op.drop_table("integration_connections")
