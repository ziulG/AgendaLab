"""Engine, sessão e criação do esquema.

**Sem estado global.** Nenhum engine de módulo, nenhum `SessionLocal` importável: as três funções
recebem o que precisam e devolvem o que produzem. Quem monta o engine da aplicação é o composition
root da task 11, e quem monta o de teste é a fixture — e é por isso que a suíte pode usar um arquivo
temporário por teste sem nada para desfazer depois.

Não há ferramenta de migração. O esquema nasce dos metadados na inicialização, decisão registrada no
ADR-0003: com banco em arquivo local e um MVP sem histórico de produção a preservar, migração seria
infraestrutura sem propósito.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class Base(DeclarativeBase):
    """A base dos modelos de persistência — e **somente** deles.

    Nenhuma entidade de domínio herda daqui. É a regra que o ADR-0003 escolheu proteger, e o teste
    de arquitetura a garante por outro caminho: `domain/` não pode importar `sqlalchemy`, logo não
    tem como herdar desta classe nem por acidente.
    """


def create_engine_for(url: str) -> Engine:
    """O engine para a URL indicada, com dois desvios do comportamento padrão do SQLite.

    **Integridade referencial.** O SQLite vem com chaves estrangeiras desligadas, por
    compatibilidade histórica. Declarar a `ForeignKey` no modelo não basta: sem o `PRAGMA`, uma
    reserva poderia apontar para um espaço que não existe e o banco aceitaria em silêncio.

    **Transações de verdade.** O driver `pysqlite` gerencia transações por conta própria e de um
    jeito que não abre `BEGIN` quando deveria — o que faz `SAVEPOINT` rodar fora de transação e,
    pior, faz um `rollback` posterior não ter o que desfazer. O efeito prático seria grave e
    silencioso: uma requisição que falhasse no meio deixaria gravado o que já tinha escrito,
    exatamente o oposto do que o ADR-0003 promete ao pôr o limite transacional na requisição.

    A correção é a recomendada pela documentação do SQLAlchemy: desligar o controle de transação do
    driver e emitir o `BEGIN` explicitamente. Está verificada por
    `tests/e2e/test_criterios_da_borda.py`, que grava, falha de propósito e confere que nada ficou.
    """
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _preparar_conexao(dbapi_connection: Any, _: Any) -> None:  # noqa: ANN401
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        dbapi_connection.isolation_level = None  # o SQLAlchemy passa a controlar a transação

    @event.listens_for(engine, "begin")
    def _abrir_transacao(conn: Any) -> None:  # noqa: ANN401
        conn.exec_driver_sql("BEGIN")

    return engine


def create_schema(engine: Engine) -> None:
    """Cria as tabelas que faltam. Chamável a cada inicialização, sem efeito na segunda vez."""
    from agendalab.infrastructure.persistence import models  # noqa: F401  — registra os modelos

    Base.metadata.create_all(engine)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    """A fábrica de sessões.

    `expire_on_commit=False` porque os repositórios devolvem entidades de domínio, desligadas da
    sessão: expirar os modelos após o commit forçaria recarregamentos que não servem a ninguém.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)
