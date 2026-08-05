"""`Booking` — a solicitação de uso de um espaço num intervalo.

A reserva **não decide** se uma transição é válida: ela pergunta ao seu estado atual (ADR-0005).
É a diferença entre um `if status == ...` replicado em cada caso de uso e uma regra que existe num
lugar só.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from agendalab.domain.value_objects.time_slot import TimeSlot

if TYPE_CHECKING:
    from agendalab.domain.actor import Actor
    from agendalab.domain.states.booking_state import BookingState


class BookingStatus(StrEnum):
    """Os quatro estados da §5.5. `REJECTED` e `CANCELLED` são terminais."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class Booking:
    id: UUID
    space_code: str
    requester_id: str
    slot: TimeSlot
    purpose: str
    attendees: int
    status: BookingStatus
    created_at: datetime
    # Trilha de decisão — nula até que alguém decida sobre a reserva.
    decided_by: str | None = None
    decided_at: datetime | None = None
    rejection_reason: str | None = None

    @property
    def _state(self) -> BookingState:
        """O objeto de estado correspondente ao `status` atual.

        Derivado, e não guardado: o `status` é o que a §4.1 persiste, então ele é a única fonte de
        verdade — um atributo paralelo poderia divergir dele.

        O import é adiado de propósito. `concrete_states` importa `BookingStatus` daqui, e daqui
        se precisa de `state_for` de lá: o ciclo é inerente ao State, em que o contexto conhece
        seus estados e os estados mutam o contexto. Com os dois imports no topo dos módulos, o
        primeiro `import` falharia — seja qual for a ordem.
        """
        from agendalab.domain.states.concrete_states import state_for

        return state_for(self.status)

    def approve(self, actor: Actor, now: datetime) -> None:
        self._state.approve(self, actor, now)

    def reject(self, actor: Actor, reason: str, now: datetime) -> None:
        self._state.reject(self, actor, reason, now)

    def cancel(self, actor: Actor, now: datetime) -> None:
        self._state.cancel(self, actor, now)
