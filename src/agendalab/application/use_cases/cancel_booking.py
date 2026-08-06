"""UC-07 — cancelar reserva.

O mais magro dos sete casos de uso, e o que melhor mostra por que a autorização foi partida em duas
(ADR-0007). A RN-12 diz que cancela o próprio solicitante ou qualquer gestor: responder isso exige
saber de quem é a reserva, e a borda HTTP só conhece os cabeçalhos de identidade. Então a regra vive
no domínio, dentro de `_ensure_may_cancel`, e este arquivo não a menciona.

Cancelar é também a única operação permitida a partir de dois estados — `PENDING` e `APPROVED`. O
caso de uso não sabe disso: chama `cancel` e deixa cada estado responder por si.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agendalab.domain.errors import BookingNotFound
from agendalab.domain.events.booking_events import BookingCancelled

if TYPE_CHECKING:
    from agendalab.application.dto import CancelBookingCommand
    from agendalab.domain.entities.booking import Booking
    from agendalab.domain.events.publisher import EventPublisher
    from agendalab.domain.repositories import BookingRepository


class CancelBooking:
    def __init__(self, bookings: BookingRepository, publisher: EventPublisher) -> None:
        self._bookings = bookings
        self._publisher = publisher

    def execute(self, command: CancelBookingCommand) -> Booking:
        """A reserva cancelada. Levanta `BookingNotFound`, `PermissionDenied` (RN-12) ou
        `InvalidStateTransition` (RN-13) — os dois últimos vindos do domínio."""
        booking = self._bookings.find_by_id(command.booking_id)
        if booking is None:
            raise BookingNotFound(command.booking_id)

        booking.cancel(command.actor, command.now)
        self._bookings.update(booking)
        self._publisher.publish(  # RN-15
            BookingCancelled(
                booking_id=booking.id,
                space_code=booking.space_code,
                requester_id=booking.requester_id,
                occurred_at=command.now,
                # Quem cancelou pode não ser quem solicitou — o notificador precisa dos dois.
                decided_by=command.actor.user_id,
            )
        )
        return booking
