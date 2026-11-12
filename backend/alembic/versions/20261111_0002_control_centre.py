"""Add Control Centre audit logs, security events, revoked tokens, API logs, 2FA, and platform config.

Revision ID: 20261111_0002
Revises: 20261111_0001
Create Date: 2026-11-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "20261111_0002"
down_revision: Union[str, None] = "20261111_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    return column_name in [c["name"] for c in sa.inspect(bind).get_columns(table_name)]


def upgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "users"):
        if not _column_exists(bind, "users", "totp_secret"):
            op.add_column("users", sa.Column("totp_secret", sa.String(length=64), nullable=True))
        if not _column_exists(bind, "users", "totp_enabled"):
            op.add_column("users", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))

    if not _table_exists(bind, "revoked_tokens"):
        op.create_table(
            "revoked_tokens",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("jti", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("jti"),
        )
        op.create_index("ix_revoked_tokens_jti", "revoked_tokens", ["jti"])
        op.create_index("ix_revoked_tokens_user_id", "revoked_tokens", ["user_id"])
        op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])
        op.create_index("ix_revoked_tokens_revoked_at", "revoked_tokens", ["revoked_at"])

    if not _table_exists(bind, "admin_audit_logs"):
        op.create_table(
            "admin_audit_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("actor_user_id", sa.String(length=36), nullable=True),
            sa.Column("actor_username", sa.String(length=64), nullable=False),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("target_type", sa.String(length=64), nullable=True),
            sa.Column("target_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
            sa.Column("summary", sa.String(length=255), nullable=False),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_admin_audit_logs_id", "admin_audit_logs", ["id"])
        op.create_index("ix_admin_audit_logs_actor_user_id", "admin_audit_logs", ["actor_user_id"])
        op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
        op.create_index("ix_admin_audit_logs_status", "admin_audit_logs", ["status"])
        op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])

    if not _table_exists(bind, "security_events"):
        op.create_table(
            "security_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("identifier", sa.String(length=255), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("path", sa.String(length=255), nullable=True),
            sa.Column("detail", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_security_events_id", "security_events", ["id"])
        op.create_index("ix_security_events_event_type", "security_events", ["event_type"])
        op.create_index("ix_security_events_severity", "security_events", ["severity"])
        op.create_index("ix_security_events_user_id", "security_events", ["user_id"])
        op.create_index("ix_security_events_created_at", "security_events", ["created_at"])

    if not _table_exists(bind, "api_request_logs"):
        op.create_table(
            "api_request_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("method", sa.String(length=16), nullable=False),
            sa.Column("path", sa.String(length=255), nullable=False),
            sa.Column("status_code", sa.Integer(), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("client_ip", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_api_request_logs_id", "api_request_logs", ["id"])
        op.create_index("ix_api_request_logs_path", "api_request_logs", ["path"])
        op.create_index("ix_api_request_logs_status_code", "api_request_logs", ["status_code"])
        op.create_index("ix_api_request_logs_user_id", "api_request_logs", ["user_id"])
        op.create_index("ix_api_request_logs_created_at", "api_request_logs", ["created_at"])
        op.create_index("ix_api_logs_created_status", "api_request_logs", ["created_at", "status_code"])

    if not _table_exists(bind, "platform_configs"):
        op.create_table(
            "platform_configs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("config_key", sa.String(length=64), nullable=False),
            sa.Column("app_display_name", sa.String(length=128), nullable=False),
            sa.Column("maintenance_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("maintenance_message", sa.String(length=255), nullable=False),
            sa.Column("allow_public_registration", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("log_retention_days", sa.Integer(), nullable=False),
            sa.Column("auth_rate_limit_per_min", sa.Integer(), nullable=False),
            sa.Column("chat_rate_limit_per_min", sa.Integer(), nullable=False),
            sa.Column("upload_rate_limit_per_min", sa.Integer(), nullable=False),
            sa.Column("enable_api_request_logging", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("config_key"),
        )
        op.create_index("ix_platform_configs_config_key", "platform_configs", ["config_key"])


def downgrade() -> None:
    bind = op.get_bind()
    for tbl in ("platform_configs", "api_request_logs", "security_events", "admin_audit_logs", "revoked_tokens"):
        if _table_exists(bind, tbl):
            op.drop_table(tbl)
    if _table_exists(bind, "users"):
        if _column_exists(bind, "users", "totp_enabled"):
            op.drop_column("users", "totp_enabled")
        if _column_exists(bind, "users", "totp_secret"):
            op.drop_column("users", "totp_secret")
