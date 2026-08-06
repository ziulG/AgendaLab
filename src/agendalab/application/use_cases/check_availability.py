"""UC-03 — consultar a agenda de um espaço num dia.

Devolve o que está **ocupado**, não o que está livre. A diferença é deliberada: "faixa livre"
depende do horário de funcionamento e da granularidade que o cliente quer exibir, e nenhum dos dois
é regra de negócio deste sistema. Entregar as reservas ativas do dia deixa essa leitura para quem
consome a API, sem inventar um conceito que a especificação não tem.

Este é o primeiro caso de uso com duas dependências, e ele mostra por que a ordem importa: valida a
existência do espaço **antes** de consultar a agenda. Um código inexistente devolveria lista vazia
pelo caminho contrário — indistinguível de um espaço realmente livre.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agendalab.domain.errors import SpaceNotFound

if TYPE_CHECKING:
    from agendalab.application.dto import CheckAvailabilityQuery
    from agendalab.domain.entities.booking import Booking
    from agendalab.domain.repositories import BookingRepository, SpaceRepository


class CheckAvailability:
    def __init__(self, spaces: SpaceRepository, bookings: BookingRepository) -> None:
        self._spaces = spaces
        self._bookings = bookings

    def execute(self, query: CheckAvailabilityQuery) -> list[Booking]:
        """As reservas ativas do dia, em ordem cronológica. `SpaceNotFound` se o espaço não existir.

        Espaço inativo tem agenda: a RN-05 impede criar reserva nele, não consultar as que já
        existem. Quais reservas contam como ativas é a RN-01, e quem a aplica é o repositório.

        A ordenação é por `start_at` apenas — nunca pela reserva inteira. `Booking` não é ordenável,
        e um desempate por comparação de objetos levantaria `TypeError` no primeiro par de reservas
        que começasse no mesmo instante. `sorted` é estável, então o empate preserva a ordem de
        origem.
        """
        if self._spaces.find_by_code(query.space_code) is None:
            raise SpaceNotFound(query.space_code)

        agenda = self._bookings.list_by_space_and_date(query.space_code, query.day)
        return sorted(agenda, key=lambda booking: booking.slot.start_at)
