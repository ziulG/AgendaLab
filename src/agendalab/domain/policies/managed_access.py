"""`ManagedAccessPolicy` — como se reserva um laboratório (RN-09).

Laboratório tem equipamento caro e precisa de preparo: exige aval humano, aviso prévio de um dia
e sessões curtas o bastante para caber na agenda do técnico.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from agendalab.domain.entities.booking import BookingStatus
from agendalab.domain.errors import PolicyViolation

if TYPE_CHECKING:
    from agendalab.domain.policies.booking_policy import BookingRequest, PolicyContext


class ManagedAccessPolicy:
    MIN_NOTICE_HOURS = 24
    MAX_DURATION_HOURS = 4

    def initial_status(self) -> BookingStatus:
        return BookingStatus.PENDING

    def validate(self, request: BookingRequest, context: PolicyContext) -> None:
        """RN-09 — antecedência mínima e duração máxima, nesta ordem."""
        if request.slot.start_at - context.now < timedelta(hours=self.MIN_NOTICE_HOURS):
            raise PolicyViolation(
                f"Reservar laboratório exige {self.MIN_NOTICE_HOURS}h de antecedência.",
                "RN-09",
            )
        if request.slot.duration_hours() > self.MAX_DURATION_HOURS:
            raise PolicyViolation(
                f"Uma reserva de laboratório não pode passar de {self.MAX_DURATION_HOURS}h.",
                "RN-09",
            )
