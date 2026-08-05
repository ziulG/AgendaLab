"""RN-12 — quem pode cancelar uma reserva.

A regra é "o próprio solicitante **ou** qualquer gestor", e responder isso exige conhecer a
reserva. É por isso que ela fica no domínio, e não na borda: a verificação de papel a apresentação
consegue fazer sozinha, mas a de propriedade — "esta reserva é sua?" — não
([ADR-0007](docs/ADRs/0007-autenticacao-fora-de-escopo.md)).
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from agendalab.domain.actor import Actor, Role
from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.errors import InvalidStateTransition, PermissionDenied
from agendalab.domain.value_objects.time_slot import TimeSlot

DONO = Actor(user_id="2019001234", role=Role.REQUESTER)
TERCEIRO = Actor(user_id="2020005678", role=Role.REQUESTER)
GESTOR = Actor(user_id="chefe.laboratorio", role=Role.MANAGER)
AGORA = datetime(2026, 8, 6, 10, 30)

# As duas células ✅ de `cancel` na §5.5 — a regra vale igual nas duas.
ESTADOS_CANCELAVEIS = [BookingStatus.PENDING, BookingStatus.APPROVED]
ESTADOS_TERMINAIS = [BookingStatus.REJECTED, BookingStatus.CANCELLED]


def reserva(status: BookingStatus) -> Booking:
    return Booking(
        id=uuid4(),
        space_code="LAB-01",
        requester_id=DONO.user_id,
        slot=TimeSlot(datetime(2026, 8, 20, 14), datetime(2026, 8, 20, 16)),
        purpose="Aula prática de Redes de Computadores",
        attendees=25,
        status=status,
        created_at=datetime(2026, 8, 5, 9, 12, 33),
    )


@pytest.mark.parametrize("status", ESTADOS_CANCELAVEIS, ids=lambda s: str(s))
def test_o_dono_cancela_a_propria_reserva(status: BookingStatus) -> None:
    """RN-12."""
    booking = reserva(status)
    booking.cancel(DONO, AGORA)
    assert booking.status is BookingStatus.CANCELLED
    assert booking.decided_by == DONO.user_id


@pytest.mark.parametrize("status", ESTADOS_CANCELAVEIS, ids=lambda s: str(s))
def test_o_gestor_cancela_reserva_de_terceiro(status: BookingStatus) -> None:
    """RN-12 — o gestor não precisa ser o solicitante."""
    booking = reserva(status)
    booking.cancel(GESTOR, AGORA)
    assert booking.status is BookingStatus.CANCELLED
    assert booking.decided_by == GESTOR.user_id


@pytest.mark.parametrize("status", ESTADOS_CANCELAVEIS, ids=lambda s: str(s))
def test_solicitante_nao_cancela_reserva_alheia(status: BookingStatus) -> None:
    """RN-12 — ser solicitante não basta; é preciso ser o solicitante daquela reserva."""
    booking = reserva(status)
    with pytest.raises(PermissionDenied) as erro:
        booking.cancel(TERCEIRO, AGORA)
    assert erro.value.rule == "RN-12"


@pytest.mark.parametrize("status", ESTADOS_CANCELAVEIS, ids=lambda s: str(s))
def test_recusa_por_permissao_nao_altera_a_reserva(status: BookingStatus) -> None:
    booking = reserva(status)
    with pytest.raises(PermissionDenied):
        booking.cancel(TERCEIRO, AGORA)
    assert booking.status is status
    assert booking.decided_by is None
    assert booking.decided_at is None


@pytest.mark.parametrize("status", ESTADOS_TERMINAIS, ids=lambda s: str(s))
def test_em_estado_terminal_o_estado_recusa_antes_da_permissao(status: BookingStatus) -> None:
    """A ordem importa: `RejectedState` e `CancelledState` não sobrescrevem `cancel`, então nem
    chegam a consultar a RN-12. Mesmo o dono recebe `InvalidStateTransition`, não `PermissionDenied`.
    """
    booking = reserva(status)
    with pytest.raises(InvalidStateTransition):
        booking.cancel(DONO, AGORA)
