"""`SqlAlchemyBookingRepository` contra SQLite.

A mesma bateria da dupla em memória, herdada de `BookingRepositoryContract`. É onde as fórmulas da
RN-01, RN-02 e RN-08 são reescritas em SQL, e onde um `<=` no lugar de um `<` produziria reserva
dupla sem que nenhum teste de domínio percebesse — as fronteiras estão todas no contrato.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.infrastructure.persistence.database import session_factory
from agendalab.infrastructure.persistence.models import BookingModel
from agendalab.infrastructure.persistence.sqlalchemy_repositories import (
    SqlAlchemyBookingRepository,
)
from tests.contracts.booking_repository_contract import (
    ESPACO,
    QUINTA,
    BookingRepositoryContract,
    intervalo,
    reserva,
)


@pytest.mark.usefixtures("espacos_do_contrato")
class TestSqlAlchemyBookingRepository(BookingRepositoryContract):
    @pytest.fixture
    def bookings(self, session: Session) -> SqlAlchemyBookingRepository:
        return SqlAlchemyBookingRepository(session)

    # --- o que só o banco real prova -----------------------------------------------------------

    def test_o_repositorio_devolve_entidade_de_dominio(
        self, bookings: SqlAlchemyBookingRepository
    ) -> None:
        """O critério do ADR-0003: `BookingModel` não vaza para fora do repositório."""
        guardada = reserva(intervalo(QUINTA, 14, 16))
        bookings.add(guardada)

        assert type(bookings.find_by_id(guardada.id)) is Booking
        assert all(
            type(r) is Booking for r in bookings.list_by_space_and_date(ESPACO, QUINTA)
        )

    def test_a_reserva_sobrevive_ao_fim_da_sessao(
        self, bookings: SqlAlchemyBookingRepository, session: Session, engine: Engine
    ) -> None:
        guardada = reserva(intervalo(QUINTA, 14, 16))
        bookings.add(guardada)
        session.commit()
        session.close()

        with session_factory(engine)() as outra:
            assert SqlAlchemyBookingRepository(outra).find_by_id(guardada.id) == guardada

    def test_mutar_a_entidade_sem_update_nao_chega_ao_banco(
        self, bookings: SqlAlchemyBookingRepository, session: Session, engine: Engine
    ) -> None:
        """O oposto exato da dupla em memória, e a razão de a `TrackingBookingRepository` existir.

        Aqui a entidade é reconstruída a partir da linha: mutá-la não muta nada no banco. Um caso de
        uso que esquecesse `update` funcionaria em todos os testes unitários e perderia a transição
        em produção.
        """
        guardada = reserva(intervalo(QUINTA, 14, 16), status=BookingStatus.PENDING)
        bookings.add(guardada)
        session.commit()

        carregada = bookings.find_by_id(guardada.id)
        assert carregada is not None
        carregada.status = BookingStatus.APPROVED  # sem `update`
        session.commit()
        session.close()

        with session_factory(engine)() as outra:
            relida = SqlAlchemyBookingRepository(outra).find_by_id(guardada.id)
            assert relida is not None
            assert relida.status is BookingStatus.PENDING

    def test_o_intervalo_vira_duas_colunas(
        self, bookings: SqlAlchemyBookingRepository, session: Session
    ) -> None:
        """`TimeSlot` é objeto de valor no domínio e duas colunas na tabela — nenhum dos dois lados
        cedeu ao outro, que é o argumento do ADR-0003 para modelos separados."""
        slot = intervalo(QUINTA, 14, 16)
        guardada = reserva(slot)
        bookings.add(guardada)

        linha = session.scalars(
            select(BookingModel).where(BookingModel.id == guardada.id)
        ).one()
        assert (linha.start_at, linha.end_at) == (slot.start_at, slot.end_at)

    def test_a_reserva_relida_aceita_as_transicoes_do_seu_estado(
        self, bookings: SqlAlchemyBookingRepository, session: Session, engine: Engine
    ) -> None:
        """O State reconstruído a partir do status persistido.

        `Booking._state` deriva o objeto de estado do `status`, então uma reserva vinda do banco
        precisa se comportar exatamente como uma criada em memória — inclusive recusando o que a
        tabela da §5.5 recusa.
        """
        from agendalab.domain.actor import Actor, Role
        from agendalab.domain.errors import InvalidStateTransition

        guardada = reserva(intervalo(QUINTA, 14, 16), status=BookingStatus.PENDING)
        bookings.add(guardada)
        session.commit()
        session.close()

        gestor = Actor(user_id="1998007766", role=Role.MANAGER)
        with session_factory(engine)() as outra:
            repo = SqlAlchemyBookingRepository(outra)
            relida = repo.find_by_id(guardada.id)
            assert relida is not None

            relida.approve(gestor, guardada.created_at)
            repo.update(relida)
            assert relida.status is BookingStatus.APPROVED

            # E, aprovada, recusa uma segunda aprovação — como recusaria em memória.
            with pytest.raises(InvalidStateTransition):
                relida.approve(gestor, guardada.created_at)
