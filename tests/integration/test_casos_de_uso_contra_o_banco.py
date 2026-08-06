"""Os casos de uso das tasks 07 a 09, sem uma linha alterada, contra SQLite de verdade.

Este é o teste que fecha o argumento do ADR-0001. `RequestBooking` foi escrito e testado contra
duplas em memória, não sabe que SQLAlchemy existe, e é construído aqui com implementações que ele
nunca viu — porque as duas satisfazem a interface que o **domínio** declarou.

Se a inversão de dependência fosse decorativa, alguma coisa aqui precisaria mudar. Nada muda: os
casos de uso recebem outro objeto no `__init__` e seguem funcionando.

É deliberadamente um fio fino — um fluxo completo, não a matriz de casos. A cobertura das regras
está nos testes unitários, que rodam em milissegundos; o que falta provar aqui é a integração.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from agendalab.application.dto import (
    ApproveBookingCommand,
    CancelBookingCommand,
    CheckAvailabilityQuery,
    ListSpacesQuery,
    RegisterSpaceCommand,
    RequestBookingCommand,
)
from agendalab.application.use_cases.approve_booking import ApproveBooking
from agendalab.application.use_cases.cancel_booking import CancelBooking
from agendalab.application.use_cases.check_availability import CheckAvailability
from agendalab.application.use_cases.list_spaces import ListSpaces
from agendalab.application.use_cases.register_space import RegisterSpace
from agendalab.application.use_cases.request_booking import RequestBooking
from agendalab.domain.actor import Actor, Role
from agendalab.domain.entities.booking import BookingStatus
from agendalab.domain.entities.space import SpaceKind
from agendalab.domain.errors import ScheduleConflict
from agendalab.domain.events.publisher import EventPublisher
from agendalab.domain.value_objects.time_slot import TimeSlot
from agendalab.infrastructure.notifications.inbox import NotificationInbox
from agendalab.infrastructure.persistence.database import session_factory
from agendalab.infrastructure.persistence.sqlalchemy_repositories import (
    SqlAlchemyBookingRepository,
    SqlAlchemySpaceRepository,
)

AGORA = datetime(2026, 8, 5, 9, 0)
QUINTA = datetime(2026, 8, 20, 14, 0)
DECISAO = datetime(2026, 8, 6, 10, 30)

SOLICITANTE = "2019001234"
GESTOR = Actor(user_id="1998007766", role=Role.MANAGER)
DONO = Actor(user_id=SOLICITANTE, role=Role.REQUESTER)


class Aplicacao:
    """O que a task 11 vai montar como composition root, aqui montado à mão."""

    def __init__(self, session: Session) -> None:
        spaces = SqlAlchemySpaceRepository(session)
        bookings = SqlAlchemyBookingRepository(session)

        self.inbox = NotificationInbox()
        publisher = EventPublisher()
        publisher.subscribe(self.inbox)

        self.cadastrar = RegisterSpace(spaces)
        self.listar = ListSpaces(spaces)
        self.consultar = CheckAvailability(spaces, bookings)
        self.solicitar = RequestBooking(spaces, bookings, publisher)
        self.aprovar = ApproveBooking(bookings, publisher)
        self.cancelar = CancelBooking(bookings, publisher)


@pytest.fixture
def app(session: Session) -> Aplicacao:
    return Aplicacao(session)


def intervalo(inicio: datetime, horas: float) -> TimeSlot:
    return TimeSlot(inicio, inicio + timedelta(hours=horas))


def solicitar_laboratorio(app: Aplicacao, inicio: datetime = QUINTA) -> RequestBookingCommand:
    return RequestBookingCommand(
        space_code="LAB-01",
        requester_id=SOLICITANTE,
        slot=intervalo(inicio, 2),
        purpose="Aula prática de Redes de Computadores",
        attendees=25,
        now=AGORA,
    )


@pytest.fixture
def laboratorio(app: Aplicacao) -> None:
    app.cadastrar.execute(
        RegisterSpaceCommand(
            code="LAB-01", name="Laboratório de Redes", kind=SpaceKind.LAB, capacity=30
        )
    )


# --- o fluxo inteiro ---------------------------------------------------------------------------


@pytest.mark.usefixtures("laboratorio")
def test_cadastrar_solicitar_e_aprovar_contra_o_banco(app: Aplicacao) -> None:
    """UC-01 → UC-04 → UC-05, cada passo lendo o que o anterior gravou."""
    assert [e.code for e in app.listar.execute(ListSpacesQuery())] == ["LAB-01"]

    criada = app.solicitar.execute(solicitar_laboratorio(app))
    assert criada.status is BookingStatus.PENDING  # laboratório exige aval — RN-09

    aprovada = app.aprovar.execute(
        ApproveBookingCommand(booking_id=criada.id, actor=GESTOR, now=DECISAO)
    )
    assert (aprovada.status, aprovada.decided_by) == (BookingStatus.APPROVED, GESTOR.user_id)


@pytest.mark.usefixtures("laboratorio")
def test_a_reserva_aprovada_continua_aprovada_numa_sessao_nova(
    app: Aplicacao, session: Session, engine: Engine
) -> None:
    """A prova de que `update` chegou ao disco: fecha tudo, reabre e o estado é o novo."""
    criada = app.solicitar.execute(solicitar_laboratorio(app))
    app.aprovar.execute(ApproveBookingCommand(booking_id=criada.id, actor=GESTOR, now=DECISAO))
    session.commit()
    session.close()

    with session_factory(engine)() as outra:
        relida = SqlAlchemyBookingRepository(outra).find_by_id(criada.id)
        assert relida is not None
        assert relida.status is BookingStatus.APPROVED


@pytest.mark.usefixtures("laboratorio")
def test_o_conflito_de_horario_e_detectado_atraves_do_banco(app: Aplicacao) -> None:
    """RN-01 pela consulta SQL — a mesma regra que os testes unitários exercitam em memória."""
    app.solicitar.execute(solicitar_laboratorio(app))

    with pytest.raises(ScheduleConflict):
        app.solicitar.execute(solicitar_laboratorio(app))


@pytest.mark.usefixtures("laboratorio")
def test_cancelar_libera_o_horario_e_a_nova_solicitacao_passa(app: Aplicacao) -> None:
    """UC-07 e depois UC-04 no mesmo intervalo: o ciclo completo da RN-01."""
    criada = app.solicitar.execute(solicitar_laboratorio(app))
    app.cancelar.execute(CancelBookingCommand(booking_id=criada.id, actor=DONO, now=DECISAO))

    outra = app.solicitar.execute(solicitar_laboratorio(app))
    assert outra.id != criada.id


@pytest.mark.usefixtures("laboratorio")
def test_a_agenda_do_dia_vem_do_banco(app: Aplicacao) -> None:
    """UC-03 — e em ordem cronológica, como a task 07 decidiu."""
    tarde = app.solicitar.execute(solicitar_laboratorio(app, QUINTA))
    manha = app.solicitar.execute(solicitar_laboratorio(app, QUINTA - timedelta(hours=6)))

    agenda = app.consultar.execute(
        CheckAvailabilityQuery(space_code="LAB-01", day=date(2026, 8, 20))
    )
    assert [r.id for r in agenda] == [manha.id, tarde.id]


# --- o Observer, ligado ------------------------------------------------------------------------


@pytest.mark.usefixtures("laboratorio")
def test_a_caixa_de_entrada_acumula_o_que_aconteceu(app: Aplicacao) -> None:
    """A evidência do padrão Observer que a defesa mostra em captura de tela: duas operações, duas
    notificações, na ordem em que ocorreram."""
    criada = app.solicitar.execute(solicitar_laboratorio(app))
    app.aprovar.execute(ApproveBookingCommand(booking_id=criada.id, actor=GESTOR, now=DECISAO))

    mensagens = [n.message for n in app.inbox.all()]
    assert len(mensagens) == 2
    assert "solicitada" in mensagens[0]
    assert "aprovada" in mensagens[1]
    assert all("LAB-01" in m for m in mensagens)
