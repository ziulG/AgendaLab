"""`OpenAccessPolicy` — como se reserva uma sala de aula (RN-08).

Sala de aula é recurso abundante e de baixo risco, então a barreira é mínima: aprovação automática,
sem antecedência exigida. A única restrição é de uso justo — 8 horas por solicitante na semana.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from agendalab.domain.entities.booking import BookingStatus
from agendalab.domain.errors import PolicyViolation

if TYPE_CHECKING:
    from agendalab.domain.policies.booking_policy import BookingRequest, PolicyContext

ACTIVE_STATUSES = (BookingStatus.PENDING, BookingStatus.APPROVED)


def _iso_week(moment: datetime) -> tuple[int, int]:
    """Ano e número da semana ISO — segunda a domingo, conforme a RN-08."""
    return moment.isocalendar()[:2]


class OpenAccessPolicy:
    WEEKLY_HOUR_CAP = 8

    def initial_status(self) -> BookingStatus:
        return BookingStatus.APPROVED

    def validate(self, request: BookingRequest, context: PolicyContext) -> None:
        """RN-08 — teto semanal, contando a reserva em análise.

        A soma é feita em `timedelta`, e não com `duration_hours()`: vinte minutos é 0,333... hora,
        e acumular horas quebradas em ponto flutuante pode ultrapassar o teto por um fio e recusar
        uma solicitação que a regra aceita. `timedelta` conta microssegundos inteiros.
        """
        week = _iso_week(request.slot.start_at)
        booked = request.slot.end_at - request.slot.start_at
        for booking in context.requester_week_bookings:
            if booking.status in ACTIVE_STATUSES and _iso_week(booking.slot.start_at) == week:
                booked += booking.slot.end_at - booking.slot.start_at

        if booked > timedelta(hours=self.WEEKLY_HOUR_CAP):
            horas = booked.total_seconds() / 3600
            raise PolicyViolation(
                f"O teto de {self.WEEKLY_HOUR_CAP}h semanais em salas de aula seria excedido: "
                f"a semana ficaria com {horas:.1f}h.",
                "RN-08",
            )
