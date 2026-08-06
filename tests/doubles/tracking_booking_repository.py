"""`TrackingBookingRepository` — a dupla que torna `update` visível.

Existe por causa de um ponto cego descoberto por teste de mutação: retirar a chamada a
`bookings.update(booking)` dos casos de uso de decisão **não quebrava teste nenhum**.

A razão é a dupla em memória. Ela guarda a entidade como recebeu, sem cópia — decisão consciente da
task 06 — então mutar o objeto já o deixa mutado dentro do repositório, e `update` vira redundante.
Contra a implementação SQLAlchemy da task 10 isso não vale: lá as entidades são convertidas para
modelos separados ([ADR-0003](../../docs/ADRs/0003-persistencia-sqlite-repository.md)), e uma
mudança que não passe por `update` simplesmente não chega ao banco.

O erro que esta dupla pega, portanto, é um que só apareceria na task 10 — e que apareceria como
"aprovei a reserva e ela continua pendente depois de reiniciar", que é caro de diagnosticar.

Herda em vez de reimplementar: o comportamento das consultas continua sendo o mesmo, verificado
pelos testes da task 06, e o que muda é apenas o registro do que foi pedido.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.doubles.in_memory_repositories import InMemoryBookingRepository

if TYPE_CHECKING:
    from uuid import UUID

    from agendalab.domain.entities.booking import Booking


class TrackingBookingRepository(InMemoryBookingRepository):
    """Um `InMemoryBookingRepository` que anota quais reservas tiveram `update` solicitado."""

    def __init__(self) -> None:
        super().__init__()
        self.updated_ids: list[UUID] = []

    def update(self, booking: Booking) -> None:
        self.updated_ids.append(booking.id)
        super().update(booking)
