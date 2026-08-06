"""Os schemas Pydantic — a forma dos dados **na fronteira HTTP**.

São classes separadas das entidades de domínio, pelo mesmo motivo que os modelos de persistência são
(ADR-0003): o formato do JSON e o modelo de negócio evoluem por razões diferentes. Aqui a diferença
mais visível é o `TimeSlot`, que no domínio é um objeto de valor com `overlaps` e no corpo da
resposta são dois campos ISO 8601 planos, como manda a §7.1.

A validação que estes schemas fazem é de **formato**: tipo, obrigatoriedade, faixa numérica. Regra
de negócio nenhuma — capacidade positiva é invariante de `Space`, e o intervalo válido é da RN-03.
Uma requisição malformada é recusada com o `422` do Pydantic antes de tocar o domínio; uma
requisição bem formada e inadmissível chega ao domínio e volta com o erro tipado da §7.2.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.infrastructure.notifications.notification import Notification

# --- espaços ---------------------------------------------------------------------------------


class RegisterSpaceRequest(BaseModel):
    """O corpo de `POST /spaces`. Não há campo `active`: o UC-01 diz que o espaço nasce ativo."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32, examples=["LAB-01"])
    name: str = Field(min_length=1, max_length=120, examples=["Laboratório de Redes"])
    kind: SpaceKind
    # `gt=0` repete no formato a invariante de `Space`. Não é duplicação de regra: o domínio
    # continua sendo quem a garante, e isto apenas devolve `422` a quem digitou zero em vez de
    # deixar um `ValueError` virar erro interno.
    capacity: int = Field(gt=0, examples=[30])


class SpaceResponse(BaseModel):
    code: str
    name: str
    kind: SpaceKind
    capacity: int
    active: bool

    @classmethod
    def of(cls, space: Space) -> SpaceResponse:
        return cls(
            code=space.code,
            name=space.name,
            kind=space.kind,
            capacity=space.capacity,
            active=space.active,
        )


# --- reservas --------------------------------------------------------------------------------


class RequestBookingRequest(BaseModel):
    """O corpo de `POST /bookings`, igual ao exemplo da §7.1.

    Não traz `requester_id`: quem solicita é quem fez a requisição, e isso vem do cabeçalho
    `X-User-Id`. Aceitá-lo no corpo permitiria reservar em nome de outra pessoa.
    """

    model_config = ConfigDict(extra="forbid")

    space_code: str = Field(min_length=1, max_length=32, examples=["LAB-01"])
    start_at: datetime = Field(examples=["2026-08-20T14:00:00"])
    end_at: datetime = Field(examples=["2026-08-20T16:00:00"])
    purpose: str = Field(min_length=1, max_length=255, examples=["Aula prática de Redes"])
    attendees: int = Field(gt=0, examples=[25])


class RejectBookingRequest(BaseModel):
    """RN-14 — a rejeição exige motivo. `min_length=1` recusa o corpo vazio no formato; um motivo só
    de espaços passa por aqui e é recusado pelo domínio, que é quem sabe o que "vazio" significa."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=255, examples=["Laboratório em manutenção."])


class BookingResponse(BaseModel):
    id: UUID
    space_code: str
    requester_id: str
    start_at: datetime
    end_at: datetime
    purpose: str
    attendees: int
    status: BookingStatus
    created_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None
    rejection_reason: str | None = None

    @classmethod
    def of(cls, booking: Booking) -> BookingResponse:
        """O `TimeSlot` do domínio vira dois campos planos — a §7.1 não conhece intervalo."""
        return cls(
            id=booking.id,
            space_code=booking.space_code,
            requester_id=booking.requester_id,
            start_at=booking.slot.start_at,
            end_at=booking.slot.end_at,
            purpose=booking.purpose,
            attendees=booking.attendees,
            status=booking.status,
            created_at=booking.created_at,
            decided_by=booking.decided_by,
            decided_at=booking.decided_at,
            rejection_reason=booking.rejection_reason,
        )


# --- notificações e saúde ----------------------------------------------------------------------


class NotificationResponse(BaseModel):
    booking_id: UUID
    space_code: str
    requester_id: str
    occurred_at: datetime
    message: str

    @classmethod
    def of(cls, notification: Notification) -> NotificationResponse:
        return cls(
            booking_id=notification.booking_id,
            space_code=notification.space_code,
            requester_id=notification.requester_id,
            occurred_at=notification.occurred_at,
            message=notification.message,
        )


class ErrorResponse(BaseModel):
    """O corpo único de erro da §7.2. Declarado para aparecer no `/docs`, e não para ser construído
    — quem monta a resposta de erro é `error_handlers.to_response`."""

    error: str = Field(examples=["ScheduleConflict"])
    message: str = Field(examples=["O espaço LAB-01 já possui reserva ativa entre 14:00 e 16:00."])
    rule: str | None = Field(default=None, examples=["RN-01"])
