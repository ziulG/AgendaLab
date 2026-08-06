"""`SqlAlchemySpaceRepository` contra SQLite.

A bateria é **a mesma** que a dupla em memória passa — herdada de `SpaceRepositoryContract`. Essa
identidade é o ponto: os casos de uso são testados contra a dupla e rodam contra esta implementação,
e enquanto as duas passarem na mesma bateria essa troca é segura.

Aqui embaixo ficam apenas as afirmações que só fazem sentido contra um banco de verdade.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.domain.errors import DuplicateSpaceCode
from agendalab.infrastructure.persistence.database import session_factory
from agendalab.infrastructure.persistence.models import SpaceModel
from agendalab.infrastructure.persistence.sqlalchemy_repositories import (
    SqlAlchemySpaceRepository,
)
from tests.contracts.space_repository_contract import SALA, SpaceRepositoryContract


class TestSqlAlchemySpaceRepository(SpaceRepositoryContract):
    @pytest.fixture
    def spaces(self, session: Session) -> SqlAlchemySpaceRepository:
        return SqlAlchemySpaceRepository(session)

    # --- o que só o banco real prova -----------------------------------------------------------

    def test_o_repositorio_devolve_entidade_de_dominio(
        self, spaces: SqlAlchemySpaceRepository
    ) -> None:
        """O critério do ADR-0003: o modelo ORM não vaza para fora do repositório."""
        spaces.add(SALA)

        encontrado = spaces.find_by_code(SALA.code)
        assert type(encontrado) is Space
        assert all(type(e) is Space for e in spaces.list_all())

    def test_o_espaco_sobrevive_ao_fim_da_sessao(
        self, spaces: SqlAlchemySpaceRepository, session: Session, engine: Engine
    ) -> None:
        """Persistir é isto: gravar, encerrar a sessão, abrir outra e o dado continuar lá."""
        spaces.add(SALA)
        session.commit()
        session.close()

        with session_factory(engine)() as outra:
            assert SqlAlchemySpaceRepository(outra).find_by_code(SALA.code) == SALA

    def test_codigo_duplicado_e_rejeitado_pelo_proprio_banco(
        self, spaces: SqlAlchemySpaceRepository, session: Session
    ) -> None:
        """RN-16 no nível do esquema: `code` é chave primária, e é a restrição que acusa.

        O repositório não consulta antes de inserir — traduz a violação que o banco reporta. Não há
        janela entre verificar e gravar.
        """
        spaces.add(SALA)
        with pytest.raises(DuplicateSpaceCode):
            spaces.add(Space(code=SALA.code, name="Outro", kind=SpaceKind.LAB, capacity=10))

        # A sessão continua utilizável depois da recusa — sem isso, a requisição inteira morreria.
        assert spaces.find_by_code(SALA.code) == SALA

    def test_a_linha_gravada_tem_as_colunas_do_diagrama(
        self, spaces: SqlAlchemySpaceRepository, session: Session
    ) -> None:
        """Olhando o modelo por baixo do repositório: é a tabela do diagrama ER, não a entidade."""
        spaces.add(SALA)

        linha = session.scalars(select(SpaceModel).where(SpaceModel.code == SALA.code)).one()
        assert (linha.code, linha.name, linha.kind, linha.capacity, linha.active) == (
            SALA.code,
            SALA.name,
            SALA.kind.value,  # texto na coluna, enum na entidade
            SALA.capacity,
            SALA.active,
        )
