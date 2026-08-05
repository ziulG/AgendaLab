"""`ManagedAccessPolicy` — laboratório (RN-07 e RN-09).

Laboratório tem equipamento caro e precisa de preparo: exige aval humano, aviso prévio de um dia
e sessões de no máximo quatro horas.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from agendalab.domain.entities.booking import BookingStatus
from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.domain.errors import PolicyViolation
from agendalab.domain.policies.booking_policy import BookingRequest, PolicyContext
from agendalab.domain.policies.managed_access import ManagedAccessPolicy
from agendalab.domain.value_objects.time_slot import TimeSlot

AGORA = datetime(2026, 8, 5, 9, 0)
LABORATORIO = Space(code="LAB-01", name="Laboratório de Redes", kind=SpaceKind.LAB, capacity=30)


def solicitacao(inicio: datetime, duracao: timedelta) -> BookingRequest:
    return BookingRequest(
        space_code=LABORATORIO.code,
        requester_id="2019001234",
        slot=TimeSlot(inicio, inicio + duracao),
        purpose="Aula prática de Redes de Computadores",
        attendees=25,
    )


CONTEXTO = PolicyContext(now=AGORA, space=LABORATORIO, requester_week_bookings=[])


def test_laboratorio_exige_decisao_do_gestor() -> None:
    """RN-07 e RN-09 — a reserva nasce pendente, esperando aval humano."""
    assert ManagedAccessPolicy().initial_status() is BookingStatus.PENDING


def test_solicitacao_dentro_das_regras_e_aceita() -> None:
    ManagedAccessPolicy().validate(
        solicitacao(AGORA + timedelta(days=3), timedelta(hours=2)), CONTEXTO
    )


# --- RN-09: antecedência mínima de 24h -------------------------------------------------------


def test_exatamente_vinte_e_quatro_horas_de_antecedencia_passa() -> None:
    """RN-09 — a fronteira: 24h de antecedência é suficiente."""
    ManagedAccessPolicy().validate(
        solicitacao(AGORA + timedelta(hours=24), timedelta(hours=2)), CONTEXTO
    )


def test_um_minuto_a_menos_de_antecedencia_recusa() -> None:
    """RN-09 — o outro lado da mesma fronteira."""
    with pytest.raises(PolicyViolation) as erro:
        ManagedAccessPolicy().validate(
            solicitacao(AGORA + timedelta(hours=23, minutes=59), timedelta(hours=2)), CONTEXTO
        )
    assert erro.value.rule == "RN-09"


def test_reserva_para_daqui_a_pouco_recusa() -> None:
    """RN-09 — laboratório não se reserva em cima da hora."""
    with pytest.raises(PolicyViolation):
        ManagedAccessPolicy().validate(
            solicitacao(AGORA + timedelta(hours=1), timedelta(hours=2)), CONTEXTO
        )


# --- RN-09: duração máxima de 4h -------------------------------------------------------------


def test_exatamente_quatro_horas_de_duracao_passa() -> None:
    """RN-09 — a fronteira: 4h é o máximo permitido, não o primeiro valor recusado."""
    ManagedAccessPolicy().validate(
        solicitacao(AGORA + timedelta(days=3), timedelta(hours=4)), CONTEXTO
    )


def test_quatro_horas_e_um_minuto_recusa() -> None:
    """RN-09 — o outro lado da mesma fronteira."""
    with pytest.raises(PolicyViolation) as erro:
        ManagedAccessPolicy().validate(
            solicitacao(AGORA + timedelta(days=3), timedelta(hours=4, minutes=1)), CONTEXTO
        )
    assert erro.value.rule == "RN-09"


def test_antecedencia_e_verificada_antes_da_duracao() -> None:
    """Uma solicitação que viola as duas recusa pela primeira — a ordem da §5.3."""
    with pytest.raises(PolicyViolation) as erro:
        ManagedAccessPolicy().validate(
            solicitacao(AGORA + timedelta(hours=1), timedelta(hours=8)), CONTEXTO
        )
    assert "antecedência" in erro.value.message
