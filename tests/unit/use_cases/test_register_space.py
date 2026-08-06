"""UC-01 — cadastrar espaço.

O caso de uso não implementa a RN-16: ele monta a entidade e entrega ao repositório, que é quem
promete recusar código repetido. O que os testes daqui verificam é que essa recusa **atravessa** o
caso de uso em vez de ser engolida — e que nada de regra de negócio foi reimplementado no caminho.

Tudo roda contra `InMemorySpaceRepository`. Nenhum banco, conforme o ADR-0009.
"""

from __future__ import annotations

import pytest

from agendalab.application.dto import RegisterSpaceCommand
from agendalab.application.use_cases.register_space import RegisterSpace
from agendalab.domain.entities.space import SpaceKind
from agendalab.domain.errors import DuplicateSpaceCode
from tests.doubles.in_memory_repositories import InMemorySpaceRepository


def comando(
    code: str = "LAB-01",
    kind: SpaceKind = SpaceKind.LAB,
    capacity: int = 30,
) -> RegisterSpaceCommand:
    return RegisterSpaceCommand(
        code=code,
        name="Laboratório de Redes",
        kind=kind,
        capacity=capacity,
    )


def caso_de_uso() -> tuple[RegisterSpace, InMemorySpaceRepository]:
    """Devolve também o repositório: alguns testes precisam olhar o que foi guardado."""
    spaces = InMemorySpaceRepository()
    return RegisterSpace(spaces), spaces


# --- caminho feliz -----------------------------------------------------------------------------


def test_espaco_cadastrado_e_devolvido_com_os_dados_do_comando() -> None:
    cadastrar, _ = caso_de_uso()
    espaco = cadastrar.execute(comando(code="LAB-01", kind=SpaceKind.LAB, capacity=30))
    assert (espaco.code, espaco.name, espaco.kind, espaco.capacity) == (
        "LAB-01",
        "Laboratório de Redes",
        SpaceKind.LAB,
        30,
    )


def test_espaco_cadastrado_fica_recuperavel_no_repositorio() -> None:
    """Devolver a entidade não basta: o efeito do caso de uso é ela estar guardada."""
    cadastrar, spaces = caso_de_uso()
    espaco = cadastrar.execute(comando(code="SALA-01"))
    assert spaces.find_by_code("SALA-01") is espaco


def test_espaco_nasce_ativo() -> None:
    """UC-01 — "o espaço é persistido como ativo". O comando nem oferece o campo."""
    cadastrar, _ = caso_de_uso()
    assert cadastrar.execute(comando()).active is True


def test_cadastros_sucessivos_convivem() -> None:
    cadastrar, spaces = caso_de_uso()
    cadastrar.execute(comando(code="LAB-01"))
    cadastrar.execute(comando(code="LAB-02"))
    assert sorted(e.code for e in spaces.list_all()) == ["LAB-01", "LAB-02"]


# --- RN-16: código único -----------------------------------------------------------------------


def test_codigo_repetido_e_recusado() -> None:
    """RN-16 — a recusa nasce no repositório e o caso de uso deixa passar, sem traduzir."""
    cadastrar, _ = caso_de_uso()
    cadastrar.execute(comando(code="LAB-01"))
    with pytest.raises(DuplicateSpaceCode) as erro:
        cadastrar.execute(comando(code="LAB-01", kind=SpaceKind.CLASSROOM))
    assert erro.value.rule == "RN-16"


def test_codigo_repetido_nao_substitui_o_espaco_existente() -> None:
    """A recusa é total: o segundo cadastro não deixa rastro no repositório."""
    cadastrar, spaces = caso_de_uso()
    cadastrar.execute(comando(code="LAB-01", kind=SpaceKind.LAB, capacity=30))
    with pytest.raises(DuplicateSpaceCode):
        cadastrar.execute(comando(code="LAB-01", kind=SpaceKind.AUDITORIUM, capacity=200))
    guardado = spaces.find_by_code("LAB-01")
    assert guardado is not None
    assert (guardado.kind, guardado.capacity) == (SpaceKind.LAB, 30)


# --- invariantes da entidade -------------------------------------------------------------------


@pytest.mark.parametrize("capacidade", [0, -1, -40])
def test_capacidade_nao_positiva_e_recusada(capacidade: int) -> None:
    """`ValueError`, e não `DomainError`: a §7.2 não traduz este caso porque a validação da borda
    o recusa antes de chegar aqui. A invariante vive em `Space`, não no caso de uso."""
    cadastrar, _ = caso_de_uso()
    with pytest.raises(ValueError, match="capacidade"):
        cadastrar.execute(comando(capacity=capacidade))


def test_codigo_vazio_e_recusado() -> None:
    cadastrar, _ = caso_de_uso()
    with pytest.raises(ValueError, match="código"):
        cadastrar.execute(comando(code="   "))


def test_espaco_recusado_pela_invariante_nao_e_guardado() -> None:
    """A entidade nem chega a ser construída, então o repositório continua vazio."""
    cadastrar, spaces = caso_de_uso()
    with pytest.raises(ValueError):
        cadastrar.execute(comando(code="LAB-01", capacity=0))
    assert spaces.list_all() == []
