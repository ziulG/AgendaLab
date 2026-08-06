"""UC-03 — consultar a agenda de um espaço num dia.

O caso de uso responde "o que já está ocupado", e é o cliente quem lê nisso as faixas livres. Duas
coisas ele acrescenta ao que o repositório entrega: traduz o espaço ausente em `SpaceNotFound` — o
contrato devolve `None`, e virar erro é responsabilidade de quem orquestra — e devolve a lista em
ordem cronológica, porque uma agenda fora de ordem não serve para procurar horário.

O que **não** aparece na agenda é regra do domínio, não daqui: reservas canceladas e rejeitadas
saem do caminho ainda no repositório, pela RN-01.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from agendalab.application.dto import CheckAvailabilityQuery
from agendalab.application.use_cases.check_availability import CheckAvailability
from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.domain.errors import SpaceNotFound
from agendalab.domain.value_objects.time_slot import TimeSlot
from tests.doubles.in_memory_repositories import (
    InMemoryBookingRepository,
    InMemorySpaceRepository,
)

LAB = "LAB-01"
OUTRO_ESPACO = "LAB-02"

QUINTA = date(2026, 8, 20)
SEXTA = date(2026, 8, 21)


def intervalo(dia: date, inicio: float, fim: float) -> TimeSlot:
    meia_noite = datetime.combine(dia, datetime.min.time())
    return TimeSlot(meia_noite + timedelta(hours=inicio), meia_noite + timedelta(hours=fim))


def espaco(code: str = LAB, active: bool = True) -> Space:
    return Space(code=code, name=f"Espaço {code}", kind=SpaceKind.LAB, capacity=30, active=active)


def reserva(
    slot: TimeSlot,
    *,
    space_code: str = LAB,
    status: BookingStatus = BookingStatus.APPROVED,
) -> Booking:
    return Booking(
        id=uuid4(),
        space_code=space_code,
        requester_id="2019001234",
        slot=slot,
        purpose="Aula prática de Redes de Computadores",
        attendees=25,
        status=status,
        created_at=datetime(2026, 8, 5, 9, 0),
    )


def caso_de_uso(espacos: list[Space], reservas: list[Booking]) -> CheckAvailability:
    spaces = InMemorySpaceRepository()
    for e in espacos:
        spaces.add(e)
    bookings = InMemoryBookingRepository()
    for r in reservas:
        bookings.add(r)
    return CheckAvailability(spaces, bookings)


def inicios(reservas: list[Booking]) -> list[datetime]:
    return [r.slot.start_at for r in reservas]


# --- espaço inexistente ------------------------------------------------------------------------


def test_agenda_de_espaco_inexistente_e_recusada() -> None:
    """O repositório devolve `None`; traduzir isso em erro é do caso de uso."""
    consultar = caso_de_uso([espaco(LAB)], [])
    with pytest.raises(SpaceNotFound, match="NAO-EXISTE"):
        consultar.execute(CheckAvailabilityQuery(space_code="NAO-EXISTE", day=QUINTA))


def test_a_recusa_vem_antes_de_qualquer_consulta_de_agenda() -> None:
    """Mesmo havendo reservas com aquele código, sem espaço cadastrado a resposta é `SpaceNotFound`."""
    consultar = caso_de_uso([], [reserva(intervalo(QUINTA, 14, 16))])
    with pytest.raises(SpaceNotFound):
        consultar.execute(CheckAvailabilityQuery(space_code=LAB, day=QUINTA))


# --- o que a agenda devolve --------------------------------------------------------------------


def test_dia_sem_reserva_devolve_agenda_vazia() -> None:
    """Espaço existente e livre: lista vazia, não erro."""
    consultar = caso_de_uso([espaco(LAB)], [])
    assert consultar.execute(CheckAvailabilityQuery(space_code=LAB, day=QUINTA)) == []


@pytest.mark.parametrize("status", [BookingStatus.PENDING, BookingStatus.APPROVED])
def test_reservas_ativas_aparecem_na_agenda(status: BookingStatus) -> None:
    """RN-01 — pendente e aprovada ocupam o horário, e as duas precisam ser visíveis."""
    ocupada = reserva(intervalo(QUINTA, 14, 16), status=status)
    consultar = caso_de_uso([espaco(LAB)], [ocupada])
    assert consultar.execute(CheckAvailabilityQuery(space_code=LAB, day=QUINTA)) == [ocupada]


@pytest.mark.parametrize("status", [BookingStatus.CANCELLED, BookingStatus.REJECTED])
def test_reservas_encerradas_nao_aparecem_na_agenda(status: BookingStatus) -> None:
    """Uma reserva cancelada ou rejeitada libera o horário — ela não ocupa mais nada."""
    consultar = caso_de_uso([espaco(LAB)], [reserva(intervalo(QUINTA, 14, 16), status=status)])
    assert consultar.execute(CheckAvailabilityQuery(space_code=LAB, day=QUINTA)) == []


def test_agenda_ignora_reservas_de_outro_espaco() -> None:
    vizinha = reserva(intervalo(QUINTA, 14, 16), space_code=OUTRO_ESPACO)
    consultar = caso_de_uso([espaco(LAB), espaco(OUTRO_ESPACO)], [vizinha])
    assert consultar.execute(CheckAvailabilityQuery(space_code=LAB, day=QUINTA)) == []


def test_agenda_ignora_reservas_de_outro_dia() -> None:
    consultar = caso_de_uso([espaco(LAB)], [reserva(intervalo(SEXTA, 14, 16))])
    assert consultar.execute(CheckAvailabilityQuery(space_code=LAB, day=QUINTA)) == []


def test_reserva_que_atravessa_a_meia_noite_aparece_nos_dois_dias() -> None:
    """Das 22h de quinta às 2h de sexta ocupa faixa dos dois dias, e some da agenda de nenhum."""
    virada = reserva(intervalo(QUINTA, 22, 26))
    consultar = caso_de_uso([espaco(LAB)], [virada])
    assert consultar.execute(CheckAvailabilityQuery(space_code=LAB, day=QUINTA)) == [virada]
    assert consultar.execute(CheckAvailabilityQuery(space_code=LAB, day=SEXTA)) == [virada]


def test_espaco_inativo_continua_com_agenda_consultavel() -> None:
    """A RN-05 impede **criar** reserva em espaço inativo; consultar o que já existe é livre."""
    ocupada = reserva(intervalo(QUINTA, 14, 16))
    consultar = caso_de_uso([espaco(LAB, active=False)], [ocupada])
    assert consultar.execute(CheckAvailabilityQuery(space_code=LAB, day=QUINTA)) == [ocupada]


# --- ordem cronológica -------------------------------------------------------------------------


def test_agenda_sai_em_ordem_cronologica() -> None:
    """Inseridas fora de ordem de propósito: quem procura horário livre lê a agenda de cima."""
    tarde = reserva(intervalo(QUINTA, 14, 16))
    manha = reserva(intervalo(QUINTA, 8, 10))
    fim_do_dia = reserva(intervalo(QUINTA, 18, 20))
    consultar = caso_de_uso([espaco(LAB)], [tarde, fim_do_dia, manha])
    agenda = consultar.execute(CheckAvailabilityQuery(space_code=LAB, day=QUINTA))
    assert agenda == [manha, tarde, fim_do_dia]


def test_reservas_que_comecam_juntas_nao_quebram_a_ordenacao() -> None:
    """Empate no início é possível entre espaços diferentes; aqui só não pode levantar erro.

    `Booking` não é ordenável, então uma ordenação que caísse no desempate por comparação de
    objetos falharia com `TypeError`.
    """
    curta = reserva(intervalo(QUINTA, 14, 15))
    longa = reserva(intervalo(QUINTA, 14, 18))
    consultar = caso_de_uso([espaco(LAB)], [curta, longa])
    agenda = consultar.execute(CheckAvailabilityQuery(space_code=LAB, day=QUINTA))
    assert inicios(agenda) == [datetime(2026, 8, 20, 14, 0)] * 2
