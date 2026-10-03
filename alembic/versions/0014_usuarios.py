"""Create copilot.usuarios, copilot.sessoes and copilot.tentativas_login (ADR-0007).

Users log in with e-mail and password (argon2id). The session token lives in a cookie
and only its hash is stored. `tentativas_login` keeps the failed attempts for the lockout.

Revision ID: 0014_usuarios
Revises: 0013_lead_time_ignorado
Create Date: 2026-10-03

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_usuarios"
down_revision: Union[str, Sequence[str], None] = "0013_lead_time_ignorado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PAPEIS = "ARRAY['comprador', 'vendas', 'reposicao', 'admin']::text[]"


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nome", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("senha_hash", sa.Text, nullable=False),
        sa.Column("papeis", postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ultimo_acesso_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("btrim(nome) <> ''", name="usuarios_nome_check"),
        sa.CheckConstraint("email = lower(btrim(email)) AND email <> ''", name="usuarios_email_check"),
        sa.CheckConstraint(f"papeis <@ {_PAPEIS}", name="usuarios_papeis_check"),
        schema="copilot",
    )
    op.create_table(
        "sessoes",
        sa.Column("token_hash", sa.Text, primary_key=True),
        sa.Column(
            "usuario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("copilot.usuarios.id"),
            nullable=False,
        ),
        sa.Column("criada_em", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("expira_em", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revogada_em", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="copilot",
    )
    op.create_index("sessoes_usuario_id_idx", "sessoes", ["usuario_id"], schema="copilot")
    op.create_table(
        "tentativas_login",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("tentada_em", sa.TIMESTAMP(timezone=True), nullable=False),
        schema="copilot",
    )
    op.create_index(
        "tentativas_login_email_tentada_em_idx", "tentativas_login", ["email", "tentada_em"], schema="copilot"
    )


def downgrade() -> None:
    op.drop_table("tentativas_login", schema="copilot")
    op.drop_table("sessoes", schema="copilot")
    op.drop_table("usuarios", schema="copilot")
