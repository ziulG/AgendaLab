"""UC-06 — rejeitar reserva.

Quatro linhas de orquestração: carrega, transiciona, persiste, publica. A RN-14 — motivo
obrigatório — não aparece aqui, e essa ausência é deliberada: verificá-la neste arquivo criaria uma
segunda guarda que poderia divergir da primeira, e deixaria a regra vivendo em dois lugares.

Quem recusa motivo vazio é `PendingState.reject`, **antes** de mudar o status. É o que garante a
invariante da §4.3 — uma reserva `REJECTED` sempre tem `rejection_reason` preenchido — sem uma
janela em que ela esteja rejeitada e sem motivo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agendalab.domain.errors import BookingNotFound
from agendalab.domain.events.booking_events import BookingRejected

if TYPE_CHECKING:
    from agendalab.application.dto import RejectBookingCommand
    from agendalab.domain.entities.booking import Booking
    from agendalab.domain.events.publisher import EventPublisher
    from agendalab.domain.repositories import BookingRepository


class RejectBooking:
    def __init__(self, bookings: BookingRepository, publisher: EventPublisher) -> None:
        self._bookings = bookings
        self._publisher = publisher

    def execute(self, command: RejectBookingCommand) -> Booking:
        """A reserva rejeitada. Levanta `BookingNotFound`, `MissingRejectionReason` (RN-14) ou
        `InvalidStateTransition` (RN-13) — os dois últimos vindos do domínio."""
        booking = self._bookings.find_by_id(command.booking_id)
        if booking is None:
            raise BookingNotFound(command.booking_id)

        booking.reject(command.actor, command.reason, command.now)
        self._bookings.update(booking)
        self._publisher.publish(  # RN-15
            BookingRejected(
                booking_id=booking.id,
                space_code=booking.space_code,
                requester_id=booking.requester_id,
                occurred_at=command.now,
                decided_by=command.actor.user_id,
                # O mesmo texto que o domínio acabou de gravar. Vem do comando, e não da entidade,
                # porque lá ele é `str | None` — e a essa altura já se sabe que não é nulo.
                reason=command.reason,
            )
        )
        return booking
