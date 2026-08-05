"""`OpenAccessPolicy` — sala de aula (RN-07 e RN-08).

Sala de aula é recurso abundante e de baixo risco: aprovação automática, sem antecedência mínima.
A única barreira é o teto de uso justo — 8 horas por solicitante na semana ISO.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.domain.errors import PolicyViolation
from agendalab.domain.policies.booking_policy import BookingRequest, PolicyContext
from agendalab.domain.policies.open_access import OpenAccessPolicy
from agendalab.domain.value_objects.time_slot import TimeSlot

SOLICITANTE = "2019001234"
AGORA = datetime(2026, 8, 5, 9, 0)

# 20/08/2026 é uma quinta-feira: semana ISO 34, de segunda 17/08 a domingo 23/08.
SEGUNDA = datetime(2026, 8, 17, 8, 0)
QUINTA = datetime(2026, 8, 20, 14, 0)
# 24/08 é a segunda seguinte — semana ISO 35.
SEMANA_SEGUINTE = datetime(2026, 8, 24, 8, 0)

SALA = Space(code="SALA-01", name="Sala 101", kind=SpaceKind.CLASSROOM, capacity=40)


def intervalo(inicio: datetime, horas: int) -> TimeSlot:
    return TimeSlot(inicio, inicio + timedelta(hours=horas))


def bloco_de_vinte_minutos(inicio: datetime) -> TimeSlot:
    return TimeSlot(inicio, inicio + timedelta(minutes=20))


def solicitacao(slot: TimeSlot) -> BookingRequest:
    return BookingRequest(
        space_code=SALA.code,
        requester_id=SOLICITANTE,
        slot=slot,
        purpose="Monitoria de Cálculo I",
        attendees=15,
    )


def reserva(slot: TimeSlot, status: BookingStatus = BookingStatus.APPROVED) -> Booking:
    return Booking(
        id=uuid4(),
        space_code=SALA.code,
        requester_id=SOLICITANTE,
        slot=slot,
        purpose="Monitoria de Cálculo I",
        attendees=15,
        status=status,
        created_at=AGORA,
    )


def contexto(*reservas_da_semana: Booking) -> PolicyContext:
    return PolicyContext(now=AGORA, space=SALA, requester_week_bookings=list(reservas_da_semana))


def test_sala_de_aula_tem_aprovacao_automatica() -> None:
    """RN-07 e RN-08 — a política define o status inicial, e aqui não há gestor no caminho."""
    assert OpenAccessPolicy().initial_status() is BookingStatus.APPROVED


def test_primeira_reserva_da_semana_e_aceita() -> None:
    OpenAccessPolicy().validate(solicitacao(intervalo(QUINTA, 2)), contexto())


# --- RN-08: a fronteira das 8 horas ----------------------------------------------------------


def test_exatamente_oito_horas_na_semana_passa() -> None:
    """RN-08 — o teto é 8h; passar de 8h é que recusa."""
    politica = OpenAccessPolicy()
    ja_reservadas = reserva(intervalo(SEGUNDA, 6))
    politica.validate(solicitacao(intervalo(QUINTA, 2)), contexto(ja_reservadas))


def test_oito_horas_e_um_minuto_na_semana_recusa() -> None:
    """RN-08 — o outro lado da mesma fronteira."""
    politica = OpenAccessPolicy()
    ja_reservadas = reserva(intervalo(SEGUNDA, 6))
    with pytest.raises(PolicyViolation) as erro:
        politica.validate(solicitacao(TimeSlot(QUINTA, QUINTA + timedelta(hours=2, minutes=1))),
                          contexto(ja_reservadas))
    assert erro.value.rule == "RN-08"


def test_a_reserva_em_analise_conta_no_total() -> None:
    """RN-08 — "incluindo a reserva em análise": 8h já reservadas e mais 1h estoura."""
    politica = OpenAccessPolicy()
    with pytest.raises(PolicyViolation):
        politica.validate(solicitacao(intervalo(QUINTA, 1)), contexto(reserva(intervalo(SEGUNDA, 8))))


def test_uma_unica_reserva_acima_do_teto_recusa() -> None:
    """RN-08 — sem histórico algum, 9 horas de uma vez já passam do teto."""
    with pytest.raises(PolicyViolation):
        OpenAccessPolicy().validate(solicitacao(intervalo(QUINTA, 9)), contexto())


def test_horas_quebradas_somam_sem_erro_de_arredondamento() -> None:
    """RN-08 — 24 blocos de 20 minutos dão exatamente 8h, e exatamente 8h passa.

    Vinte minutos é 0,333... hora: somar 24 deles em ponto flutuante pode ultrapassar 8 por um
    fio e recusar uma solicitação que a regra aceita. A soma é feita em `timedelta`, que é exato.
    """
    politica = OpenAccessPolicy()
    blocos = [
        reserva(bloco_de_vinte_minutos(SEGUNDA + timedelta(minutes=20 * i))) for i in range(23)
    ]
    politica.validate(solicitacao(bloco_de_vinte_minutos(QUINTA)), contexto(*blocos))


# --- RN-08: o que não entra na conta ---------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [BookingStatus.REJECTED, BookingStatus.CANCELLED],
    ids=lambda s: str(s),
)
def test_reserva_inativa_nao_ocupa_o_teto(status: BookingStatus) -> None:
    """RN-08 — só reservas ativas contam. Uma reserva cancelada devolve as horas."""
    politica = OpenAccessPolicy()
    politica.validate(solicitacao(intervalo(QUINTA, 8)), contexto(reserva(intervalo(SEGUNDA, 6), status)))


@pytest.mark.parametrize(
    "status",
    [BookingStatus.PENDING, BookingStatus.APPROVED],
    ids=lambda s: str(s),
)
def test_reserva_ativa_ocupa_o_teto(status: BookingStatus) -> None:
    """RN-08 — ativa é `PENDING` ou `APPROVED`; ambas ocupam."""
    politica = OpenAccessPolicy()
    with pytest.raises(PolicyViolation):
        politica.validate(solicitacao(intervalo(QUINTA, 8)), contexto(reserva(intervalo(SEGUNDA, 1), status)))


def test_reserva_de_outra_semana_nao_ocupa_o_teto() -> None:
    """RN-08 — o teto é semanal, e a semana é a ISO da reserva solicitada."""
    politica = OpenAccessPolicy()
    politica.validate(
        solicitacao(intervalo(QUINTA, 8)), contexto(reserva(intervalo(SEMANA_SEGUINTE, 6)))
    )


def test_o_teto_segue_a_semana_da_reserva_e_nao_a_de_hoje() -> None:
    """RN-08 — `now` é 05/08 e a reserva é de 20/08: a semana que conta é a da reserva."""
    politica = OpenAccessPolicy()
    with pytest.raises(PolicyViolation):
        politica.validate(solicitacao(intervalo(QUINTA, 3)), contexto(reserva(intervalo(SEGUNDA, 6))))
