"""Fixtures dos testes que tocam banco.

O banco é um **arquivo** temporário, não `:memory:`. Custa alguns milissegundos e paga por eles: é o
que exercita `create_schema` de verdade e o que permite fechar a sessão, abrir outra e reler — que é
o significado da palavra "persistir". Com banco em memória, um repositório que nunca gravasse nada
passaria em quase todos os testes.

`tmp_path` é do pytest e some ao fim de cada teste, o que atende ao critério de banco temporário
apagado ao final sem nenhuma limpeza escrita à mão.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.infrastructure.persistence.database import (
    create_engine_for,
    create_schema,
    session_factory,
)
from agendalab.infrastructure.persistence.sqlalchemy_repositories import (
    SqlAlchemySpaceRepository,
)
from tests.contracts.booking_repository_contract import ESPACO, OUTRO_ESPACO


@pytest.fixture
def db_url(tmp_path: pytest.TempPathFactory) -> str:
    return f"sqlite:///{tmp_path}/agendalab.db"  # type: ignore[operator]


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    motor = create_engine_for(db_url)
    create_schema(motor)
    yield motor
    motor.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with session_factory(engine)() as sessao:
        yield sessao


@pytest.fixture
def espacos_do_contrato(session: Session) -> None:
    """Os espaços que as reservas do contrato referenciam.

    O contrato de `BookingRepository` fala apenas de reservas — na dupla em memória não há
    integridade referencial para satisfazer. Aqui há: `bookings.space_code` é chave estrangeira para
    `spaces.code`, e a restrição está ligada. Preparar o terreno é responsabilidade de quem
    implementa o contrato, não do contrato.
    """
    spaces = SqlAlchemySpaceRepository(session)
    for code in (ESPACO, OUTRO_ESPACO):
        spaces.add(
            Space(code=code, name=f"Espaço {code}", kind=SpaceKind.LAB, capacity=40, active=True)
        )
