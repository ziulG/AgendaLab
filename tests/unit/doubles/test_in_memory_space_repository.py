"""`InMemorySpaceRepository` — a dupla que as tasks 07 a 09 usam.

Testar uma dupla parece redundante até se notar o que ela sustenta: se ela estiver errada, os
testes dos casos de uso passam contra um comportamento que a implementação real não tem.

O grosso dos casos vive em `SpaceRepositoryContract`, herdado logo abaixo e compartilhado com a
implementação SQLAlchemy da task 10. O que sobra neste arquivo é o que só vale para uma dupla em
memória — e que, por isso mesmo, não poderia estar no contrato.
"""

from __future__ import annotations

import pytest

from agendalab.domain.entities.space import SpaceKind
from tests.contracts.space_repository_contract import SALA, SpaceRepositoryContract, espaco
from tests.doubles.in_memory_repositories import InMemorySpaceRepository


class TestInMemorySpaceRepository(SpaceRepositoryContract):
    @pytest.fixture
    def spaces(self) -> InMemorySpaceRepository:
        return InMemorySpaceRepository()

    # --- o que é específico da dupla -----------------------------------------------------------

    def test_a_dupla_guarda_a_propria_instancia(self, spaces: InMemorySpaceRepository) -> None:
        """Sem cópia, deliberadamente: é o comportamento esperado de um repositório em memória, e a
        separação real entre modelo de persistência e domínio é da task 10.

        O contrato compartilhado compara por valor justamente porque a implementação SQLAlchemy
        reconstrói a entidade e **não** pode satisfazer esta afirmação.
        """
        spaces.add(SALA)
        assert spaces.find_by_code("SALA-01") is SALA

    def test_a_dupla_nao_toca_disco(self, spaces: InMemorySpaceRepository) -> None:
        """A razão de ela existir: a camada de aplicação inteira roda sem banco (ADR-0009)."""
        spaces.add(espaco("X-01", SpaceKind.LAB))
        assert spaces.list_all() != []
