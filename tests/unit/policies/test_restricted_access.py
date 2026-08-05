"""`RestrictedAccessPolicy` — auditório (RN-07 e RN-10).

Auditório é recurso único no campus: só se justifica para eventos de porte, com três dias de
antecedência para a logística.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from agendalab.domain.entities.booking import BookingStatus
from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.domain.errors import PolicyViolation
from agendalab.domain.policies.booking_policy import BookingRequest, PolicyContext
from agendalab.domain.policies.restricted_access import RestrictedAccessPolicy
from agendalab.domain.value_objects.time_slot import TimeSlot

AGORA = datetime(2026, 8, 5, 9, 0)
AUDITORIO = Space(
    code="AUD-01", name="Auditório Central", kind=SpaceKind.AUDITORIUM, capacity=200
)


def solicitacao(inicio: datetime, participantes: int) -> BookingRequest:
    return BookingRequest(
        space_code=AUDITORIO.code,
        requester_id="2019001234",
        slot=TimeSlot(inicio, inicio + timedelta(hours=3)),
        purpose="Semana de Ciência da Computação",
        attendees=participantes,
    )


CONTEXTO = PolicyContext(now=AGORA, space=AUDITORIO, requester_week_bookings=[])


def test_auditorio_exige_decisao_do_gestor() -> None:
    """RN-07 e RN-10."""
    assert RestrictedAccessPolicy().initial_status() is BookingStatus.PENDING


def test_solicitacao_dentro_das_regras_e_aceita() -> None:
    RestrictedAccessPolicy().validate(solicitacao(AGORA + timedelta(days=7), 80), CONTEXTO)


# --- RN-10: antecedência mínima de 72h -------------------------------------------------------


def test_exatamente_setenta_e_duas_horas_de_antecedencia_passa() -> None:
    """RN-10 — a fronteira."""
    RestrictedAccessPolicy().validate(solicitacao(AGORA + timedelta(hours=72), 80), CONTEXTO)


def test_um_minuto_a_menos_de_antecedencia_recusa() -> None:
    """RN-10 — o outro lado da mesma fronteira."""
    with pytest.raises(PolicyViolation) as erro:
        RestrictedAccessPolicy().validate(
            solicitacao(AGORA + timedelta(hours=71, minutes=59), 80), CONTEXTO
        )
    assert erro.value.rule == "RN-10"


def test_antecedencia_do_auditorio_e_maior_que_a_do_laboratorio() -> None:
    """RN-09 contra RN-10 — 48h bastariam num laboratório, mas não num auditório."""
    with pytest.raises(PolicyViolation):
        RestrictedAccessPolicy().validate(solicitacao(AGORA + timedelta(hours=48), 80), CONTEXTO)


# --- RN-10: mínimo de 20 participantes -------------------------------------------------------


def test_exatamente_vinte_participantes_passa() -> None:
    """RN-10 — 20 é o mínimo aceito, não o primeiro valor recusado."""
    RestrictedAccessPolicy().validate(solicitacao(AGORA + timedelta(days=7), 20), CONTEXTO)


def test_dezenove_participantes_recusa() -> None:
    """RN-10 — o outro lado da mesma fronteira: auditório não é para reunião pequena."""
    with pytest.raises(PolicyViolation) as erro:
        RestrictedAccessPolicy().validate(solicitacao(AGORA + timedelta(days=7), 19), CONTEXTO)
    assert erro.value.rule == "RN-10"


def test_antecedencia_e_verificada_antes_dos_participantes() -> None:
    """Violando as duas, recusa pela primeira — a ordem da §5.3."""
    with pytest.raises(PolicyViolation) as erro:
        RestrictedAccessPolicy().validate(solicitacao(AGORA + timedelta(hours=2), 5), CONTEXTO)
    assert "antecedência" in erro.value.message
