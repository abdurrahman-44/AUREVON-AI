"""Add V2 owner roles, AI request analytics, and centralized intelligence config.

Revision ID: 20261111_0001
Revises:
Create Date: 2026-11-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "20261111_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in cols


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "users"):
        # Fresh installation: initialize the complete baseline schema idempotently.
        from backend.app.models import Base

        Base.metadata.create_all(bind=bind, checkfirst=True)
        return

    if _table_exists(bind, "users"):
        if not _column_exists(bind, "users", "role"):
            op.add_column("users", sa.Column("role", sa.String(length=32), nullable=False, server_default="user"))
        if not _column_exists(bind, "users", "is_active"):
            op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        if not _column_exists(bind, "users", "last_active_at"):
            op.add_column("users", sa.Column("last_active_at", sa.DateTime(), nullable=True))

        if not _index_exists(bind, "users", "ix_users_role"):
            op.create_index("ix_users_role", "users", ["role"])
        if not _index_exists(bind, "users", "ix_users_is_active"):
            op.create_index("ix_users_is_active", "users", ["is_active"])
        if not _index_exists(bind, "users", "ix_users_last_active_at"):
            op.create_index("ix_users_last_active_at", "users", ["last_active_at"])

    if not _table_exists(bind, "system_prompt_versions"):
        op.create_table(
            "system_prompt_versions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("notes", sa.String(length=255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_system_prompt_versions_id", "system_prompt_versions", ["id"])
        op.create_index("ix_system_prompt_versions_version_number", "system_prompt_versions", ["version_number"])
        op.create_index("ix_system_prompt_versions_is_active", "system_prompt_versions", ["is_active"])
        op.create_index("ix_system_prompt_versions_created_at", "system_prompt_versions", ["created_at"])

    if not _table_exists(bind, "system_ai_configs"):
        op.create_table(
            "system_ai_configs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("config_key", sa.String(length=64), nullable=False),
            sa.Column("active_provider", sa.String(length=64), nullable=False),
            sa.Column("active_model", sa.String(length=128), nullable=False),
            sa.Column("context_window", sa.Integer(), nullable=False),
            sa.Column("temperature", sa.Float(), nullable=False),
            sa.Column("allow_user_model_switching", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("fallback_provider", sa.String(length=64), nullable=True),
            sa.Column("fallback_model", sa.String(length=128), nullable=True),
            sa.Column("enable_memory_injection", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("enable_rag_injection", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("enable_agent_tools", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("active_prompt_version_id", sa.String(length=36), nullable=True),
            sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["active_prompt_version_id"], ["system_prompt_versions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("config_key"),
        )
        op.create_index("ix_system_ai_configs_config_key", "system_ai_configs", ["config_key"])

    if not _table_exists(bind, "ai_request_logs"):
        op.create_table(
            "ai_request_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("conversation_id", sa.String(length=36), nullable=True),
            sa.Column("request_type", sa.String(length=32), nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("first_token_ms", sa.Integer(), nullable=True),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("error_category", sa.String(length=64), nullable=True),
            sa.Column("error_message", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_request_logs_id", "ai_request_logs", ["id"])
        op.create_index("ix_ai_request_logs_user_id", "ai_request_logs", ["user_id"])
        op.create_index("ix_ai_request_logs_conversation_id", "ai_request_logs", ["conversation_id"])
        op.create_index("ix_ai_request_logs_request_type", "ai_request_logs", ["request_type"])
        op.create_index("ix_ai_request_logs_provider", "ai_request_logs", ["provider"])
        op.create_index("ix_ai_request_logs_model", "ai_request_logs", ["model"])
        op.create_index("ix_ai_request_logs_created_at", "ai_request_logs", ["created_at"])
        op.create_index("ix_ai_request_logs_success", "ai_request_logs", ["success"])
        op.create_index("ix_ai_request_logs_error_category", "ai_request_logs", ["error_category"])
        op.create_index("ix_ai_logs_created_success", "ai_request_logs", ["created_at", "success"])
        op.create_index("ix_ai_logs_provider_model", "ai_request_logs", ["provider", "model"])


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "ai_request_logs"):
        op.drop_table("ai_request_logs")
    if _table_exists(bind, "system_ai_configs"):
        op.drop_table("system_ai_configs")
    if _table_exists(bind, "system_prompt_versions"):
        op.drop_table("system_prompt_versions")
    if _table_exists(bind, "users"):
        if _index_exists(bind, "users", "ix_users_last_active_at"):
            op.drop_index("ix_users_last_active_at", table_name="users")
        if _index_exists(bind, "users", "ix_users_is_active"):
            op.drop_index("ix_users_is_active", table_name="users")
        if _index_exists(bind, "users", "ix_users_role"):
            op.drop_index("ix_users_role", table_name="users")
        if _column_exists(bind, "users", "last_active_at"):
            op.drop_column("users", "last_active_at")
        if _column_exists(bind, "users", "is_active"):
            op.drop_column("users", "is_active")
        if _column_exists(bind, "users", "role"):
            op.drop_column("users", "role")
