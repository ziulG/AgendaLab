"""As rotas de espaço — UC-01, UC-02 e UC-03.

Cada função aqui faz três coisas e nenhuma a mais: monta o comando a partir do que chegou, chama
`execute` e converte a entidade em schema de resposta. Não há `if`, não há regra e não há tratamento
de erro — o `DomainError` sobe até o tratador central, que sabe traduzi-lo (§7.2).

É por serem assim tão finas que estas funções não precisam de teste próprio: o que elas fazem já
está testado dos dois lados, nos casos de uso e no tratador.
"""

from __future__ import annotations

from datetime import date
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from agendalab.application.dto import (
    CheckAvailabilityQuery,
    GetSpaceQuery,
    ListSpacesQuery,
    RegisterSpaceCommand,
)
from agendalab.application.use_cases.check_availability import CheckAvailability
from agendalab.application.use_cases.get_space import GetSpace
from agendalab.application.use_cases.list_spaces import ListSpaces
from agendalab.application.use_cases.register_space import RegisterSpace
from agendalab.domain.entities.space import SpaceKind
from agendalab.presentation.api.schemas import (
    BookingResponse,
    RegisterSpaceRequest,
    SpaceResponse,
)
from agendalab.presentation.dependencies import (
    ManagerDep,
    get_actor,
    get_check_availability,
    get_get_space,
    get_list_spaces,
    get_register_space,
)

# A identidade é exigida em **toda** rota de negócio, inclusive nas de leitura: a §7 diz que todas
# as rotas recebem `X-User-Id` e `X-User-Role`, e "papel exigido: qualquer" significa qualquer um
# dos dois papéis, não ausência de identidade. Declarada no router, e não rota a rota, para que
# acrescentar um endpoint não signifique lembrar de exigi-la.
router = APIRouter(prefix="/spaces", tags=["espaços"], dependencies=[Depends(get_actor)])


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    summary="Cadastrar espaço (UC-01)",
    response_description="O espaço cadastrado, sempre ativo",
)
def register_space(
    body: RegisterSpaceRequest,
    caso_de_uso: Annotated[RegisterSpace, Depends(get_register_space)],
    _: ManagerDep,
) -> SpaceResponse:
    """Só gestor cadastra — §7. O `ManagerDep` é a verificação, e ela não aparece no corpo da
    função: está na assinatura, onde o FastAPI a resolve antes de entrar aqui."""
    space = caso_de_uso.execute(
        RegisterSpaceCommand(
            code=body.code, name=body.name, kind=body.kind, capacity=body.capacity
        )
    )
    return SpaceResponse.of(space)


@router.get("", summary="Listar espaços (UC-02)")
def list_spaces(
    caso_de_uso: Annotated[ListSpaces, Depends(get_list_spaces)],
    kind: Annotated[SpaceKind | None, Query(description="Filtrar por tipo")] = None,
    active: Annotated[bool | None, Query(description="Filtrar por situação")] = None,
) -> list[SpaceResponse]:
    """Os dois filtros são opcionais; ausentes, devolvem tudo."""
    espacos = caso_de_uso.execute(ListSpacesQuery(kind=kind, active=active))
    return [SpaceResponse.of(e) for e in espacos]


@router.get(
    "/{code}",
    summary="Consultar um espaço (UC-02)",
    responses={HTTPStatus.NOT_FOUND: {"description": "Espaço inexistente"}},
)
def get_space(
    code: str, caso_de_uso: Annotated[GetSpace, Depends(get_get_space)]
) -> SpaceResponse:
    return SpaceResponse.of(caso_de_uso.execute(GetSpaceQuery(code=code)))


@router.get(
    "/{code}/availability",
    summary="Consultar a agenda de um dia (UC-03)",
    response_description="As reservas ativas do dia, em ordem cronológica",
    responses={HTTPStatus.NOT_FOUND: {"description": "Espaço inexistente"}},
)
def check_availability(
    code: str,
    caso_de_uso: Annotated[CheckAvailability, Depends(get_check_availability)],
    day: Annotated[date, Query(alias="date", description="Dia consultado, em ISO 8601")],
) -> list[BookingResponse]:
    """Devolve o que está **ocupado**; ler nisso as faixas livres é do cliente.

    O parâmetro se chama `date` na URL, como a §7 promete, e `day` aqui dentro — `date` é o nome de
    um tipo, e sombreá-lo numa função que trabalha com datas é pedir confusão.
    """
    agenda = caso_de_uso.execute(CheckAvailabilityQuery(space_code=code, day=day))
    return [BookingResponse.of(r) for r in agenda]
