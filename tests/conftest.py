"""Os marcadores da pirâmide, aplicados pelo diretório em que o teste vive.

O `pyproject.toml` declara `unit`, `integration` e `e2e` desde a task 01, e a pirâmide do ADR-0009
organiza a suíte exatamente nesses diretórios. Ligar as duas coisas à mão significaria um decorador
no topo de cada um dos sessenta arquivos — sessenta chances de esquecer, e um arquivo novo nasceria
sem marcador nenhum.

Aqui a classificação sai de onde o arquivo está, que é a mesma informação, sem cópia. Fazem
`pytest -m unit` funcionar, e é ele que sustenta a afirmação central do ADR-0009: a suíte de domínio
roda sem tocar disco.

`tests/architecture/` não recebe marcador. É um nível à parte na tabela do ADR-0009 — não testa
comportamento, testa a estrutura —, e agrupá-lo com os unitários confundiria as duas coisas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

MARCADOR_POR_DIRETORIO = {
    "unit": "unit",
    "integration": "integration",
    "e2e": "e2e",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Marca cada teste com o nível da pirâmide a que ele pertence."""
    for item in items:
        for parte in item.path.parts:
            marcador = MARCADOR_POR_DIRETORIO.get(parte)
            if marcador is not None:
                item.add_marker(marcador)
                break
