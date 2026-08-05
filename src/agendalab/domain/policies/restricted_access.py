"""`RestrictedAccessPolicy` — como se reserva o auditório (RN-10).

Auditório é recurso único no campus: só se justifica para eventos de porte, e três dias de
antecedência é o que a logística exige.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from agendalab.domain.entities.booking import BookingStatus
from agendalab.domain.errors import PolicyViolation

if TYPE_CHECKING:
    from agendalab.domain.policies.booking_policy import BookingRequest, PolicyContext


class RestrictedAccessPolicy:
    MIN_NOTICE_HOURS = 72
    MIN_ATTENDEES = 20

    def initial_status(self) -> BookingStatus:
        return BookingStatus.PENDING

    def validate(self, request: BookingRequest, context: PolicyContext) -> None:
        """RN-10 — antecedência mínima e porte mínimo do evento, nesta ordem."""
        if request.slot.start_at - context.now < timedelta(hours=self.MIN_NOTICE_HOURS):
            raise PolicyViolation(
                f"Reservar o auditório exige {self.MIN_NOTICE_HOURS}h de antecedência.",
                "RN-10",
            )
        if request.attendees < self.MIN_ATTENDEES:
            raise PolicyViolation(
                f"O auditório é destinado a eventos de porte: mínimo de "
                f"{self.MIN_ATTENDEES} participantes, e foram informados {request.attendees}.",
                "RN-10",
            )
