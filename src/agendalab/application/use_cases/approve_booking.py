"""UC-05 — aprovar reserva.

O caso de uso não decide se a reserva pode ser aprovada. Ele chama `approve`, e a reserva pergunta
ao seu estado atual (ADR-0005). A tabela da §5.5 mora num lugar só, e este arquivo é um dos lugares
onde ela **não** está.

O que existe aqui e não nos outros dois é a revalidação do conflito. Entre a solicitação e a decisão
do gestor pode ter passado uma semana, e o horário pode ter sido ocupado nesse meio-tempo — a
verificação da task 08 respondeu sobre um mundo que já mudou.

A RN-11, que exige gestor para aprovar, é da borda HTTP (task 11, ADR-0007). Aqui o `actor` serve
para a trilha de decisão.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agendalab.domain.errors import BookingNotFound, ScheduleConflict
from agendalab.domain.events.booking_events import BookingApproved

if TYPE_CHECKING:
    from agendalab.application.dto import ApproveBookingCommand
    from agendalab.domain.entities.booking import Booking
    from agendalab.domain.events.publisher import EventPublisher
    from agendalab.domain.repositories import BookingRepository


class ApproveBooking:
    def __init__(self, bookings: BookingRepository, publisher: EventPublisher) -> None:
        self._bookings = bookings
        self._publisher = publisher

    def execute(self, command: ApproveBookingCommand) -> Booking:
        """A reserva aprovada. Levanta `BookingNotFound`, `ScheduleConflict` ou
        `InvalidStateTransition` — este último vindo do estado, não daqui."""
        booking = self._bookings.find_by_id(command.booking_id)
        if booking is None:
            raise BookingNotFound(command.booking_id)

        self._ensure_slot_still_free(booking)

        booking.approve(command.actor, command.now)  # RN-13 — quem valida é o estado
        self._bookings.update(booking)
        self._publisher.publish(  # RN-15
            BookingApproved(
                booking_id=booking.id,
                space_code=booking.space_code,
                requester_id=booking.requester_id,
                occurred_at=command.now,
                decided_by=command.actor.user_id,
            )
        )
        return booking

    def _ensure_slot_still_free(self, booking: Booking) -> None:
        """RN-01 revalidada no momento da decisão.

        A própria reserva é descartada pelo `id`: ela está `PENDING`, logo é ativa, logo aparece na
        consulta de sobreposição — comparada consigo mesma, todo intervalo conflita. Sem esse
        descarte o sistema recusaria toda aprovação.
        """
        concorrentes = [
            outra
            for outra in self._bookings.find_active_overlapping(booking.space_code, booking.slot)
            if outra.id != booking.id
        ]
        if concorrentes:
            raise ScheduleConflict(
                booking.space_code, booking.slot.start_at, booking.slot.end_at
            )
