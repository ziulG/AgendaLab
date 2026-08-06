"""`InMemoryBookingRepository` — a dupla que sustenta os testes das tasks 07 a 09.

As três consultas carregam regra de negócio de verdade: RN-01 define o que é reserva ativa, RN-02
define o que é sobreposição e RN-08 define o que é "a mesma semana". Errar qualquer uma delas aqui
faria os casos de uso passarem contra um comportamento que a task 10 não reproduz.

Esses casos vivem em `BookingRepositoryContract`, herdado abaixo e compartilhado com a implementação
SQLAlchemy — o que torna a divergência entre as duas impossível de passar despercebida. Aqui ficam
apenas as afirmações que só uma dupla em memória pode cumprir.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from agendalab.domain.entities.booking import BookingStatus
from tests.contracts.booking_repository_contract import (
    ESPACO,
    QUINTA,
    BookingRepositoryContract,
    intervalo,
    reserva,
)
from tests.doubles.in_memory_repositories import InMemoryBookingRepository


class TestInMemoryBookingRepository(BookingRepositoryContract):
    @pytest.fixture
    def bookings(self) -> InMemoryBookingRepository:
        return InMemoryBookingRepository()

    # --- o que é específico da dupla -----------------------------------------------------------

    def test_a_dupla_guarda_a_propria_instancia(
        self, bookings: InMemoryBookingRepository
    ) -> None:
        """Sem cópia — e é justamente isso que torna `update` invisível contra ela, motivo pelo qual
        existe a `TrackingBookingRepository` da task 09."""
        guardada = reserva(intervalo(QUINTA, 14, 16))
        bookings.add(guardada)
        assert bookings.find_by_id(guardada.id) is guardada

    def test_mutar_a_entidade_ja_a_muta_no_repositorio(
        self, bookings: InMemoryBookingRepository
    ) -> None:
        """A consequência direta da linha acima, dita em voz alta: contra esta dupla, transicionar
        a entidade basta. Contra o SQLAlchemy da task 10, não — lá é preciso chamar `update`."""
        guardada = reserva(intervalo(QUINTA, 14, 16), status=BookingStatus.PENDING)
        bookings.add(guardada)

        guardada.status = BookingStatus.APPROVED  # sem `update`

        encontrada = bookings.find_by_id(guardada.id)
        assert encontrada is not None
        assert encontrada.status is BookingStatus.APPROVED

    def test_a_semana_sai_de_iso_week_e_nao_de_uma_copia_da_regra(
        self, bookings: InMemoryBookingRepository
    ) -> None:
        """A dupla delega a `TimeSlot.iso_week()` em vez de recalcular a semana — reimplementar a
        regra aqui seria a forma mais direta de ela divergir da implementação real."""
        virada_do_ano = reserva(
            intervalo(datetime(2025, 12, 31, 8).date(), 8, 10)
        )  # 31/12/2025 pertence à semana 1 de 2026
        bookings.add(virada_do_ano)

        encontradas = bookings.find_active_by_requester_in_week(
            virada_do_ano.requester_id, datetime(2026, 1, 2, 9)
        )
        assert [r.id for r in encontradas] == [virada_do_ano.id]

    def test_a_dupla_nao_toca_disco(self, bookings: InMemoryBookingRepository) -> None:
        """A razão de ela existir: a camada de aplicação inteira roda sem banco (ADR-0009)."""
        bookings.add(reserva(intervalo(QUINTA, 14, 16)))
        assert bookings.list_by_space_and_date(ESPACO, QUINTA) != []
