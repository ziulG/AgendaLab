"""As implementações reais de `SpaceRepository` e `BookingRepository`.

Este arquivo é o outro lado das interfaces que o domínio declarou, e nada aqui é importado por ele —
a seta aponta para dentro. A prova de que a inversão não é decorativa está em
`tests/integration/test_casos_de_uso_contra_o_banco.py`: os sete casos de uso, escritos e testados
contra duplas em memória, funcionam contra estas classes sem uma linha alterada.

**Nenhum método aqui commita.** O limite transacional é a requisição HTTP, e quem fecha a transação
é a dependência do FastAPI da task 11 — `commit` no sucesso, `rollback` na exceção (ADR-0003). Um
`commit` escondido dentro de um repositório tornaria impossível desfazer uma operação composta.

As consultas repetem em SQL as fórmulas que o domínio define, e é o único lugar do sistema onde elas
aparecem duas vezes. A duplicação é inevitável — um `WHERE` não chama `TimeSlot.overlaps()` linha a
linha — e é por isso que a bateria de contrato de `tests/contracts/` roda contra as duas
implementações: é ela que impede que as duas versões da mesma regra divirjam.

Os repositórios **sempre devolvem entidades de domínio**. `SpaceModel` e `BookingModel` não
atravessam esta fronteira.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from agendalab.domain.errors import DuplicateSpaceCode
from agendalab.domain.states.concrete_states import ACTIVE_STATUSES
from agendalab.infrastructure.persistence.mappers import (
    apply_booking,
    to_booking,
    to_booking_model,
    to_space,
    to_space_model,
)
from agendalab.infrastructure.persistence.models import BookingModel, SpaceModel

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    from agendalab.domain.entities.booking import Booking
    from agendalab.domain.entities.space import Space, SpaceKind
    from agendalab.domain.value_objects.time_slot import TimeSlot

# RN-01 em forma de `IN (...)`. Derivado dos próprios estados, nunca escrito à mão: quem decide se
# uma reserva ocupa o horário é `BookingState.occupies_slot()`, e uma lista literal aqui poderia
# divergir dele no dia em que um estado novo aparecesse.
STATUS_ATIVOS = [status.value for status in ACTIVE_STATUSES]


class SqlAlchemySpaceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, space: Space) -> None:
        """Guarda o espaço. Levanta `DuplicateSpaceCode` se o código já existir (RN-16).

        O `flush` é o que faz a violação aparecer **agora**, e não lá no commit: sem ele, um código
        repetido só estouraria no fim da requisição, longe da operação que o causou e já sem como
        devolver o erro certo ao cliente.

        Quem detecta a repetição é a chave primária, não uma consulta prévia — assim não existe
        janela entre verificar e gravar.

        A inserção acontece dentro de um `SAVEPOINT`. Depois de uma falha de integridade a sessão
        fica inutilizável até que algo seja desfeito, e um `rollback` comum desfaria a **transação
        inteira** — no meio de uma requisição que cadastrasse vários espaços, um código repetido no
        último apagaria todos os anteriores. O savepoint desfaz só esta inserção.
        """
        try:
            with self._session.begin_nested():
                self._session.add(to_space_model(space))
        except IntegrityError as erro:
            raise DuplicateSpaceCode(space.code) from erro

    def find_by_code(self, code: str) -> Space | None:
        """O espaço, ou `None`. Traduzir a ausência em `SpaceNotFound` é do caso de uso."""
        model = self._session.get(SpaceModel, code)
        return to_space(model) if model is not None else None

    def list_all(self, kind: SpaceKind | None = None, active: bool | None = None) -> list[Space]:
        """Os espaços que casam com os filtros. `None` significa não filtrar por aquele critério."""
        consulta = select(SpaceModel)
        if kind is not None:
            consulta = consulta.where(SpaceModel.kind == kind.value)
        if active is not None:
            consulta = consulta.where(SpaceModel.active.is_(active))
        return [to_space(m) for m in self._session.scalars(consulta)]


class SqlAlchemyBookingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, booking: Booking) -> None:
        self._session.add(to_booking_model(booking))
        self._session.flush()

    def update(self, booking: Booking) -> None:
        """Grava o estado atual de uma reserva já existente.

        Carrega a linha e aplica os campos sobre ela, em vez de inserir um modelo novo com o mesmo
        `id`: é a diferença entre um `UPDATE` e um conflito de chave primária.

        Diferente da dupla em memória, aqui esta chamada é indispensável. A entidade devolvida por
        `find_by_id` é reconstruída a partir da linha e não está ligada a ela — mutá-la não muda
        nada no banco.
        """
        model = self._session.get(BookingModel, booking.id)
        if model is None:  # pragma: no cover — o caso de uso já garantiu que a reserva existe
            return
        apply_booking(model, booking)
        self._session.flush()

    def find_by_id(self, booking_id: UUID) -> Booking | None:
        """A reserva, ou `None`. Traduzir a ausência em `BookingNotFound` é do caso de uso."""
        model = self._session.get(BookingModel, booking_id)
        return to_booking(model) if model is not None else None

    def find_active_overlapping(self, space_code: str, slot: TimeSlot) -> list[Booking]:
        """Reservas ativas do espaço que se sobrepõem ao intervalo — RN-01 e RN-02.

        A condição é a mesma fórmula de `TimeSlot.overlaps`: `início_a < fim_b ∧ início_b < fim_a`.
        As desigualdades são **estritas**, e é isso que faz uma reserva das 8h às 10h conviver com
        outra das 10h às 12h. Trocar por `<=` produziria conflito onde a RN-02 não vê nenhum.
        """
        consulta = (
            select(BookingModel)
            .where(BookingModel.space_code == space_code)
            .where(BookingModel.status.in_(STATUS_ATIVOS))
            .where(BookingModel.start_at < slot.end_at)
            .where(BookingModel.end_at > slot.start_at)
        )
        return [to_booking(m) for m in self._session.scalars(consulta)]

    def find_active_by_requester_in_week(
        self, requester_id: str, reference: datetime
    ) -> list[Booking]:
        """Reservas ativas do solicitante na semana ISO de `reference` — insumo da RN-08.

        A semana vira um intervalo de datas calculado em Python. Poderia ser uma função de data do
        SQLite, mas `strftime('%W')` não é a semana ISO — difere na virada do ano, justamente onde
        `TimeSlot.iso_week` toma o cuidado de carregar o ano junto.

        O filtro é sobre `start_at`: a RN-08 conta "reservas cuja data de início cai na mesma
        semana", então uma reserva que atravesse a virada pertence à semana em que começa.
        """
        inicio, fim = _limites_da_semana(reference)
        consulta = (
            select(BookingModel)
            .where(BookingModel.requester_id == requester_id)
            .where(BookingModel.status.in_(STATUS_ATIVOS))
            .where(BookingModel.start_at >= inicio)
            .where(BookingModel.start_at < fim)
        )
        return [to_booking(m) for m in self._session.scalars(consulta)]

    def list_by_space_and_date(self, space_code: str, day: date) -> list[Booking]:
        """Reservas ativas do espaço naquele dia — a agenda que o UC-03 devolve.

        O dia vira um intervalo de meia-noite a meia-noite e a pergunta volta a ser sobreposição.
        Comparar apenas a data de início esconderia uma reserva das 22h às 2h da consulta do dia
        seguinte — justamente quando ela atrapalha quem procura horário livre pela manhã.
        """
        inicio = datetime.combine(day, time.min)
        fim = inicio + timedelta(days=1)
        consulta = (
            select(BookingModel)
            .where(BookingModel.space_code == space_code)
            .where(BookingModel.status.in_(STATUS_ATIVOS))
            .where(BookingModel.start_at < fim)
            .where(BookingModel.end_at > inicio)
        )
        return [to_booking(m) for m in self._session.scalars(consulta)]


def _limites_da_semana(reference: datetime) -> tuple[datetime, datetime]:
    """A segunda-feira 00:00 da semana ISO de `reference`, e a segunda seguinte.

    Fechado no início e aberto no fim, como todo intervalo do sistema: domingo 23:59 está dentro,
    segunda 00:00 já é a semana seguinte.
    """
    segunda = datetime.combine(reference.date() - timedelta(days=reference.weekday()), time.min)
    return segunda, segunda + timedelta(days=7)
