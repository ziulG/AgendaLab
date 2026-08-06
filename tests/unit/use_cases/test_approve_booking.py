"""UC-05 — aprovar reserva.

O caso de uso é magro por construção: carrega, revalida o conflito, chama `approve` e persiste.
Quem decide se a transição é legítima é o estado atual da reserva, e por isso os testes das células
❌ da §5.5 aparecem aqui — não para verificar de novo o que a task 03 já cobriu, mas para provar que
o caso de uso **deixa o domínio decidir** em vez de responder por conta própria.

O passo que só existe aqui é a revalidação do conflito. Entre a solicitação e a decisão do gestor
pode ter passado uma semana, e outra reserva pode ter sido aprovada no mesmo intervalo.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from agendalab.application.dto import ApproveBookingCommand
from agendalab.application.use_cases.approve_booking import ApproveBooking
from agendalab.domain.actor import Actor, Role
from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.errors import (
    BookingNotFound,
    DomainError,
    InvalidStateTransition,
    ScheduleConflict,
)
from agendalab.domain.events.booking_events import BookingApproved
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
OUTRO_ESPACO = "L-02"

TERMINAIS = [BookingStatus.APPROVED, BookingStatus.REJECTED, BookingStatus.CANCELLED]


def intervalo(inicio: datetime, horas: float) -> TimeSlot:
    return TimeSlot(inicio, inicio + timedelta(hours=horas))


def reserva(
    *,
    slot: TimeSlot | None = None,
    space_code: str = ESPACO,
    requester_id: str = SOLICITANTE,
    status: BookingStatus = BookingStatus.PENDING,
) -> Booking:
    return Booking(
        id=uuid4(),
        space_code=space_code,
        requester_id=requester_id,
        slot=slot if slot is not None else intervalo(QUINTA, 2),
        purpose="Aula prática de Redes de Computadores",
        attendees=25,
        status=status,
        created_at=CRIACAO,
    )


def comando(booking_id: UUID, *, actor: Actor = GESTOR) -> ApproveBookingCommand:
    return ApproveBookingCommand(booking_id=booking_id, actor=actor, now=DECISAO)


class Cenario:
    def __init__(self, *reservas: Booking) -> None:
        self.bookings = TrackingBookingRepository()
        for existente in reservas:
            self.bookings.add(existente)

        self.espiao = SpyObserver()
        publicador = EventPublisher()
        publicador.subscribe(self.espiao)

        self.aprovar = ApproveBooking(self.bookings, publicador)


# --- a reserva precisa existir -----------------------------------------------------------------


def test_aprovar_reserva_inexistente_e_recusado() -> None:
    """O repositório devolve `None`; traduzir em erro é do caso de uso."""
    with pytest.raises(BookingNotFound):
        Cenario().aprovar.execute(comando(uuid4()))


# --- caminho feliz -----------------------------------------------------------------------------


def test_reserva_pendente_e_aprovada() -> None:
    pendente = reserva()
    aprovada = Cenario(pendente).aprovar.execute(comando(pendente.id))
    assert aprovada.status is BookingStatus.APPROVED


def test_a_aprovacao_registra_quem_decidiu_e_quando() -> None:
    """A trilha de decisão da §4.1. O instante vem do comando, não de um relógio."""
    pendente = reserva()
    aprovada = Cenario(pendente).aprovar.execute(comando(pendente.id))
    assert (aprovada.decided_by, aprovada.decided_at) == (GESTOR.user_id, DECISAO)


def test_a_reserva_aprovada_fica_persistida() -> None:
    pendente = reserva()
    c = Cenario(pendente)
    c.aprovar.execute(comando(pendente.id))

    guardada = c.bookings.find_by_id(pendente.id)
    assert guardada is not None
    assert guardada.status is BookingStatus.APPROVED


def test_a_persistencia_e_solicitada_explicitamente_ao_repositorio() -> None:
    """Contra a dupla em memória, mutar a entidade já a deixa mutada dentro do repositório — o que
    torna a ausência de `update` invisível. Contra o SQLAlchemy da task 10, que converte a entidade
    em modelo separado, a mesma ausência faria a aprovação nunca chegar ao banco."""
    pendente = reserva()
    c = Cenario(pendente)
    c.aprovar.execute(comando(pendente.id))
    assert c.bookings.updated_ids == [pendente.id]


def test_a_reserva_aprovada_nao_ganha_motivo_de_rejeicao() -> None:
    pendente = reserva()
    aprovada = Cenario(pendente).aprovar.execute(comando(pendente.id))
    assert aprovada.rejection_reason is None


# --- RN-13: as células ❌ da tabela da §5.5 ------------------------------------------------------


@pytest.mark.parametrize("status", TERMINAIS, ids=TERMINAIS)
def test_aprovar_o_que_a_tabela_nao_permite_e_recusado(status: BookingStatus) -> None:
    """Só `PENDING` aceita `approve`. Quem responde isso é o estado, não um `if` aqui."""
    fora_de_hora = reserva(status=status)
    with pytest.raises(InvalidStateTransition) as erro:
        Cenario(fora_de_hora).aprovar.execute(comando(fora_de_hora.id))
    assert erro.value.rule == "RN-13"


@pytest.mark.parametrize("status", TERMINAIS, ids=TERMINAIS)
def test_a_reserva_recusada_pela_tabela_fica_intacta(status: BookingStatus) -> None:
    fora_de_hora = reserva(status=status)
    with pytest.raises(InvalidStateTransition):
        Cenario(fora_de_hora).aprovar.execute(comando(fora_de_hora.id))
    assert (fora_de_hora.status, fora_de_hora.decided_by) == (status, None)


# --- RN-01: a revalidação do conflito ----------------------------------------------------------
#
# O passo que existe só neste caso de uso. Sem ele, duas reservas pendentes no mesmo horário
# poderiam ser aprovadas em sequência, e o sistema teria autorizado uma reserva dupla.


def test_conflito_surgido_no_meio_tempo_impede_a_aprovacao() -> None:
    pendente = reserva(slot=intervalo(QUINTA, 2))
    concorrente = reserva(slot=intervalo(QUINTA, 2), status=BookingStatus.APPROVED)

    with pytest.raises(ScheduleConflict) as erro:
        Cenario(pendente, concorrente).aprovar.execute(comando(pendente.id))
    assert erro.value.rule == "RN-01"


def test_a_reserva_permanece_pendente_quando_o_conflito_impede() -> None:
    """A recusa é total: nem status, nem trilha de decisão."""
    pendente = reserva(slot=intervalo(QUINTA, 2))
    concorrente = reserva(slot=intervalo(QUINTA, 2), status=BookingStatus.APPROVED)
    c = Cenario(pendente, concorrente)

    with pytest.raises(ScheduleConflict):
        c.aprovar.execute(comando(pendente.id))

    assert (pendente.status, pendente.decided_by, pendente.decided_at) == (
        BookingStatus.PENDING,
        None,
        None,
    )


def test_a_propria_reserva_nao_conflita_consigo_mesma() -> None:
    """A reserva sendo aprovada está `PENDING`, logo é ativa e aparece na própria consulta.

    Um caso de uso que esquecesse de descartá-la pelo `id` recusaria toda aprovação do sistema.
    """
    sozinha = reserva()
    aprovada = Cenario(sozinha).aprovar.execute(comando(sozinha.id))
    assert aprovada.status is BookingStatus.APPROVED


def test_reserva_que_apenas_toca_a_borda_nao_impede_a_aprovacao() -> None:
    """RN-02 — quem começa às 16h não conflita com quem termina às 16h."""
    pendente = reserva(slot=intervalo(QUINTA, 2))
    vizinha = reserva(
        slot=intervalo(QUINTA + timedelta(hours=2), 2), status=BookingStatus.APPROVED
    )
    aprovada = Cenario(pendente, vizinha).aprovar.execute(comando(pendente.id))
    assert aprovada.status is BookingStatus.APPROVED


def test_conflito_em_outro_espaco_nao_impede_a_aprovacao() -> None:
    pendente = reserva(slot=intervalo(QUINTA, 2), space_code=ESPACO)
    alheia = reserva(
        slot=intervalo(QUINTA, 2), space_code=OUTRO_ESPACO, status=BookingStatus.APPROVED
    )
    aprovada = Cenario(pendente, alheia).aprovar.execute(comando(pendente.id))
    assert aprovada.status is BookingStatus.APPROVED


@pytest.mark.parametrize(
    "status", [BookingStatus.CANCELLED, BookingStatus.REJECTED], ids=["cancelada", "rejeitada"]
)
def test_reserva_encerrada_no_mesmo_horario_nao_impede_a_aprovacao(
    status: BookingStatus,
) -> None:
    """RN-01 — encerrada não ocupa. O horário está livre para quem esperava."""
    pendente = reserva(slot=intervalo(QUINTA, 2))
    encerrada = reserva(slot=intervalo(QUINTA, 2), status=status)
    aprovada = Cenario(pendente, encerrada).aprovar.execute(comando(pendente.id))
    assert aprovada.status is BookingStatus.APPROVED


# --- RN-15: o evento ---------------------------------------------------------------------------


def test_a_aprovacao_publica_o_evento_correspondente() -> None:
    pendente = reserva()
    c = Cenario(pendente)
    c.aprovar.execute(comando(pendente.id))

    evento = c.espiao.unico
    assert isinstance(evento, BookingApproved)
    assert (
        evento.booking_id,
        evento.space_code,
        evento.requester_id,
        evento.decided_by,
        evento.occurred_at,
    ) == (pendente.id, ESPACO, SOLICITANTE, GESTOR.user_id, DECISAO)


# --- o que acontece quando a aprovação é recusada -----------------------------------------------


def recusa_reserva_inexistente() -> tuple[Cenario, ApproveBookingCommand]:
    return Cenario(), comando(uuid4())


def recusa_pela_tabela_de_transicoes() -> tuple[Cenario, ApproveBookingCommand]:
    ja_aprovada = reserva(status=BookingStatus.APPROVED)
    return Cenario(ja_aprovada), comando(ja_aprovada.id)


def recusa_por_conflito_de_horario() -> tuple[Cenario, ApproveBookingCommand]:
    pendente = reserva(slot=intervalo(QUINTA, 2))
    concorrente = reserva(slot=intervalo(QUINTA, 2), status=BookingStatus.APPROVED)
    return Cenario(pendente, concorrente), comando(pendente.id)


RECUSAS = [
    recusa_reserva_inexistente,
    recusa_pela_tabela_de_transicoes,
    recusa_por_conflito_de_horario,
]
IDS_DAS_RECUSAS = [f.__name__.removeprefix("recusa_") for f in RECUSAS]

MontarRecusa = Callable[[], tuple[Cenario, ApproveBookingCommand]]


@pytest.mark.parametrize("montar", RECUSAS, ids=IDS_DAS_RECUSAS)
def test_nenhum_evento_e_publicado_quando_a_aprovacao_e_recusada(montar: MontarRecusa) -> None:
    """RN-15 — o evento registra um fato consumado. Uma aprovação recusada não é fato nenhum."""
    c, cmd = montar()
    with pytest.raises(DomainError):
        c.aprovar.execute(cmd)
    assert c.espiao.recebidos == []


@pytest.mark.parametrize("montar", RECUSAS, ids=IDS_DAS_RECUSAS)
def test_nada_e_persistido_quando_a_aprovacao_e_recusada(montar: MontarRecusa) -> None:
    c, cmd = montar()
    with pytest.raises(DomainError):
        c.aprovar.execute(cmd)
    assert c.bookings.updated_ids == []
