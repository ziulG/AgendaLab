"""`InMemorySpaceRepository` — a dupla que as tasks 07 a 09 vão usar.

Testar uma dupla parece redundante até se notar o que ela sustenta: se ela estiver errada, os
testes dos casos de uso passam contra um comportamento que a implementação real não tem, e o erro
só aparece na task 10.
"""

from __future__ import annotations

import pytest

from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.domain.errors import DuplicateSpaceCode
from tests.doubles.in_memory_repositories import InMemorySpaceRepository


def espaco(code: str, kind: SpaceKind = SpaceKind.CLASSROOM, active: bool = True) -> Space:
    return Space(code=code, name=f"Espaço {code}", kind=kind, capacity=40, active=active)


SALA = espaco("SALA-01", SpaceKind.CLASSROOM)
LABORATORIO = espaco("LAB-01", SpaceKind.LAB)
LAB_DESATIVADO = espaco("LAB-02", SpaceKind.LAB, active=False)
AUDITORIO = espaco("AUD-01", SpaceKind.AUDITORIUM, active=False)


def repositorio(*espacos: Space) -> InMemorySpaceRepository:
    repo = InMemorySpaceRepository()
    for e in espacos:
        repo.add(e)
    return repo


def codigos(espacos: list[Space]) -> list[str]:
    """`Space` é dataclass mutável e não é hashável — comparar por código evita a questão."""
    return sorted(e.code for e in espacos)


# --- add -------------------------------------------------------------------------------------


def test_espaco_adicionado_pode_ser_encontrado() -> None:
    repo = repositorio(SALA)
    assert repo.find_by_code("SALA-01") is SALA


def test_codigo_repetido_e_recusado() -> None:
    """RN-16 — o código de um espaço é único no sistema."""
    repo = repositorio(SALA)
    with pytest.raises(DuplicateSpaceCode) as erro:
        repo.add(espaco("SALA-01", SpaceKind.LAB))
    assert erro.value.rule == "RN-16"


def test_codigo_repetido_nao_substitui_o_existente() -> None:
    """A recusa precisa ser total: o espaço original continua lá, intacto."""
    repo = repositorio(SALA)
    with pytest.raises(DuplicateSpaceCode):
        repo.add(espaco("SALA-01", SpaceKind.LAB))
    guardado = repo.find_by_code("SALA-01")
    assert guardado is not None
    assert guardado.kind is SpaceKind.CLASSROOM


# --- find_by_code ----------------------------------------------------------------------------


def test_buscar_codigo_inexistente_devolve_nulo() -> None:
    """A interface devolve `Space | None`; quem levanta `SpaceNotFound` é o caso de uso."""
    assert repositorio(SALA).find_by_code("NAO-EXISTE") is None


def test_buscar_em_repositorio_vazio_devolve_nulo() -> None:
    assert InMemorySpaceRepository().find_by_code("SALA-01") is None


# --- list_all --------------------------------------------------------------------------------


def test_listar_sem_filtro_devolve_tudo() -> None:
    repo = repositorio(SALA, LABORATORIO, AUDITORIO)
    assert codigos(repo.list_all()) == ["AUD-01", "LAB-01", "SALA-01"]


def test_listar_filtrando_por_tipo() -> None:
    repo = repositorio(SALA, LABORATORIO, LAB_DESATIVADO, AUDITORIO)
    assert codigos(repo.list_all(kind=SpaceKind.LAB)) == ["LAB-01", "LAB-02"]


def test_listar_filtrando_por_situacao() -> None:
    repo = repositorio(SALA, LABORATORIO, LAB_DESATIVADO, AUDITORIO)
    assert codigos(repo.list_all(active=True)) == ["LAB-01", "SALA-01"]
    assert codigos(repo.list_all(active=False)) == ["AUD-01", "LAB-02"]


def test_listar_combinando_os_dois_filtros() -> None:
    """Os filtros são independentes e se somam."""
    repo = repositorio(SALA, LABORATORIO, LAB_DESATIVADO, AUDITORIO)
    assert codigos(repo.list_all(kind=SpaceKind.LAB, active=False)) == ["LAB-02"]


def test_filtro_que_nao_casa_devolve_lista_vazia() -> None:
    repo = repositorio(SALA)
    assert repo.list_all(kind=SpaceKind.AUDITORIUM) == []


def test_listar_repositorio_vazio_devolve_lista_vazia() -> None:
    assert InMemorySpaceRepository().list_all() == []


def test_nulo_no_filtro_significa_nao_filtrar() -> None:
    """`None` não é "situação nula": é ausência de filtro, e a assinatura usa isso como padrão."""
    repo = repositorio(SALA, LAB_DESATIVADO)
    assert codigos(repo.list_all(kind=None, active=None)) == ["LAB-02", "SALA-01"]
