"""As duplas satisfazem os contratos declarados no domínio.

É o teste que dá sentido a testar duplas. Sem ele, uma dupla poderia divergir da interface e as
tasks 07 a 09 passariam contra um contrato que a implementação SQLAlchemy da task 10 não
implementa — e a divergência só apareceria lá, com o dobro de código para investigar.
"""

from __future__ import annotations

import inspect

import pytest

from agendalab.domain.repositories import BookingRepository, SpaceRepository
from tests.doubles.in_memory_repositories import (
    InMemoryBookingRepository,
    InMemorySpaceRepository,
)

CONTRATOS = [
    (SpaceRepository, InMemorySpaceRepository),
    (BookingRepository, InMemoryBookingRepository),
]
IDS = [contrato.__name__ for contrato, _ in CONTRATOS]


@pytest.mark.parametrize(("contrato", "dupla"), CONTRATOS, ids=IDS)
def test_a_dupla_satisfaz_o_protocolo(contrato: type, dupla: type) -> None:
    """A dupla não herda do `Protocol`: a conformidade é estrutural, e é verificada aqui."""
    assert isinstance(dupla(), contrato)


@pytest.mark.parametrize(("contrato", "dupla"), CONTRATOS, ids=IDS)
def test_as_assinaturas_batem_com_o_contrato(contrato: type, dupla: type) -> None:
    """`isinstance` num `Protocol` só confere que o método existe — os parâmetros, não.

    Uma dupla com `list_all(self)` passaria pela verificação estrutural e quebraria no primeiro
    caso de uso que filtrasse por tipo.
    """
    for nome, declarado in inspect.getmembers(contrato, inspect.isfunction):
        if nome.startswith("_"):
            continue
        implementado = getattr(dupla, nome)
        assert inspect.signature(implementado) == inspect.signature(declarado), (
            f"{dupla.__name__}.{nome} diverge da assinatura de {contrato.__name__}"
        )
