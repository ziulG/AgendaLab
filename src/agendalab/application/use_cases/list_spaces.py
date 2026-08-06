"""UC-02 — listar espaços.

O caso de uso mais magro do sistema, e ele é magro de propósito: a filtragem é uma consulta, e
consulta é do repositório. Trazer todos os espaços para memória e filtrar aqui funcionaria com as
duplas e viraria uma varredura de tabela inteira na task 10.

Não ordena. A ordem de listagem é decisão de apresentação, e a §7 não a especifica.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agendalab.application.dto import ListSpacesQuery
    from agendalab.domain.entities.space import Space
    from agendalab.domain.repositories import SpaceRepository


class ListSpaces:
    def __init__(self, spaces: SpaceRepository) -> None:
        self._spaces = spaces

    def execute(self, query: ListSpacesQuery) -> list[Space]:
        """Os dois filtros são independentes e opcionais; `None` é ausência de filtro."""
        return self._spaces.list_all(kind=query.kind, active=query.active)
