"""UC-03 — consultar uma reserva pelo identificador.

O par de `GetSpace`, e pela mesma razão: a §7 promete `GET /bookings/{id}`, e sem ele um cliente que
acabou de criar uma reserva não teria como relê-la para acompanhar a decisão do gestor.

Note o que ele **não** faz: não verifica se quem consulta é o dono da reserva. Consultar não é
decidir, e a RN-12 fala de cancelamento. Restringir a leitura seria inventar regra que a
especificação não tem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agendalab.domain.errors import BookingNotFound

if TYPE_CHECKING:
    from agendalab.application.dto import GetBookingQuery
    from agendalab.domain.entities.booking import Booking
    from agendalab.domain.repositories import BookingRepository


class GetBooking:
    def __init__(self, bookings: BookingRepository) -> None:
        self._bookings = bookings

    def execute(self, query: GetBookingQuery) -> Booking:
        """A reserva, ou `BookingNotFound`."""
        booking = self._bookings.find_by_id(query.booking_id)
        if booking is None:
            raise BookingNotFound(query.booking_id)
        return booking
