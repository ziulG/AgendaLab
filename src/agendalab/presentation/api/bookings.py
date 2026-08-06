"""As rotas de reserva — UC-03 a UC-07.

As três transições são **sub-recursos criados por `POST`** (`/approval`, `/rejection`,
`/cancellation`), e não um `PATCH /bookings/{id}` com o status novo no corpo. O motivo é semântico e
está na §7: aprovar não é editar um campo, é executar uma transição que o domínio pode recusar. A
rota nomeia a intenção, e o verbo comunica que a operação não é idempotente nem um simples `set`.

Quem verifica o papel é uma dependência (`ManagerDep`, `RequesterDep`), nunca um `if` dentro da
função — RN-11. E quem verifica se a reserva é sua, no cancelamento, é o domínio: isso depende do
estado da reserva, e a borda não o conhece (ADR-0007).
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from agendalab.application.dto import (
    ApproveBookingCommand,
    CancelBookingCommand,
    GetBookingQuery,
    RejectBookingCommand,
    RequestBookingCommand,
)
from agendalab.application.use_cases.approve_booking import ApproveBooking
from agendalab.application.use_cases.cancel_booking import CancelBooking
from agendalab.application.use_cases.get_booking import GetBooking
from agendalab.application.use_cases.reject_booking import RejectBooking
from agendalab.application.use_cases.request_booking import RequestBooking
from agendalab.domain.value_objects.time_slot import TimeSlot
from agendalab.presentation.api.schemas import (
    BookingResponse,
    RejectBookingRequest,
    RequestBookingRequest,
)
from agendalab.presentation.dependencies import (
    ActorDep,
    ManagerDep,
    NowDep,
    get_actor,
    get_approve_booking,
    get_cancel_booking,
    get_get_booking,
    get_reject_booking,
    get_request_booking,
)

# Identidade exigida em todas — ver a nota equivalente em `spaces.py`.
router = APIRouter(prefix="/bookings", tags=["reservas"], dependencies=[Depends(get_actor)])

# As transições devolvem `200`, e não `201`: o sub-recurso criado não tem representação própria, e o
# que interessa a quem chamou é a reserva no estado novo.
RESPOSTAS_DE_TRANSICAO = {
    HTTPStatus.NOT_FOUND: {"description": "Reserva inexistente"},
    HTTPStatus.CONFLICT: {"description": "A transição não é permitida no estado atual (RN-13)"},
}


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    summary="Solicitar reserva (UC-04)",
    response_description="A reserva criada, no status que a política do tipo de espaço determinou",
)
def request_booking(
    body: RequestBookingRequest,
    caso_de_uso: Annotated[RequestBooking, Depends(get_request_booking)],
    actor: ActorDep,
    now: NowDep,
) -> BookingResponse:
    """O intervalo vira `TimeSlot` aqui — se `start_at >= end_at`, a RN-03 recusa na construção.

    `requester_id` vem do cabeçalho, nunca do corpo: quem solicita é quem fez a requisição.

    Sem exigência de papel: qualquer identidade válida solicita, gestor inclusive. A RN-11 restringe
    aprovar e rejeitar, não pedir.
    """
    criada = caso_de_uso.execute(
        RequestBookingCommand(
            space_code=body.space_code,
            requester_id=actor.user_id,
            slot=TimeSlot(body.start_at, body.end_at),
            purpose=body.purpose,
            attendees=body.attendees,
            now=now,
        )
    )
    return BookingResponse.of(criada)


@router.get(
    "/{booking_id}",
    summary="Consultar uma reserva (UC-03)",
    responses={HTTPStatus.NOT_FOUND: {"description": "Reserva inexistente"}},
)
def get_booking(
    booking_id: UUID, caso_de_uso: Annotated[GetBooking, Depends(get_get_booking)]
) -> BookingResponse:
    return BookingResponse.of(caso_de_uso.execute(GetBookingQuery(booking_id=booking_id)))


@router.post(
    "/{booking_id}/approval",
    summary="Aprovar reserva (UC-05)",
    responses=RESPOSTAS_DE_TRANSICAO,  # type: ignore[arg-type]
)
def approve_booking(
    booking_id: UUID,
    caso_de_uso: Annotated[ApproveBooking, Depends(get_approve_booking)],
    actor: ManagerDep,
    now: NowDep,
) -> BookingResponse:
    """RN-11 — só gestor aprova, e é o `ManagerDep` que garante isso antes de a função rodar."""
    aprovada = caso_de_uso.execute(
        ApproveBookingCommand(booking_id=booking_id, actor=actor, now=now)
    )
    return BookingResponse.of(aprovada)


@router.post(
    "/{booking_id}/rejection",
    summary="Rejeitar reserva (UC-06)",
    responses=RESPOSTAS_DE_TRANSICAO,  # type: ignore[arg-type]
)
def reject_booking(
    booking_id: UUID,
    body: RejectBookingRequest,
    caso_de_uso: Annotated[RejectBooking, Depends(get_reject_booking)],
    actor: ManagerDep,
    now: NowDep,
) -> BookingResponse:
    """RN-11 pela dependência, RN-14 pelo domínio — o motivo obrigatório não é verificado aqui."""
    rejeitada = caso_de_uso.execute(
        RejectBookingCommand(
            booking_id=booking_id, actor=actor, reason=body.reason, now=now
        )
    )
    return BookingResponse.of(rejeitada)


@router.post(
    "/{booking_id}/cancellation",
    summary="Cancelar reserva (UC-07)",
    responses=RESPOSTAS_DE_TRANSICAO,  # type: ignore[arg-type]
)
def cancel_booking(
    booking_id: UUID,
    caso_de_uso: Annotated[CancelBooking, Depends(get_cancel_booking)],
    actor: ActorDep,
    now: NowDep,
) -> BookingResponse:
    """A única transição sem exigência de papel na borda.

    A RN-12 permite ao próprio solicitante **ou** a qualquer gestor, e distinguir os dois exige
    saber de quem é a reserva — o que a borda não sabe. Por isso aqui entra o `ActorDep` sem
    filtro, e quem recusa é `_ensure_may_cancel`, dentro do estado.
    """
    cancelada = caso_de_uso.execute(
        CancelBookingCommand(booking_id=booking_id, actor=actor, now=now)
    )
    return BookingResponse.of(cancelada)
