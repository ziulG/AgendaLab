"""`BookingState` — o contrato do padrão State (ADR-0005).

**A recusa é o comportamento padrão.** Os três métodos de transição levantam
`InvalidStateTransition` aqui na base, e cada estado concreto sobrescreve apenas o que permite.
Isso inverte o ônus da escrita: um estado novo é seguro por omissão, porque esquecer de habilitar
uma transição resulta em recusa — nunca em permissão indevida.

O instante da decisão chega por parâmetro, e não de `datetime.now()`: relógio é I/O disfarçado
(ADR-0009), e nenhuma camada interna do sistema o lê. É o mesmo mecanismo do `PolicyContext.now`
usado pelas políticas (ADR-0004).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from agendalab.domain.actor import Role
from agendalab.domain.errors import InvalidStateTransition, PermissionDenied

if TYPE_CHECKING:
    from datetime import datetime

    from agendalab.domain.actor import Actor
    from agendalab.domain.entities.booking import Booking, BookingStatus


class BookingState(ABC):
    @abstractmethod
    def status(self) -> BookingStatus:
        """O membro de `BookingStatus` que este estado representa."""

    def approve(self, booking: Booking, actor: Actor, now: datetime) -> None:
        raise InvalidStateTransition(self.status(), "approve")

    def reject(self, booking: Booking, actor: Actor, reason: str, now: datetime) -> None:
        raise InvalidStateTransition(self.status(), "reject")

    def cancel(self, booking: Booking, actor: Actor, now: datetime) -> None:
        raise InvalidStateTransition(self.status(), "cancel")

    def occupies_slot(self) -> bool:
        """RN-01 — se uma reserva neste estado ocupa o horário do espaço.

        O estado governa mais do que a transição, e é por isso que o ADR-0005 preferiu State a uma
        tabela declarativa: uma tabela responderia "esta transição é permitida?" mas não expressaria
        que uma reserva rejeitada não ocupa horário.

        O padrão aqui é `True`, ao contrário das transições — e a inversão é deliberada. Nas
        transições, esquecer de habilitar resulta em recusa, que é o lado seguro. Aqui o lado seguro
        é o oposto: um estado novo que esqueça de se declarar bloqueia o horário, em vez de liberar
        um intervalo que deveria estar ocupado e abrir caminho para reserva dupla.
        """
        return True

    # --- auxiliares dos estados que permitem transição ---------------------------------------
    #
    # Ficam na base porque são idênticos em todo estado que permite a transição, e duplicá-los é
    # exatamente como as variações divergentes nascem.

    @staticmethod
    def _record_decision(
        booking: Booking, status: BookingStatus, actor: Actor, now: datetime
    ) -> None:
        """Aplica o novo status e registra a trilha de decisão da §4.1."""
        booking.status = status
        booking.decided_by = actor.user_id
        booking.decided_at = now

    @staticmethod
    def _ensure_may_cancel(booking: Booking, actor: Actor) -> None:
        """RN-12 — cancela o próprio solicitante da reserva ou qualquer gestor.

        Esta é a metade da autorização que pertence ao domínio: responder "esta reserva é sua?"
        exige conhecer a reserva, e a borda não tem como fazê-lo (ADR-0007).
        """
        if actor.role is not Role.MANAGER and actor.user_id != booking.requester_id:
            raise PermissionDenied(
                f"O solicitante {actor.user_id} não pode cancelar uma reserva de "
                f"{booking.requester_id}.",
                "RN-12",
            )
