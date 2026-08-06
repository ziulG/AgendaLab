"""A aplicação FastAPI.

`create_app` é o composition root propriamente dito: monta o engine, cria o esquema, instancia o
publicador com os dois observadores inscritos e registra rotas e tratadores. É a única função do
sistema que precisa saber que SQLAlchemy, SQLite e `LogNotifier` existem.

Recebe a URL do banco por parâmetro, e o módulo expõe uma instância pronta em `app` para o
`uvicorn`. A separação importa: um teste monta a aplicação sobre um banco temporário chamando
`create_app(...)`, sem variável de ambiente e sem tocar o banco de desenvolvimento.

Acrescentar um canal de notificação é uma linha aqui. Trocar SQLite por outro banco é outra. Nenhum
caso de uso muda — é o que o ADR-0001 promete, e este arquivo é onde a promessa se paga.
"""

from __future__ import annotations

from fastapi import FastAPI

from agendalab.domain.events.publisher import EventPublisher
from agendalab.infrastructure.notifications.inbox import NotificationInbox
from agendalab.infrastructure.notifications.log_notifier import LogNotifier
from agendalab.infrastructure.persistence.database import (
    create_engine_for,
    create_schema,
    session_factory,
)
from agendalab.presentation.api import bookings, notifications, spaces
from agendalab.presentation.error_handlers import register_error_handlers

DEFAULT_DB_URL = "sqlite:///agendalab.db"

DESCRICAO = """
Sistema de reserva de salas e laboratórios universitários.

**A identidade chega por cabeçalho e não é verificada** — `X-User-Id` e `X-User-Role`
(`REQUESTER` ou `MANAGER`). A autorização, essa sim, está implementada por inteiro.
Não exponha esta aplicação em rede.
"""


def create_app(db_url: str = DEFAULT_DB_URL) -> FastAPI:
    """A aplicação, ligada ao banco indicado."""
    app = FastAPI(
        title="AgendaLab",
        description=DESCRICAO,
        version="0.1.0",
        summary="Projeto Final de Arquitetura de Software — UFMA",
    )

    engine = create_engine_for(db_url)
    create_schema(engine)  # sem migrações: o esquema nasce dos metadados (ADR-0003)
    app.state.engine = engine
    app.state.sessions = session_factory(engine)

    # O Observer, montado. O publicador conhece a interface; estes dois a implementam, e nenhum
    # deles é conhecido pelo domínio. Um terceiro canal seria mais uma linha `subscribe`.
    inbox = NotificationInbox()
    publisher = EventPublisher()
    publisher.subscribe(LogNotifier())
    publisher.subscribe(inbox)
    app.state.inbox = inbox
    app.state.publisher = publisher

    register_error_handlers(app)
    app.include_router(spaces.router)
    app.include_router(bookings.router)
    app.include_router(notifications.router)

    return app


app = create_app()
