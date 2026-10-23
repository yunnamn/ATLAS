"""Separate semantic assessments from citations; add explicit human approval proposals."""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_claims",
        sa.Column("semantic_assessment", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "research_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column(
            "target_opportunity_id", sa.Integer(), sa.ForeignKey("opportunities.id"), nullable=True
        ),
        sa.Column("expected_opportunity_revision", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("approval", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_research_proposals_run_id", "research_proposals", ["run_id"])


def downgrade() -> None:
    op.drop_table("research_proposals")
    with op.batch_alter_table("research_claims") as batch:
        batch.drop_column("semantic_assessment")
