"""UC-06 — rejeitar reserva.

O mais magro dos três: carrega, chama `reject`, persiste, publica. Nem a RN-14 é verificada aqui —
o motivo vazio é recusado pelo próprio estado, antes de qualquer mudança. Os testes de motivo vazio
existem para provar exatamente isso: que o caso de uso repassa e não reimplementa.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from agendalab.application.dto import RejectBookingCommand
from agendalab.application.use_cases.reject_booking import RejectBooking
from agendalab.domain.actor import Actor, Role
from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.errors import (
    BookingNotFound,
    DomainError,
    InvalidStateTransition,
    MissingRejectionReason,
)
from agendalab.domain.events.booking_events import BookingRejected
from agendalab.domain.events.publisher import EventPublisher
from agendalab.domain.value_objects.time_slot import TimeSlot
from tests.doubles.spy_observer import SpyObserver
from tests.doubles.tracking_booking_repository import TrackingBookingRepository

SOLICITANTE = "2019001234"
GESTOR = Actor(user_id="1998007766", role=Role.MANAGER)

CRIACAO = datetime(2026, 8, 5, 9, 0)
DECISAO = datetime(2026, 8, 6, 10, 30)
QUINTA = datetime(2026, 8, 20, 14, 0)

ESPACO = "L-01"
MOTIVO = "O laboratório estará em manutenção preventiva nesta data."

TERMINAIS = [BookingStatus.APPROVED, BookingStatus.REJECTED, BookingStatus.CANCELLED]
MOTIVOS_VAZIOS = ["", "   ", "\t\n"]


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


def comando(booking_id: UUID, *, reason: str = MOTIVO) -> RejectBookingCommand:
    return RejectBookingCommand(
        booking_id=booking_id, actor=GESTOR, reason=reason, now=DECISAO
    )


class Cenario:
    def __init__(self, *reservas: Booking) -> None:
        self.bookings = TrackingBookingRepository()
        for existente in reservas:
            self.bookings.add(existente)

        self.espiao = SpyObserver()
        publicador = EventPublisher()
        publicador.subscribe(self.espiao)

        self.rejeitar = RejectBooking(self.bookings, publicador)


# --- a reserva precisa existir -----------------------------------------------------------------


def test_rejeitar_reserva_inexistente_e_recusado() -> None:
    with pytest.raises(BookingNotFound):
        Cenario().rejeitar.execute(comando(uuid4()))


# --- caminho feliz -----------------------------------------------------------------------------


def test_reserva_pendente_e_rejeitada() -> None:
    pendente = reserva()
    rejeitada = Cenario(pendente).rejeitar.execute(comando(pendente.id))
    assert rejeitada.status is BookingStatus.REJECTED


def test_a_rejeicao_guarda_o_motivo() -> None:
    """Invariante da §4.3: uma reserva `REJECTED` sempre tem `rejection_reason` preenchido."""
    pendente = reserva()
    rejeitada = Cenario(pendente).rejeitar.execute(comando(pendente.id))
    assert rejeitada.rejection_reason == MOTIVO


def test_a_rejeicao_registra_quem_decidiu_e_quando() -> None:
    pendente = reserva()
    rejeitada = Cenario(pendente).rejeitar.execute(comando(pendente.id))
    assert (rejeitada.decided_by, rejeitada.decided_at) == (GESTOR.user_id, DECISAO)


def test_a_reserva_rejeitada_fica_persistida() -> None:
    pendente = reserva()
    c = Cenario(pendente)
    c.rejeitar.execute(comando(pendente.id))

    guardada = c.bookings.find_by_id(pendente.id)
    assert guardada is not None
    assert guardada.status is BookingStatus.REJECTED


def test_a_persistencia_e_solicitada_explicitamente_ao_repositorio() -> None:
    """A dupla em memória guarda a própria instância, então mutá-la basta e a falta de `update`
    passaria despercebida. A implementação da task 10 não tem essa propriedade."""
    pendente = reserva()
    c = Cenario(pendente)
    c.rejeitar.execute(comando(pendente.id))
    assert c.bookings.updated_ids == [pendente.id]


def test_a_reserva_rejeitada_libera_o_horario() -> None:
    """RN-01 — rejeitada não ocupa. O intervalo volta a ficar disponível."""
    pendente = reserva()
    c = Cenario(pendente)
    c.rejeitar.execute(comando(pendente.id))
    assert c.bookings.find_active_overlapping(ESPACO, pendente.slot) == []


# --- RN-14: o motivo é obrigatório --------------------------------------------------------------


@pytest.mark.parametrize("vazio", MOTIVOS_VAZIOS, ids=["vazio", "espacos", "quebras"])
def test_rejeitar_sem_motivo_e_recusado(vazio: str) -> None:
    """A verificação é do domínio. O caso de uso repassa o texto como recebeu."""
    pendente = reserva()
    with pytest.raises(MissingRejectionReason) as erro:
        Cenario(pendente).rejeitar.execute(comando(pendente.id, reason=vazio))
    assert erro.value.rule == "RN-14"


@pytest.mark.parametrize("vazio", MOTIVOS_VAZIOS, ids=["vazio", "espacos", "quebras"])
def test_a_reserva_continua_pendente_quando_falta_o_motivo(vazio: str) -> None:
    """RN-14 é verificada **antes** de transicionar: não existe rejeitada sem motivo, nem por um
    instante."""
    pendente = reserva()
    with pytest.raises(MissingRejectionReason):
        Cenario(pendente).rejeitar.execute(comando(pendente.id, reason=vazio))
    assert (pendente.status, pendente.rejection_reason, pendente.decided_by) == (
        BookingStatus.PENDING,
        None,
        None,
    )


# --- RN-13: as células ❌ da tabela da §5.5 ------------------------------------------------------


@pytest.mark.parametrize("status", TERMINAIS, ids=TERMINAIS)
def test_rejeitar_o_que_a_tabela_nao_permite_e_recusado(status: BookingStatus) -> None:
    fora_de_hora = reserva(status=status)
    with pytest.raises(InvalidStateTransition) as erro:
        Cenario(fora_de_hora).rejeitar.execute(comando(fora_de_hora.id))
    assert erro.value.rule == "RN-13"


@pytest.mark.parametrize("status", TERMINAIS, ids=TERMINAIS)
def test_a_reserva_recusada_pela_tabela_fica_intacta(status: BookingStatus) -> None:
    fora_de_hora = reserva(status=status)
    with pytest.raises(InvalidStateTransition):
        Cenario(fora_de_hora).rejeitar.execute(comando(fora_de_hora.id))
    assert (fora_de_hora.status, fora_de_hora.decided_by) == (status, None)


# --- RN-15: o evento ---------------------------------------------------------------------------


def test_a_rejeicao_publica_o_evento_correspondente() -> None:
    pendente = reserva()
    c = Cenario(pendente)
    c.rejeitar.execute(comando(pendente.id))

    evento = c.espiao.unico
    assert isinstance(evento, BookingRejected)
    assert (
        evento.booking_id,
        evento.space_code,
        evento.requester_id,
        evento.decided_by,
        evento.occurred_at,
    ) == (pendente.id, ESPACO, SOLICITANTE, GESTOR.user_id, DECISAO)


def test_o_evento_carrega_o_motivo_da_rejeicao() -> None:
    """É o que o solicitante precisa saber, e o notificador não vai consultar o banco para descobrir."""
    pendente = reserva()
    c = Cenario(pendente)
    c.rejeitar.execute(comando(pendente.id))

    evento = c.espiao.unico
    assert isinstance(evento, BookingRejected)
    assert evento.reason == MOTIVO


# --- o que acontece quando a rejeição é recusada -------------------------------------------------


def recusa_reserva_inexistente() -> tuple[Cenario, RejectBookingCommand]:
    return Cenario(), comando(uuid4())


def recusa_por_motivo_vazio() -> tuple[Cenario, RejectBookingCommand]:
    pendente = reserva()
    return Cenario(pendente), comando(pendente.id, reason="   ")


def recusa_pela_tabela_de_transicoes() -> tuple[Cenario, RejectBookingCommand]:
    cancelada = reserva(status=BookingStatus.CANCELLED)
    return Cenario(cancelada), comando(cancelada.id)


RECUSAS = [recusa_reserva_inexistente, recusa_por_motivo_vazio, recusa_pela_tabela_de_transicoes]
IDS_DAS_RECUSAS = [f.__name__.removeprefix("recusa_") for f in RECUSAS]

MontarRecusa = Callable[[], tuple[Cenario, RejectBookingCommand]]


@pytest.mark.parametrize("montar", RECUSAS, ids=IDS_DAS_RECUSAS)
def test_nenhum_evento_e_publicado_quando_a_rejeicao_e_recusada(montar: MontarRecusa) -> None:
    c, cmd = montar()
    with pytest.raises(DomainError):
        c.rejeitar.execute(cmd)
    assert c.espiao.recebidos == []


@pytest.mark.parametrize("montar", RECUSAS, ids=IDS_DAS_RECUSAS)
def test_nada_e_persistido_quando_a_rejeicao_e_recusada(montar: MontarRecusa) -> None:
    c, cmd = montar()
    with pytest.raises(DomainError):
        c.rejeitar.execute(cmd)
    assert c.bookings.updated_ids == []
