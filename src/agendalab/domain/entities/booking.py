"""`Booking` — a solicitação de uso de um espaço num intervalo.

Nesta etapa a reserva é estrutura de dados com os campos da §4.1. Ela ainda não sabe aprovar,
rejeitar nem cancelar: as transições chegam na task 03, quando o padrão State entra e `Booking`
passa a delegar a decisão ao seu estado atual (ADR-0005).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from agendalab.domain.value_objects.time_slot import TimeSlot


class BookingStatus(StrEnum):
    """Os quatro estados da §5.5. `REJECTED` e `CANCELLED` são terminais."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class Booking:
    id: UUID
    space_code: str
    requester_id: str
    slot: TimeSlot
    purpose: str
    attendees: int
    status: BookingStatus
    created_at: datetime
    # Trilha de decisão — nula até que alguém decida sobre a reserva.
    decided_by: str | None = None
    decided_at: datetime | None = None
    rejection_reason: str | None = None
