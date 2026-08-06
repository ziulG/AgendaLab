"""UC-02 — listar espaços.

O caso de uso mais magro do sistema: ele repassa os dois filtros ao repositório e devolve o
resultado. Testá-lo pode parecer testar a dupla de novo, mas o que está sob verificação é outra
coisa — que a consulta chega ao repositório **inteira**. Um `execute` que esquecesse de encaminhar
`active` passaria em todos os testes da dupla e devolveria a lista errada em produção.
"""

from __future__ import annotations

from agendalab.application.dto import ListSpacesQuery
from agendalab.application.use_cases.list_spaces import ListSpaces
from agendalab.domain.entities.space import Space, SpaceKind
from tests.doubles.in_memory_repositories import InMemorySpaceRepository


def espaco(code: str, kind: SpaceKind, active: bool = True) -> Space:
    return Space(code=code, name=f"Espaço {code}", kind=kind, capacity=40, active=active)


SALA = espaco("SALA-01", SpaceKind.CLASSROOM)
LABORATORIO = espaco("LAB-01", SpaceKind.LAB)
LAB_DESATIVADO = espaco("LAB-02", SpaceKind.LAB, active=False)
AUDITORIO = espaco("AUD-01", SpaceKind.AUDITORIUM, active=False)


def caso_de_uso(*espacos: Space) -> ListSpaces:
    spaces = InMemorySpaceRepository()
    for e in espacos:
        spaces.add(e)
    return ListSpaces(spaces)


def codigos(espacos: list[Space]) -> list[str]:
    """`Space` é dataclass mutável e não é hashável — comparar por código evita a questão."""
    return sorted(e.code for e in espacos)


TODOS = (SALA, LABORATORIO, LAB_DESATIVADO, AUDITORIO)


# --- sem filtro --------------------------------------------------------------------------------


def test_consulta_sem_filtro_devolve_todos_os_espacos() -> None:
    listar = caso_de_uso(*TODOS)
    assert codigos(listar.execute(ListSpacesQuery())) == ["AUD-01", "LAB-01", "LAB-02", "SALA-01"]


def test_os_filtros_sao_opcionais_na_construcao_da_consulta() -> None:
    """`ListSpacesQuery()` sem argumento algum é consulta válida: `None` é ausência de filtro."""
    consulta = ListSpacesQuery()
    assert (consulta.kind, consulta.active) == (None, None)


def test_repositorio_vazio_devolve_lista_vazia() -> None:
    assert caso_de_uso().execute(ListSpacesQuery()) == []


# --- filtros -----------------------------------------------------------------------------------


def test_filtra_por_tipo() -> None:
    listar = caso_de_uso(*TODOS)
    assert codigos(listar.execute(ListSpacesQuery(kind=SpaceKind.LAB))) == ["LAB-01", "LAB-02"]


def test_filtra_por_situacao() -> None:
    listar = caso_de_uso(*TODOS)
    assert codigos(listar.execute(ListSpacesQuery(active=True))) == ["LAB-01", "SALA-01"]
    assert codigos(listar.execute(ListSpacesQuery(active=False))) == ["AUD-01", "LAB-02"]


def test_filtra_pelos_dois_criterios_ao_mesmo_tempo() -> None:
    """O teste que pega o `execute` que encaminha só um dos filtros."""
    listar = caso_de_uso(*TODOS)
    consulta = ListSpacesQuery(kind=SpaceKind.LAB, active=False)
    assert codigos(listar.execute(consulta)) == ["LAB-02"]


def test_filtro_que_nao_casa_com_nada_devolve_lista_vazia() -> None:
    listar = caso_de_uso(SALA, LABORATORIO)
    assert listar.execute(ListSpacesQuery(kind=SpaceKind.AUDITORIUM)) == []
