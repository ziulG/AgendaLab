"""Repositórios em memória — duplas de teste, não código de produção.

Vivem em `tests/` porque é o que são, e o ADR-0003 as descreve exatamente assim. Elas existem por
causa da inversão de dependência: como `SpaceRepository` e `BookingRepository` são declarados no
domínio, a camada de aplicação pode ser exercitada por inteiro sem banco, sem disco e em
milissegundos.

As consultas não reimplementam regra: a sobreposição sai de `TimeSlot.overlaps` (RN-02), a semana
sai de `TimeSlot.iso_week` (RN-08) e o que conta como ativa sai de `ACTIVE_STATUSES`, derivado dos
estados (RN-01). Uma dupla que reescrevesse essas regras poderia divergir da implementação real, e
o erro só apareceria na task 10.

Guardam as entidades como recebidas, sem cópia: é o comportamento esperado de um repositório em
memória, e a separação real entre modelo de persistência e domínio é da task 10.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from agendalab.domain.errors import DuplicateSpaceCode
from agendalab.domain.states.concrete_states import ACTIVE_STATUSES
from agendalab.domain.value_objects.time_slot import TimeSlot

if TYPE_CHECKING:
    from datetime import date
    from uuid import UUID

    from agendalab.domain.entities.booking import Booking
    from agendalab.domain.entities.space import Space, SpaceKind


class InMemorySpaceRepository:
    def __init__(self) -> None:
        self._spaces: dict[str, Space] = {}

    def add(self, space: Space) -> None:
        if space.code in self._spaces:
            raise DuplicateSpaceCode(space.code)  # RN-16
        self._spaces[space.code] = space

    def find_by_code(self, code: str) -> Space | None:
        return self._spaces.get(code)

    def list_all(self, kind: SpaceKind | None = None, active: bool | None = None) -> list[Space]:
        return [
            space
            for space in self._spaces.values()
            if (kind is None or space.kind is kind) and (active is None or space.active is active)
        ]


class InMemoryBookingRepository:
    def __init__(self) -> None:
        self._bookings: dict[UUID, Booking] = {}

    def add(self, booking: Booking) -> None:
        self._bookings[booking.id] = booking

    def update(self, booking: Booking) -> None:
        self._bookings[booking.id] = booking

    def find_by_id(self, booking_id: UUID) -> Booking | None:
        return self._bookings.get(booking_id)

    def find_active_overlapping(self, space_code: str, slot: TimeSlot) -> list[Booking]:
        """RN-01 e RN-02 — a comparação de datas é a de `TimeSlot.overlaps`, não uma cópia dela."""
        return [
            booking
            for booking in self._active()
            if booking.space_code == space_code and booking.slot.overlaps(slot)
        ]

    def find_active_by_requester_in_week(
        self, requester_id: str, reference: datetime
    ) -> list[Booking]:
        """Insumo da RN-08 — mesma semana ISO de `reference`, mesmo solicitante."""
        week = reference.isocalendar()[:2]
        return [
            booking
            for booking in self._active()
            if booking.requester_id == requester_id and booking.slot.iso_week() == week
        ]

    def list_by_space_and_date(self, space_code: str, day: date) -> list[Booking]:
        """A agenda do UC-03: reservas ativas que ocupam qualquer faixa daquele dia.

        O dia vira um intervalo de meia-noite a meia-noite e a pergunta volta a ser `overlaps`.
        Comparar apenas a data de início esconderia uma reserva das 22h às 2h da consulta do dia
        seguinte — justamente quando ela atrapalha quem procura horário livre pela manhã.
        """
        inicio = datetime.combine(day, time.min)
        dia_inteiro = TimeSlot(inicio, inicio + timedelta(days=1))
        return [
            booking
            for booking in self._active()
            if booking.space_code == space_code and booking.slot.overlaps(dia_inteiro)
        ]

    def _active(self) -> list[Booking]:
        """RN-01 — `PENDING` ou `APPROVED`; uma reserva cancelada libera o horário."""
        return [b for b in self._bookings.values() if b.status in ACTIVE_STATUSES]
