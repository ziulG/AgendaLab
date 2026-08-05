"""Os quatro estados da reserva — a tabela da §5.5 em quatro classes.

Cada classe declara **apenas** o que permite. `RejectedState` e `CancelledState` não declaram
transição alguma: são terminais, e herdam a recusa da base. Ler as quatro classes é ler a tabela
da especificação.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agendalab.domain.entities.booking import BookingStatus
from agendalab.domain.errors import MissingRejectionReason
from agendalab.domain.states.booking_state import BookingState

if TYPE_CHECKING:
    from datetime import datetime

    from agendalab.domain.actor import Actor
    from agendalab.domain.entities.booking import Booking


class PendingState(BookingState):
    """Aguardando decisão. Aceita as três transições."""

    def status(self) -> BookingStatus:
        return BookingStatus.PENDING

    def approve(self, booking: Booking, actor: Actor, now: datetime) -> None:
        self._record_decision(booking, BookingStatus.APPROVED, actor, now)

    def reject(self, booking: Booking, actor: Actor, reason: str, now: datetime) -> None:
        if not reason.strip():
            raise MissingRejectionReason()  # RN-14 — antes de transicionar, não depois
        self._record_decision(booking, BookingStatus.REJECTED, actor, now)
        booking.rejection_reason = reason

    def cancel(self, booking: Booking, actor: Actor, now: datetime) -> None:
        self._ensure_may_cancel(booking, actor)  # RN-12
        self._record_decision(booking, BookingStatus.CANCELLED, actor, now)


class ApprovedState(BookingState):
    """Aprovada e ocupando o horário. Já não pode ser aprovada nem rejeitada, mas ainda cancela."""

    def status(self) -> BookingStatus:
        return BookingStatus.APPROVED

    def cancel(self, booking: Booking, actor: Actor, now: datetime) -> None:
        self._ensure_may_cancel(booking, actor)  # RN-12
        self._record_decision(booking, BookingStatus.CANCELLED, actor, now)


class RejectedState(BookingState):
    """Terminal. Nenhuma transição sobrescrita — a recusa vem da base."""

    def status(self) -> BookingStatus:
        return BookingStatus.REJECTED


class CancelledState(BookingState):
    """Terminal. O intervalo volta a ficar livre para novas solicitações."""

    def status(self) -> BookingStatus:
        return BookingStatus.CANCELLED


# O banco guarda um `BookingStatus` simples; o objeto de estado é reconstruído a partir dele.
# Os estados não têm dados próprios, então uma instância de cada basta para o sistema inteiro.
_STATES: dict[BookingStatus, BookingState] = {
    BookingStatus.PENDING: PendingState(),
    BookingStatus.APPROVED: ApprovedState(),
    BookingStatus.REJECTED: RejectedState(),
    BookingStatus.CANCELLED: CancelledState(),
}


def state_for(status: BookingStatus) -> BookingState:
    """O estado correspondente ao status. Um status sem estado é erro de programação."""
    return _STATES[status]
