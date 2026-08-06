"""Conversão entre modelo de persistência e entidade de domínio.

Este arquivo é o preço do ADR-0003, cobrado à vista: cada campo aparece na entidade, no modelo e
aqui. Um campo novo exige tocar em três lugares.

O que se compra é o que o resto do sistema demonstra — um domínio que roda sem banco e 419 testes em
0,13 segundos. E o risco de as três cópias divergirem tem mitigação escrita: `tests/integration/
test_mappers.py` percorre os campos declarados nas dataclasses e exige que **todos** sobrevivam à
ida e volta, então um campo esquecido aqui quebra a suíte em vez de virar dado perdido.

A conversão é função pura. Nenhuma destas funções toca sessão, e é por isso que dá para testá-las
sem banco.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.domain.value_objects.time_slot import TimeSlot
from agendalab.infrastructure.persistence.models import BookingModel, SpaceModel

if TYPE_CHECKING:
    pass


# --- Space ---------------------------------------------------------------------------------------


def to_space(model: SpaceModel) -> Space:
    """A entidade correspondente à linha. `kind` volta a ser enum: `policy_for` indexa por ele."""
    return Space(
        code=model.code,
        name=model.name,
        kind=SpaceKind(model.kind),
        capacity=model.capacity,
        active=model.active,
    )


def to_space_model(space: Space) -> SpaceModel:
    return SpaceModel(
        code=space.code,
        name=space.name,
        kind=space.kind.value,
        capacity=space.capacity,
        active=space.active,
    )


# --- Booking -------------------------------------------------------------------------------------


def to_booking(model: BookingModel) -> Booking:
    """A entidade correspondente à linha.

    As duas colunas voltam a ser um `TimeSlot`, o que devolve à reserva a operação `overlaps` — e
    `status` volta a ser `BookingStatus`, sem o que `Booking._state` não conseguiria resolver o
    objeto de estado e o padrão State morreria na volta do banco.
    """
    return Booking(
        id=model.id,
        space_code=model.space_code,
        requester_id=model.requester_id,
        slot=TimeSlot(model.start_at, model.end_at),
        purpose=model.purpose,
        attendees=model.attendees,
        status=BookingStatus(model.status),
        created_at=model.created_at,
        decided_by=model.decided_by,
        decided_at=model.decided_at,
        rejection_reason=model.rejection_reason,
    )


def to_booking_model(booking: Booking) -> BookingModel:
    model = BookingModel(id=booking.id)
    apply_booking(model, booking)
    return model


def apply_booking(model: BookingModel, booking: Booking) -> None:
    """Copia o estado da entidade para um modelo já existente — o caminho do `update`.

    Escrever isto separado de `to_booking_model`, e não criar um modelo novo a cada atualização, é o
    que mantém a **identidade da linha**. A sessão já rastreia aquele objeto; substituí-lo por outro
    com o mesmo `id` seria pedir uma inserção onde se quer uma atualização.

    O `id` não é copiado, deliberadamente: identidade não muda.
    """
    model.space_code = booking.space_code
    model.requester_id = booking.requester_id
    model.start_at = booking.slot.start_at
    model.end_at = booking.slot.end_at
    model.purpose = booking.purpose
    model.attendees = booking.attendees
    model.status = booking.status.value
    model.created_at = booking.created_at
    model.decided_by = booking.decided_by
    model.decided_at = booking.decided_at
    model.rejection_reason = booking.rejection_reason
