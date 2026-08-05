"""`BookingPolicy` — o contrato do padrão Strategy (ADR-0004).

Cada tipo de espaço tem regras próprias, e elas não diferem apenas em parâmetros: "teto de horas na
semana" e "mínimo de participantes" são verificações de naturezas distintas, sobre dados distintos.
É essa variação estrutural que o Strategy isola.

A interface é um `Protocol`: as três políticas concretas **não** herdam dela. Nenhuma precisa
importar este módulo para funcionar, o que é a forma mais direta de dizer que uma política não
depende de nada. A conformidade é verificada em `tests/unit/policies/test_registry.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from agendalab.domain.entities.booking import Booking, BookingStatus
    from agendalab.domain.entities.space import Space
    from agendalab.domain.value_objects.time_slot import TimeSlot


@dataclass(frozen=True, slots=True)
class BookingRequest:
    """O que o solicitante pediu. Ainda não é uma reserva — nada foi decidido."""

    space_code: str
    requester_id: str
    slot: TimeSlot
    purpose: str
    attendees: int


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """Tudo de que uma política precisa para decidir sem consultar nada.

    Passar o contexto pronto é o que mantém as políticas como funções puras sobre os dados que
    recebem — sem repositório, sem I/O e sem relógio global.

    `requester_week_bookings` são as reservas **ativas** do solicitante cuja data de início cai na
    semana de referência, **em espaços do mesmo tipo do solicitado**. O filtro por tipo é
    responsabilidade de quem monta o contexto: `Booking` guarda `space_code`, não `kind`, e a
    política não tem como resolver um no outro. É o que a RN-08 exige ao contar apenas horas de
    sala de aula.
    """

    now: datetime
    space: Space
    requester_week_bookings: list[Booking]


@runtime_checkable
class BookingPolicy(Protocol):
    def initial_status(self) -> BookingStatus:
        """Estado em que a reserva nasce sob esta política (RN-07)."""

    def validate(self, request: BookingRequest, context: PolicyContext) -> None:
        """Passa em silêncio, ou levanta `PolicyViolation` com a regra que recusou."""
