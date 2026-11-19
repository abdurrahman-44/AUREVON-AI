"""Add Intelligence Engine tables, extended AI config fields, document hash, and FTS5 index.

Revision ID: 20261112_0003
Revises: 20261111_0002
Create Date: 2026-11-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "20261112_0003"
down_revision: Union[str, None] = "20261111_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    return column_name in [c["name"] for c in sa.inspect(bind).get_columns(table_name)]


def upgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "messages"):
        if not _column_exists(bind, "messages", "tool_calls"):
            op.add_column("messages", sa.Column("tool_calls", sa.JSON(), nullable=True))
        if not _column_exists(bind, "messages", "citations"):
            op.add_column("messages", sa.Column("citations", sa.JSON(), nullable=True))
        if not _column_exists(bind, "messages", "intent"):
            op.add_column("messages", sa.Column("intent", sa.String(length=64), nullable=True))

    if _table_exists(bind, "documents"):
        if not _column_exists(bind, "documents", "content_hash"):
            op.add_column("documents", sa.Column("content_hash", sa.String(length=64), nullable=True))
            op.create_index("ix_documents_content_hash", "documents", ["content_hash"])

    if _table_exists(bind, "ai_request_logs"):
        if not _column_exists(bind, "ai_request_logs", "intent"):
            op.add_column("ai_request_logs", sa.Column("intent", sa.String(length=64), nullable=True))
            op.create_index("ix_ai_request_logs_intent", "ai_request_logs", ["intent"])
        if not _column_exists(bind, "ai_request_logs", "tools_used"):
            op.add_column("ai_request_logs", sa.Column("tools_used", sa.JSON(), nullable=True))

    if _table_exists(bind, "system_ai_configs"):
        additions = [
            ("coding_provider", sa.Column("coding_provider", sa.String(length=64), nullable=True)),
            ("coding_model", sa.Column("coding_model", sa.String(length=128), nullable=True)),
            ("max_output_tokens", sa.Column("max_output_tokens", sa.Integer(), nullable=False, server_default="2048")),
            ("keep_alive_seconds", sa.Column("keep_alive_seconds", sa.Integer(), nullable=False, server_default="900")),
            ("request_timeout_seconds", sa.Column("request_timeout_seconds", sa.Integer(), nullable=False, server_default="120")),
            ("streaming_enabled", sa.Column("streaming_enabled", sa.Boolean(), nullable=False, server_default=sa.true())),
            ("web_search_enabled", sa.Column("web_search_enabled", sa.Boolean(), nullable=False, server_default=sa.false())),
            ("cloud_inference_enabled", sa.Column("cloud_inference_enabled", sa.Boolean(), nullable=False, server_default=sa.false())),
            ("require_cloud_consent", sa.Column("require_cloud_consent", sa.Boolean(), nullable=False, server_default=sa.true())),
            ("cloud_daily_limit", sa.Column("cloud_daily_limit", sa.Integer(), nullable=False, server_default="100")),
        ]
        for col_name, col_obj in additions:
            if not _column_exists(bind, "system_ai_configs", col_name):
                op.add_column("system_ai_configs", col_obj)

    if not _table_exists(bind, "conversation_summaries"):
        op.create_table(
            "conversation_summaries",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("conversation_id", sa.String(length=36), nullable=False),
            sa.Column("summary_text", sa.Text(), nullable=False),
            sa.Column("summarized_message_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_message_id", sa.String(length=36), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("conversation_id"),
        )
        op.create_index("ix_conversation_summaries_conversation_id", "conversation_summaries", ["conversation_id"])

    if not _table_exists(bind, "tool_configs"):
        op.create_table(
            "tool_configs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tool_name", sa.String(length=64), nullable=False),
            sa.Column("display_name", sa.String(length=128), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("permission_level", sa.String(length=32), nullable=False, server_default="standard"),
            sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("max_calls_per_request", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tool_name"),
        )
        op.create_index("ix_tool_configs_tool_name", "tool_configs", ["tool_name"])

    if not _table_exists(bind, "tool_execution_logs"):
        op.create_table(
            "tool_execution_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tool_name", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("conversation_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_summary", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_tool_execution_logs_id", "tool_execution_logs", ["id"])
        op.create_index("ix_tool_execution_logs_tool_name", "tool_execution_logs", ["tool_name"])
        op.create_index("ix_tool_execution_logs_user_id", "tool_execution_logs", ["user_id"])
        op.create_index("ix_tool_execution_logs_conversation_id", "tool_execution_logs", ["conversation_id"])
        op.create_index("ix_tool_execution_logs_status", "tool_execution_logs", ["status"])
        op.create_index("ix_tool_execution_logs_created_at", "tool_execution_logs", ["created_at"])

    if not _table_exists(bind, "provider_usage_logs"):
        op.create_table(
            "provider_usage_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("is_cloud", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("consent_granted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_provider_usage_logs_id", "provider_usage_logs", ["id"])
        op.create_index("ix_provider_usage_logs_provider", "provider_usage_logs", ["provider"])
        op.create_index("ix_provider_usage_logs_model", "provider_usage_logs", ["model"])
        op.create_index("ix_provider_usage_logs_user_id", "provider_usage_logs", ["user_id"])
        op.create_index("ix_provider_usage_logs_is_cloud", "provider_usage_logs", ["is_cloud"])
        op.create_index("ix_provider_usage_logs_success", "provider_usage_logs", ["success"])
        op.create_index("ix_provider_usage_logs_created_at", "provider_usage_logs", ["created_at"])

    if bind.dialect.name == "sqlite":
        try:
            op.execute(
                sa.text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts "
                    "USING fts5(chunk_id UNINDEXED, document_id UNINDEXED, content, tokenize='porter unicode61')"
                )
            )
            if _table_exists(bind, "document_chunks"):
                op.execute(
                    sa.text(
                        "INSERT INTO document_chunks_fts(chunk_id, document_id, content) "
                        "SELECT dc.id, dc.document_id, dc.content FROM document_chunks dc "
                        "WHERE NOT EXISTS (SELECT 1 FROM document_chunks_fts f WHERE f.chunk_id = dc.id)"
                    )
                )
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        try:
            op.execute(sa.text("DROP TABLE IF EXISTS document_chunks_fts"))
        except Exception:
            pass
    for tbl in ("provider_usage_logs", "tool_execution_logs", "tool_configs", "conversation_summaries"):
        if _table_exists(bind, tbl):
            op.drop_table(tbl)
