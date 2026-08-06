"""UC-02 — consultar um espaço pelo código.

Existe porque a §7 da especificação promete `GET /spaces/{code}` e nenhum dos casos de uso originais
a atendia: `ListSpaces` filtra por tipo e situação, não por código.

A rota poderia chamar o repositório direto e economizar este arquivo. Não o faz por uma razão só: no
dia em que consultar um espaço passar a envolver qualquer outra coisa — registrar acesso, esconder
campo de espaço inativo — o lugar dessa decisão já existe, e não é dentro de uma função de rota.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agendalab.domain.errors import SpaceNotFound

if TYPE_CHECKING:
    from agendalab.application.dto import GetSpaceQuery
    from agendalab.domain.entities.space import Space
    from agendalab.domain.repositories import SpaceRepository


class GetSpace:
    def __init__(self, spaces: SpaceRepository) -> None:
        self._spaces = spaces

    def execute(self, query: GetSpaceQuery) -> Space:
        """O espaço, ou `SpaceNotFound`. Traduzir a ausência em erro é do caso de uso, não do
        repositório — o contrato dele devolve `Space | None`."""
        space = self._spaces.find_by_code(query.code)
        if space is None:
            raise SpaceNotFound(query.code)
        return space
