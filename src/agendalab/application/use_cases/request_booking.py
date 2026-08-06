"""UC-04 — solicitar reserva.

O caso de uso central do sistema, e o único em que os três padrões colaboram na mesma operação: o
Strategy escolhe a política do tipo de espaço e com ela o status inicial, o State governa a reserva
que nasce, o Observer publica o fato consumado. Nenhum dos três é mencionado por nome aqui — é
assim que se sabe que estão funcionando.

O que este arquivo **não** contém é o argumento do ADR-0004: nenhuma referência a um tipo de espaço
concreto. Trocar as regras de um tipo, ou acrescentar um quarto, não toca uma linha daqui. Um teste
lê este próprio arquivo e reprova se um nome de tipo aparecer.

O relógio também não está aqui. O instante atual chega pelo comando, o que torna "24h de
antecedência" uma comparação entre dois valores recebidos — testável com datas fixas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from agendalab.domain.entities.booking import Booking
from agendalab.domain.errors import (
    CapacityExceeded,
    InactiveSpace,
    InvalidTimeSlot,
    ScheduleConflict,
    SpaceNotFound,
)
from agendalab.domain.events.booking_events import BookingRequested
from agendalab.domain.policies.booking_policy import BookingRequest, PolicyContext
from agendalab.domain.policies.registry import policy_for

if TYPE_CHECKING:
    from agendalab.application.dto import RequestBookingCommand
    from agendalab.domain.entities.space import Space
    from agendalab.domain.events.publisher import EventPublisher
    from agendalab.domain.repositories import BookingRepository, SpaceRepository


class RequestBooking:
    def __init__(
        self,
        spaces: SpaceRepository,
        bookings: BookingRepository,
        publisher: EventPublisher,
    ) -> None:
        self._spaces = spaces
        self._bookings = bookings
        self._publisher = publisher

    def execute(self, command: RequestBookingCommand) -> Booking:
        """A reserva criada, no status que a política determinou.

        A ordem das verificações é a do UC-04 e não é arbitrária: as baratas e locais vêm antes das
        que consultam o repositório, e a política — a mais cara, porque precisa das reservas da
        semana — vem por último. Quem informa participantes demais descobre isso sem que o banco
        seja consultado duas vezes.
        """
        space = self._spaces.find_by_code(command.space_code)
        if space is None:
            raise SpaceNotFound(command.space_code)

        if command.slot.start_at <= command.now:
            # RN-04. A RN-03 (início < fim) já veio garantida na construção do `TimeSlot`.
            raise InvalidTimeSlot(
                f"A reserva precisa começar no futuro: "
                f"{command.slot.start_at:%d/%m/%Y %H:%M} não vem depois de "
                f"{command.now:%d/%m/%Y %H:%M}.",
                "RN-04",
            )

        if not space.active:
            raise InactiveSpace(space.code)  # RN-05

        if command.attendees > space.capacity:
            raise CapacityExceeded(space.code, command.attendees, space.capacity)  # RN-06

        if self._bookings.find_active_overlapping(space.code, command.slot):
            # RN-01 e RN-02 — o que conta como sobreposição é do `TimeSlot`, não daqui.
            raise ScheduleConflict(space.code, command.slot.start_at, command.slot.end_at)

        policy = policy_for(space.kind)
        policy.validate(  # RN-07 a RN-10 — levanta `PolicyViolation` se recusar
            BookingRequest(
                space_code=space.code,
                requester_id=command.requester_id,
                slot=command.slot,
                purpose=command.purpose,
                attendees=command.attendees,
            ),
            PolicyContext(
                now=command.now,
                space=space,
                requester_week_bookings=self._reservas_da_semana_no_mesmo_tipo(command, space),
            ),
        )

        booking = Booking(
            id=uuid4(),
            space_code=space.code,
            requester_id=command.requester_id,
            slot=command.slot,
            purpose=command.purpose,
            attendees=command.attendees,
            status=policy.initial_status(),  # RN-07 — quem decide é a política
            created_at=command.now,
        )
        self._bookings.add(booking)
        self._publisher.publish(  # RN-15
            BookingRequested(
                booking_id=booking.id,
                space_code=booking.space_code,
                requester_id=booking.requester_id,
                occurred_at=command.now,
            )
        )
        return booking

    def _reservas_da_semana_no_mesmo_tipo(
        self, command: RequestBookingCommand, space: Space
    ) -> list[Booking]:
        """Insumo do `PolicyContext` — as reservas ativas do solicitante na semana da solicitação,
        restritas a espaços do mesmo tipo do que está sendo pedido.

        O filtro por tipo é feito aqui porque não há outro lugar possível: a RN-08 conta apenas
        horas do mesmo tipo de espaço, `Booking` guarda `space_code` e não o tipo, e uma política
        que consultasse repositório deixaria de ser uma função pura sobre o que recebe.

        A semana de referência é a do **início da reserva solicitada**, não a do instante atual:
        quem reserva com duas semanas de antecedência consome o teto da semana em que vai usar o
        espaço.

        Cada código distinto é resolvido uma vez só. São poucos por construção — o próprio teto
        semanal limita quantas reservas cabem aqui.
        """
        da_semana = self._bookings.find_active_by_requester_in_week(
            command.requester_id, command.slot.start_at
        )
        codigos_do_mesmo_tipo = {
            codigo
            for codigo in {reserva.space_code for reserva in da_semana}
            if self._mesmo_tipo(codigo, space)
        }
        return [r for r in da_semana if r.space_code in codigos_do_mesmo_tipo]

    def _mesmo_tipo(self, codigo: str, space: Space) -> bool:
        """Um espaço que não existe mais não tem tipo para comparar, e fica de fora."""
        if codigo == space.code:
            return True
        outro = self._spaces.find_by_code(codigo)
        return outro is not None and outro.kind is space.kind
