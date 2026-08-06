"""O esquema e a sessão.

Não há ferramenta de migração: o esquema nasce dos metadados na inicialização, decisão registrada no
ADR-0003. Estes testes verificam que ele nasce com as tabelas e colunas do diagrama ER — se um
modelo for renomeado ou uma coluna sumir, é aqui que aparece primeiro.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from agendalab.infrastructure.persistence.database import (
    create_engine_for,
    create_schema,
    session_factory,
)

TABELAS_ESPERADAS = {"spaces", "bookings"}

COLUNAS_DE_SPACES = {"code", "name", "kind", "capacity", "active"}
COLUNAS_DE_BOOKINGS = {
    "id",
    "space_code",
    "requester_id",
    "start_at",
    "end_at",
    "purpose",
    "attendees",
    "status",
    "created_at",
    "decided_by",
    "decided_at",
    "rejection_reason",
}


def test_o_esquema_cria_as_duas_tabelas(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) >= TABELAS_ESPERADAS


@pytest.mark.parametrize(
    ("tabela", "esperadas"),
    [("spaces", COLUNAS_DE_SPACES), ("bookings", COLUNAS_DE_BOOKINGS)],
)
def test_as_colunas_sao_as_do_diagrama_er(
    engine: Engine, tabela: str, esperadas: set[str]
) -> None:
    """O diagrama da ARQUITETURA §10 e o esquema real precisam continuar dizendo a mesma coisa."""
    colunas = {c["name"] for c in inspect(engine).get_columns(tabela)}
    assert colunas == esperadas


def test_o_intervalo_e_duas_colunas_e_nao_uma(engine: Engine) -> None:
    """`TimeSlot` não tem coluna própria: o objeto de valor do domínio vira `start_at` e `end_at`."""
    colunas = {c["name"] for c in inspect(engine).get_columns("bookings")}
    assert {"start_at", "end_at"} <= colunas
    assert "slot" not in colunas


def test_o_codigo_do_espaco_e_a_chave_primaria(engine: Engine) -> None:
    """Chave natural, o que torna as rotas legíveis — e caro renomear um código, como o ADR-0003
    assume ao declarar o código imutável."""
    assert inspect(engine).get_pk_constraint("spaces")["constrained_columns"] == ["code"]


def test_a_reserva_referencia_o_espaco_pelo_codigo(engine: Engine) -> None:
    (fk,) = inspect(engine).get_foreign_keys("bookings")
    assert (fk["constrained_columns"], fk["referred_table"], fk["referred_columns"]) == (
        ["space_code"],
        "spaces",
        ["code"],
    )


def test_a_integridade_referencial_esta_ligada(session: Session) -> None:
    """No SQLite as chaves estrangeiras vêm desligadas por padrão — declarar a FK não basta."""
    ligada = session.execute(text("PRAGMA foreign_keys")).scalar()
    assert ligada == 1


def test_criar_o_esquema_duas_vezes_nao_falha(db_url: str) -> None:
    """A aplicação chama isto a cada inicialização, e o banco pode já existir."""
    motor = create_engine_for(db_url)
    create_schema(motor)
    create_schema(motor)
    assert set(inspect(motor).get_table_names()) >= TABELAS_ESPERADAS
    motor.dispose()


def test_o_arquivo_de_banco_e_criado_no_caminho_indicado(db_url: str) -> None:
    motor = create_engine_for(db_url)
    create_schema(motor)
    with session_factory(motor)() as sessao:
        sessao.execute(text("SELECT 1"))
    motor.dispose()

    assert Path(db_url.removeprefix("sqlite:///")).is_file()
