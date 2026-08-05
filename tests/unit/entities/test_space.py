"""`Space` — os três tipos de espaço e as invariantes da §4.3 da especificação."""

from __future__ import annotations

import pytest

from agendalab.domain.entities.space import Space, SpaceKind


def test_os_tres_tipos_de_espaco_existem() -> None:
    """Glossário — cada tipo determina a política aplicável (RN-08 a RN-10)."""
    assert [tipo.value for tipo in SpaceKind] == ["CLASSROOM", "LAB", "AUDITORIUM"]


def test_espaco_nasce_ativo() -> None:
    espaco = Space(code="LAB-01", name="Laboratório de Redes", kind=SpaceKind.LAB, capacity=30)
    assert espaco.active is True


def test_espaco_guarda_os_campos_da_especificacao() -> None:
    espaco = Space(
        code="AUD-01",
        name="Auditório Central",
        kind=SpaceKind.AUDITORIUM,
        capacity=200,
        active=False,
    )
    assert (espaco.code, espaco.name, espaco.kind) == ("AUD-01", "Auditório Central", SpaceKind.AUDITORIUM)
    assert (espaco.capacity, espaco.active) == (200, False)


# --- Invariantes da §4.3 ---------------------------------------------------------------------
#
# Violá-las é erro de programação, não regra de negócio: a §7.2 não tem tradução HTTP para elas,
# e a validação da borda (task 11) recusa a requisição antes de chegar aqui. Daí `ValueError`,
# e não um erro de domínio — a hierarquia da §7.2 tem exatamente 11 subclasses.


@pytest.mark.parametrize("capacidade", [0, -1])
def test_capacidade_precisa_ser_positiva(capacidade: int) -> None:
    """§4.3 — capacidade é o máximo de ocupantes; zero ou negativo não descreve espaço algum."""
    with pytest.raises(ValueError, match="capacidade"):
        Space(code="SALA-01", name="Sala 1", kind=SpaceKind.CLASSROOM, capacity=capacidade)


@pytest.mark.parametrize("codigo", ["", "   "])
def test_codigo_nao_pode_ser_vazio(codigo: str) -> None:
    """§4.3 — o código é o identificador natural do espaço e a chave usada nas rotas."""
    with pytest.raises(ValueError, match="código"):
        Space(code=codigo, name="Sala 1", kind=SpaceKind.CLASSROOM, capacity=40)
