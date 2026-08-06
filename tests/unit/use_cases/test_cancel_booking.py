"""UC-07 — cancelar reserva.

O único dos três em que o ator não é necessariamente um gestor, e por isso o único que exercita a
metade da autorização que pertence ao domínio. A RN-12 — cancela o próprio solicitante ou qualquer
gestor — exige conhecer a reserva para responder "esta é sua?", e a borda HTTP não tem como fazê-lo
(ADR-0007). Quem responde é `_ensure_may_cancel`, dentro do estado; o caso de uso deixa o
`PermissionDenied` subir.

É também a única operação permitida em dois estados de origem — `PENDING` e `APPROVED` —, o que faz
dele o melhor lugar para verificar que o horário volta a ficar livre.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from agendalab.application.dto import CancelBookingCommand
from agendalab.application.use_cases.cancel_booking import CancelBooking
from agendalab.domain.actor import Actor, Role
from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.errors import (
    BookingNotFound,
    DomainError,
    InvalidStateTransition,
    PermissionDenied,
)
from agendalab.domain.events.booking_events import BookingCancelled
from agendalab.domain.events.publisher import EventPublisher
from agendalab.domain.value_objects.time_slot import TimeSlot
from tests.doubles.spy_observer import SpyObserver
from tests.doubles.tracking_booking_repository import TrackingBookingRepository

SOLICITANTE = "2019001234"

DONO = Actor(user_id=SOLICITANTE, role=Role.REQUESTER)
TERCEIRO = Actor(user_id="2020005678", role=Role.REQUESTER)
GESTOR = Actor(user_id="1998007766", role=Role.MANAGER)

CRIACAO = datetime(2026, 8, 5, 9, 0)
DECISAO = datetime(2026, 8, 6, 10, 30)
QUINTA = datetime(2026, 8, 20, 14, 0)

ESPACO = "L-01"

CANCELAVEIS = [BookingStatus.PENDING, BookingStatus.APPROVED]
TERMINAIS = [BookingStatus.REJECTED, BookingStatus.CANCELLED]


def reserva(*, status: BookingStatus = BookingStatus.PENDING) -> Booking:
    return Booking(
        id=uuid4(),
        space_code=ESPACO,
        requester_id=SOLICITANTE,
        slot=TimeSlot(QUINTA, QUINTA + timedelta(hours=2)),
        purpose="Aula prática de Redes de Computadores",
        attendees=25,
        status=status,
        created_at=CRIACAO,
    )


def comando(booking_id: UUID, *, actor: Actor = DONO) -> CancelBookingCommand:
    return CancelBookingCommand(booking_id=booking_id, actor=actor, now=DECISAO)


class Cenario:
    def __init__(self, *reservas: Booking) -> None:
        self.bookings = TrackingBookingRepository()
        for existente in reservas:
            self.bookings.add(existente)

        self.espiao = SpyObserver()
        publicador = EventPublisher()
        publicador.subscribe(self.espiao)

        self.cancelar = CancelBooking(self.bookings, publicador)


# --- a reserva precisa existir -----------------------------------------------------------------


def test_cancelar_reserva_inexistente_e_recusado() -> None:
    with pytest.raises(BookingNotFound):
        Cenario().cancelar.execute(comando(uuid4()))


# --- caminho feliz -----------------------------------------------------------------------------


@pytest.mark.parametrize("status", CANCELAVEIS, ids=CANCELAVEIS)
def test_reserva_ativa_e_cancelada(status: BookingStatus) -> None:
    """A única transição permitida em dois estados de origem — pendente e aprovada."""
    ativa = reserva(status=status)
    cancelada = Cenario(ativa).cancelar.execute(comando(ativa.id))
    assert cancelada.status is BookingStatus.CANCELLED


def test_o_cancelamento_registra_quem_decidiu_e_quando() -> None:
    ativa = reserva()
    cancelada = Cenario(ativa).cancelar.execute(comando(ativa.id))
    assert (cancelada.decided_by, cancelada.decided_at) == (DONO.user_id, DECISAO)


def test_a_reserva_cancelada_fica_persistida() -> None:
    ativa = reserva()
    c = Cenario(ativa)
    c.cancelar.execute(comando(ativa.id))

    guardada = c.bookings.find_by_id(ativa.id)
    assert guardada is not None
    assert guardada.status is BookingStatus.CANCELLED


def test_a_persistencia_e_solicitada_explicitamente_ao_repositorio() -> None:
    """Mutar a entidade basta contra a dupla, mas não contra a implementação da task 10 — e é por
    isso que a chamada a `update` precisa de teste próprio."""
    ativa = reserva()
    c = Cenario(ativa)
    c.cancelar.execute(comando(ativa.id))
    assert c.bookings.updated_ids == [ativa.id]


def test_o_cancelamento_libera_o_horario() -> None:
    """RN-01 — cancelada não ocupa, e o intervalo volta a ser solicitável na mesma hora."""
    ativa = reserva(status=BookingStatus.APPROVED)
    c = Cenario(ativa)
    assert c.bookings.find_active_overlapping(ESPACO, ativa.slot) == [ativa]

    c.cancelar.execute(comando(ativa.id))

    assert c.bookings.find_active_overlapping(ESPACO, ativa.slot) == []


# --- RN-12: quem pode cancelar ------------------------------------------------------------------


def test_o_proprio_solicitante_cancela_a_sua_reserva() -> None:
    ativa = reserva()
    cancelada = Cenario(ativa).cancelar.execute(comando(ativa.id, actor=DONO))
    assert cancelada.status is BookingStatus.CANCELLED


def test_o_gestor_cancela_reserva_de_qualquer_pessoa() -> None:
    ativa = reserva()
    cancelada = Cenario(ativa).cancelar.execute(comando(ativa.id, actor=GESTOR))
    assert (cancelada.status, cancelada.decided_by) == (
        BookingStatus.CANCELLED,
        GESTOR.user_id,
    )


def test_solicitante_nao_cancela_reserva_alheia() -> None:
    """A metade da autorização que é do domínio — a borda não sabe de quem é a reserva."""
    ativa = reserva()
    with pytest.raises(PermissionDenied) as erro:
        Cenario(ativa).cancelar.execute(comando(ativa.id, actor=TERCEIRO))
    assert erro.value.rule == "RN-12"


def test_a_reserva_fica_intacta_quando_o_cancelamento_nao_e_autorizado() -> None:
    ativa = reserva()
    with pytest.raises(PermissionDenied):
        Cenario(ativa).cancelar.execute(comando(ativa.id, actor=TERCEIRO))
    assert (ativa.status, ativa.decided_by, ativa.decided_at) == (
        BookingStatus.PENDING,
        None,
        None,
    )


# --- RN-13: as células ❌ da tabela da §5.5 ------------------------------------------------------


@pytest.mark.parametrize("status", TERMINAIS, ids=TERMINAIS)
def test_cancelar_reserva_em_estado_terminal_e_recusado(status: BookingStatus) -> None:
    """Rejeitada e cancelada são terminais: nada as tira de lá, nem um gestor."""
    encerrada = reserva(status=status)
    with pytest.raises(InvalidStateTransition) as erro:
        Cenario(encerrada).cancelar.execute(comando(encerrada.id, actor=GESTOR))
    assert erro.value.rule == "RN-13"


@pytest.mark.parametrize("status", TERMINAIS, ids=TERMINAIS)
def test_a_reserva_terminal_fica_intacta(status: BookingStatus) -> None:
    encerrada = reserva(status=status)
    with pytest.raises(InvalidStateTransition):
        Cenario(encerrada).cancelar.execute(comando(encerrada.id, actor=GESTOR))
    assert encerrada.status is status


# --- RN-15: o evento ---------------------------------------------------------------------------


def test_o_cancelamento_publica_o_evento_correspondente() -> None:
    ativa = reserva()
    c = Cenario(ativa)
    c.cancelar.execute(comando(ativa.id))

    evento = c.espiao.unico
    assert isinstance(evento, BookingCancelled)
    assert (
        evento.booking_id,
        evento.space_code,
        evento.requester_id,
        evento.decided_by,
        evento.occurred_at,
    ) == (ativa.id, ESPACO, SOLICITANTE, DONO.user_id, DECISAO)


def test_o_evento_registra_o_gestor_quando_foi_ele_quem_cancelou() -> None:
    """`requester_id` e `decided_by` são pessoas diferentes aqui — e o notificador precisa das duas."""
    ativa = reserva()
    c = Cenario(ativa)
    c.cancelar.execute(comando(ativa.id, actor=GESTOR))

    evento = c.espiao.unico
    assert isinstance(evento, BookingCancelled)
    assert (evento.requester_id, evento.decided_by) == (SOLICITANTE, GESTOR.user_id)


# --- o que acontece quando o cancelamento é recusado ---------------------------------------------


def recusa_reserva_inexistente() -> tuple[Cenario, CancelBookingCommand]:
    return Cenario(), comando(uuid4())


def recusa_por_falta_de_autorizacao() -> tuple[Cenario, CancelBookingCommand]:
    ativa = reserva()
    return Cenario(ativa), comando(ativa.id, actor=TERCEIRO)


def recusa_pela_tabela_de_transicoes() -> tuple[Cenario, CancelBookingCommand]:
    encerrada = reserva(status=BookingStatus.REJECTED)
    return Cenario(encerrada), comando(encerrada.id)


RECUSAS = [
    recusa_reserva_inexistente,
    recusa_por_falta_de_autorizacao,
    recusa_pela_tabela_de_transicoes,
]
IDS_DAS_RECUSAS = [f.__name__.removeprefix("recusa_") for f in RECUSAS]

MontarRecusa = Callable[[], tuple[Cenario, CancelBookingCommand]]


@pytest.mark.parametrize("montar", RECUSAS, ids=IDS_DAS_RECUSAS)
def test_nenhum_evento_e_publicado_quando_o_cancelamento_e_recusado(
    montar: MontarRecusa,
) -> None:
    c, cmd = montar()
    with pytest.raises(DomainError):
        c.cancelar.execute(cmd)
    assert c.espiao.recebidos == []


@pytest.mark.parametrize("montar", RECUSAS, ids=IDS_DAS_RECUSAS)
def test_nada_e_persistido_quando_o_cancelamento_e_recusado(montar: MontarRecusa) -> None:
    c, cmd = montar()
    with pytest.raises(DomainError):
        c.cancelar.execute(cmd)
    assert c.bookings.updated_ids == []
