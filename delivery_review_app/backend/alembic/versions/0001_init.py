"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-02-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


reply_status = sa.Enum("PENDING", "POSTED", "FAILED", name="replystatus")


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "platform_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("account_name", sa.String(length=120), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("platform_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform_review_id", sa.String(length=100), nullable=False),
        sa.Column("customer_name", sa.String(length=120), nullable=False),
        sa.Column("menu_name", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("connection_id", "platform_review_id", name="uq_review_connection_platform_id"),
    )
    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "replies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", reply_status, nullable=False),
        sa.Column("fail_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "reply_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reply_id", sa.Integer(), sa.ForeignKey("replies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", reply_status, nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("fail_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reply_jobs")
    op.drop_table("replies")
    op.drop_table("templates")
    op.drop_table("reviews")
    op.drop_table("platform_connections")
    op.drop_table("stores")
    reply_status.drop(op.get_bind(), checkfirst=False)
