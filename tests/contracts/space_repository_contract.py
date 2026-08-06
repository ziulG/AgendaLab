"""A bateria que toda implementação de `SpaceRepository` precisa passar.

Existem duas implementações do mesmo contrato — a dupla em memória da task 06 e a SQLAlchemy da
task 10 — e a camada de aplicação é testada contra a primeira mas roda contra a segunda. Se as duas
divergirem em qualquer detalhe, os testes de caso de uso passam contra um comportamento que a
produção não tem.

Esta classe é a defesa contra isso: os casos vivem num lugar só e cada implementação os herda.
Acrescentar um comportamento novo aqui obriga as duas a atendê-lo, na mesma execução do `pytest`.

O arquivo **não** começa com `test_`, então o pytest não o coleta — e a classe não começa com
`Test`, então nem sendo importada ela roda sozinha, sem uma implementação.

As comparações são por **valor**, nunca por identidade: um repositório que reconstrói a entidade a
partir de linhas do banco devolve um objeto novo a cada consulta, e exigir `is` seria exigir um
detalhe que só a dupla pode cumprir. `Space` é dataclass e compara campo a campo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.domain.errors import DuplicateSpaceCode

if TYPE_CHECKING:
    from agendalab.domain.repositories import SpaceRepository


def espaco(code: str, kind: SpaceKind = SpaceKind.CLASSROOM, active: bool = True) -> Space:
    return Space(code=code, name=f"Espaço {code}", kind=kind, capacity=40, active=active)


SALA = espaco("SALA-01", SpaceKind.CLASSROOM)
LABORATORIO = espaco("LAB-01", SpaceKind.LAB)
LAB_DESATIVADO = espaco("LAB-02", SpaceKind.LAB, active=False)
AUDITORIO = espaco("AUD-01", SpaceKind.AUDITORIUM, active=False)

CATALOGO = (SALA, LABORATORIO, LAB_DESATIVADO, AUDITORIO)


def codigos(espacos: list[Space]) -> list[str]:
    """`Space` é dataclass mutável e não é hashável — comparar por código evita a questão."""
    return sorted(e.code for e in espacos)


class SpaceRepositoryContract:
    """Herde e implemente a fixture `spaces`."""

    @pytest.fixture
    def spaces(self) -> SpaceRepository:
        raise NotImplementedError("a implementação sob teste precisa fornecer esta fixture")

    def povoar(self, spaces: SpaceRepository, *espacos: Space) -> None:
        for e in espacos:
            spaces.add(e)

    # --- add -----------------------------------------------------------------------------------

    def test_espaco_adicionado_pode_ser_encontrado(self, spaces: SpaceRepository) -> None:
        self.povoar(spaces, SALA)
        assert spaces.find_by_code("SALA-01") == SALA

    def test_o_espaco_volta_com_todos_os_campos(self, spaces: SpaceRepository) -> None:
        """Um campo perdido no caminho de ida e volta é o defeito clássico de um mapper."""
        self.povoar(spaces, LAB_DESATIVADO)
        guardado = spaces.find_by_code("LAB-02")
        assert guardado is not None
        assert (guardado.code, guardado.name, guardado.kind, guardado.capacity, guardado.active) == (
            LAB_DESATIVADO.code,
            LAB_DESATIVADO.name,
            LAB_DESATIVADO.kind,
            LAB_DESATIVADO.capacity,
            LAB_DESATIVADO.active,
        )

    def test_codigo_repetido_e_recusado(self, spaces: SpaceRepository) -> None:
        """RN-16 — o código de um espaço é único no sistema."""
        self.povoar(spaces, SALA)
        with pytest.raises(DuplicateSpaceCode) as erro:
            spaces.add(espaco("SALA-01", SpaceKind.LAB))
        assert erro.value.rule == "RN-16"

    def test_codigo_repetido_nao_substitui_o_existente(self, spaces: SpaceRepository) -> None:
        """A recusa precisa ser total: o espaço original continua lá, intacto."""
        self.povoar(spaces, SALA)
        with pytest.raises(DuplicateSpaceCode):
            spaces.add(espaco("SALA-01", SpaceKind.LAB))

        guardado = spaces.find_by_code("SALA-01")
        assert guardado is not None
        assert guardado.kind is SpaceKind.CLASSROOM

    # --- find_by_code --------------------------------------------------------------------------

    def test_buscar_codigo_inexistente_devolve_nulo(self, spaces: SpaceRepository) -> None:
        """A interface devolve `Space | None`; quem levanta `SpaceNotFound` é o caso de uso."""
        self.povoar(spaces, SALA)
        assert spaces.find_by_code("NAO-EXISTE") is None

    def test_buscar_em_repositorio_vazio_devolve_nulo(self, spaces: SpaceRepository) -> None:
        assert spaces.find_by_code("SALA-01") is None

    # --- list_all ------------------------------------------------------------------------------

    def test_listar_sem_filtro_devolve_tudo(self, spaces: SpaceRepository) -> None:
        self.povoar(spaces, SALA, LABORATORIO, AUDITORIO)
        assert codigos(spaces.list_all()) == ["AUD-01", "LAB-01", "SALA-01"]

    def test_listar_filtrando_por_tipo(self, spaces: SpaceRepository) -> None:
        self.povoar(spaces, *CATALOGO)
        assert codigos(spaces.list_all(kind=SpaceKind.LAB)) == ["LAB-01", "LAB-02"]

    def test_listar_filtrando_por_situacao(self, spaces: SpaceRepository) -> None:
        self.povoar(spaces, *CATALOGO)
        assert codigos(spaces.list_all(active=True)) == ["LAB-01", "SALA-01"]
        assert codigos(spaces.list_all(active=False)) == ["AUD-01", "LAB-02"]

    def test_listar_combinando_os_dois_filtros(self, spaces: SpaceRepository) -> None:
        """Os filtros são independentes e se somam."""
        self.povoar(spaces, *CATALOGO)
        assert codigos(spaces.list_all(kind=SpaceKind.LAB, active=False)) == ["LAB-02"]

    def test_filtro_que_nao_casa_devolve_lista_vazia(self, spaces: SpaceRepository) -> None:
        self.povoar(spaces, SALA)
        assert spaces.list_all(kind=SpaceKind.AUDITORIUM) == []

    def test_listar_repositorio_vazio_devolve_lista_vazia(self, spaces: SpaceRepository) -> None:
        assert spaces.list_all() == []

    def test_nulo_no_filtro_significa_nao_filtrar(self, spaces: SpaceRepository) -> None:
        """`None` não é "situação nula": é ausência de filtro, e a assinatura usa isso como padrão."""
        self.povoar(spaces, SALA, LAB_DESATIVADO)
        assert codigos(spaces.list_all(kind=None, active=None)) == ["LAB-02", "SALA-01"]
