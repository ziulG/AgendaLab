"""O composition root — o único ponto do sistema que conhece abstrações **e** implementações.

Todo o resto do código fala com interfaces. Aqui, e só aqui, `SqlAlchemySpaceRepository` encontra
`RequestBooking`, e `LogNotifier` encontra o `EventPublisher`. É o que o ADR-0001 chama de
composição de dependências, e é a razão de a seta apontar sempre para dentro: nenhuma camada
interna precisou saber que estas classes existem.

Três responsabilidades vivem aqui e em nenhum outro lugar:

1. **A transação.** O limite é a requisição HTTP: `commit` no fim de uma requisição bem-sucedida,
   `rollback` em qualquer exceção (ADR-0003). Os casos de uso não conhecem transação.
2. **A identidade.** `X-User-Id` e `X-User-Role` são lidos num único lugar, que constrói o `Actor`.
   Se outro arquivo os ler, o ADR-0007 foi violado.
3. **O papel exigido pela rota.** A RN-11 — só gestor aprova ou rejeita — é verificação de borda, e
   mora numa dependência reutilizada, nunca repetida em cada rota.

O relógio também entra por aqui. `RequestBookingCommand.now` é preenchido na borda porque nenhuma
camada interna lê `datetime.now()` — é o que torna as regras de antecedência testáveis com datas
fixas.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from agendalab.application.use_cases.approve_booking import ApproveBooking
from agendalab.application.use_cases.cancel_booking import CancelBooking
from agendalab.application.use_cases.check_availability import CheckAvailability
from agendalab.application.use_cases.get_booking import GetBooking
from agendalab.application.use_cases.get_space import GetSpace
from agendalab.application.use_cases.list_spaces import ListSpaces
from agendalab.application.use_cases.register_space import RegisterSpace
from agendalab.application.use_cases.reject_booking import RejectBooking
from agendalab.application.use_cases.request_booking import RequestBooking
from agendalab.domain.actor import Actor, Role
from agendalab.domain.errors import PermissionDenied
from agendalab.domain.events.publisher import EventPublisher
from agendalab.infrastructure.notifications.inbox import NotificationInbox
from agendalab.infrastructure.persistence.sqlalchemy_repositories import (
    SqlAlchemyBookingRepository,
    SqlAlchemySpaceRepository,
)

# --- transação ---------------------------------------------------------------------------------


def get_session(request: Request) -> Iterator[Session]:
    """Uma sessão por requisição, com a transação fechada aqui.

    O `rollback` no `except` é o que garante que nada seja gravado pela metade: se um caso de uso
    cadastrar um espaço e falhar em seguida, a requisição inteira é desfeita. Um `commit` dentro de
    um repositório tornaria isso impossível — por isso nenhum deles commita.
    """
    with request.app.state.sessions() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


SessionDep = Annotated[Session, Depends(get_session)]


# --- identidade e autorização de borda -----------------------------------------------------------


def get_actor(
    x_user_id: Annotated[str, Header(description="Matrícula ou e-mail de quem age")],
    x_user_role: Annotated[str, Header(description="REQUESTER ou MANAGER")],
) -> Actor:
    """O ator declarado nos cabeçalhos.

    **O sistema confia no que é declarado** — não há autenticação, e a decisão e seus riscos estão
    no ADR-0007. O que se verifica aqui é apenas que o papel é um dos dois conhecidos: um
    `X-User-Role: ADMIN` é requisição malformada, não permissão negada.
    """
    try:
        role = Role(x_user_role)
    except ValueError as erro:
        raise PermissionDenied(
            f"Papel desconhecido: {x_user_role}. Use REQUESTER ou MANAGER.", "RN-11"
        ) from erro
    return Actor(user_id=x_user_id, role=role)


ActorDep = Annotated[Actor, Depends(get_actor)]


def require_manager(actor: ActorDep) -> Actor:
    """RN-11 — somente o gestor aprova ou rejeita; §7 — somente o gestor cadastra espaço.

    Uma dependência só, reutilizada pelas rotas que a exigem. Repetir a verificação em cada função
    de rota seria repetir a regra, e regra repetida diverge.

    É a metade da autorização que pertence à borda: responder "quem é você?" não depende de nenhum
    dado do sistema. A outra metade — "esta reserva é sua?", RN-12 — depende, e por isso vive no
    domínio (ADR-0007).
    """
    if actor.role is not Role.MANAGER:
        raise PermissionDenied(
            f"A operação exige o papel {Role.MANAGER}, e {actor.user_id} é {actor.role}.",
            "RN-11",
        )
    return actor


ManagerDep = Annotated[Actor, Depends(require_manager)]


def require_requester(actor: ActorDep) -> Actor:
    """§7 — solicitar reserva é ação de solicitante.

    Não há RN numerada para isto: vem da coluna "papel exigido" da tabela de rotas, que atribui
    `POST /bookings` ao `REQUESTER`. Fica aqui, junto da outra verificação de papel, para que a
    regra de quem-pode-o-quê seja legível num arquivo só.
    """
    if actor.role is not Role.REQUESTER:
        raise PermissionDenied(
            f"Solicitar reserva é ação de {Role.REQUESTER}, e {actor.user_id} é {actor.role}.",
            "RN-11",
        )
    return actor


RequesterDep = Annotated[Actor, Depends(require_requester)]


# --- relógio -------------------------------------------------------------------------------------


def get_now() -> datetime:
    """O instante atual, lido **na borda** e passado adiante pelos comandos.

    É uma dependência, e não uma chamada direta nas rotas, para que um teste possa substituí-la por
    uma data fixa sem congelar o relógio do processo inteiro.
    """
    return datetime.now()  # noqa: DTZ005 — datas ingênuas, conforme a §7.1 da especificação


NowDep = Annotated[datetime, Depends(get_now)]


# --- eventos -------------------------------------------------------------------------------------
#
# Publicador e caixa de entrada vivem na aplicação, não na requisição: a caixa acumula o que
# aconteceu ao longo da execução, e recriá-la a cada requisição esvaziaria a demonstração do
# Observer. Quem os cria é `create_app`; aqui eles são apenas alcançados.


def get_publisher(request: Request) -> EventPublisher:
    return request.app.state.publisher


def get_inbox(request: Request) -> NotificationInbox:
    return request.app.state.inbox


PublisherDep = Annotated[EventPublisher, Depends(get_publisher)]
InboxDep = Annotated[NotificationInbox, Depends(get_inbox)]


# --- os casos de uso ------------------------------------------------------------------------------
#
# Cada função monta um caso de uso com as implementações concretas. É a linha em que a inversão de
# dependência se resolve: `RequestBooking` pediu um `SpaceRepository` e recebe o de SQLAlchemy, sem
# nunca ter ouvido falar dele.


def get_register_space(session: SessionDep) -> RegisterSpace:
    return RegisterSpace(SqlAlchemySpaceRepository(session))


def get_list_spaces(session: SessionDep) -> ListSpaces:
    return ListSpaces(SqlAlchemySpaceRepository(session))


def get_get_space(session: SessionDep) -> GetSpace:
    return GetSpace(SqlAlchemySpaceRepository(session))


def get_check_availability(session: SessionDep) -> CheckAvailability:
    return CheckAvailability(
        SqlAlchemySpaceRepository(session), SqlAlchemyBookingRepository(session)
    )


def get_get_booking(session: SessionDep) -> GetBooking:
    return GetBooking(SqlAlchemyBookingRepository(session))


def get_request_booking(session: SessionDep, publisher: PublisherDep) -> RequestBooking:
    return RequestBooking(
        SqlAlchemySpaceRepository(session),
        SqlAlchemyBookingRepository(session),
        publisher,
    )


def get_approve_booking(session: SessionDep, publisher: PublisherDep) -> ApproveBooking:
    return ApproveBooking(SqlAlchemyBookingRepository(session), publisher)


def get_reject_booking(session: SessionDep, publisher: PublisherDep) -> RejectBooking:
    return RejectBooking(SqlAlchemyBookingRepository(session), publisher)


def get_cancel_booking(session: SessionDep, publisher: PublisherDep) -> CancelBooking:
    return CancelBooking(SqlAlchemyBookingRepository(session), publisher)
