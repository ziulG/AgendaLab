"""Os contratos de persistência, declarados **pelo domínio**.

Este arquivo é a materialização da inversão de dependência do ADR-0001. O domínio declara o que
precisa; a infraestrutura obedece, e a seta aponta para dentro. Se estas interfaces migrarem para
`infrastructure/`, a decisão foi revertida e a arquitetura vira organização de pastas.

As assinaturas falam em `Space` e `Booking` — nunca em `Session`, `Query` ou qualquer tipo de ORM.
É isso que permite existirem duas implementações do mesmo contrato: a SQLAlchemy da task 10 e as
duplas em memória contra as quais os casos de uso são testados, em milissegundos e sem tocar disco.

Em tempo de execução este módulo importa apenas `typing`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import date, datetime
    from uuid import UUID

    from agendalab.domain.entities.booking import Booking
    from agendalab.domain.entities.space import Space, SpaceKind
    from agendalab.domain.value_objects.time_slot import TimeSlot


@runtime_checkable
class SpaceRepository(Protocol):
    def add(self, space: Space) -> None:
        """Guarda o espaço. Levanta `DuplicateSpaceCode` se o código já existir (RN-16)."""

    def find_by_code(self, code: str) -> Space | None:
        """O espaço, ou `None`. Traduzir a ausência em `SpaceNotFound` é do caso de uso."""

    def list_all(self, kind: SpaceKind | None = None, active: bool | None = None) -> list[Space]:
        """Os espaços que casam com os filtros. `None` significa não filtrar por aquele critério."""


@runtime_checkable
class BookingRepository(Protocol):
    def add(self, booking: Booking) -> None:
        """Guarda uma reserva nova."""

    def update(self, booking: Booking) -> None:
        """Grava o estado atual de uma reserva já existente."""

    def find_by_id(self, booking_id: UUID) -> Booking | None:
        """A reserva, ou `None`. Traduzir a ausência em `BookingNotFound` é do caso de uso."""

    def find_active_overlapping(self, space_code: str, slot: TimeSlot) -> list[Booking]:
        """Reservas ativas do espaço que se sobrepõem ao intervalo — RN-01 e RN-02."""

    def find_active_by_requester_in_week(
        self, requester_id: str, reference: datetime
    ) -> list[Booking]:
        """Reservas ativas do solicitante na semana ISO de `reference` — insumo da RN-08."""

    def list_by_space_and_date(self, space_code: str, day: date) -> list[Booking]:
        """Reservas ativas do espaço naquele dia — a agenda que o UC-03 devolve."""
