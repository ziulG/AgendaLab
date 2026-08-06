"""Tradução de erro de domínio em resposta HTTP — §7.2 da especificação.

**Esta é a única camada que conhece códigos de status.** O domínio levanta `ScheduleConflict`; que
isso seja um `409` é conhecimento de protocolo, e protocolo é assunto de borda. Um `raise
HTTPException` dentro de um caso de uso amarraria a regra de negócio ao HTTP e impediria que o mesmo
caso de uso servisse a uma CLI ou a um worker.

A distinção entre `409` e `422` é deliberada e está na §7.2: **409** é conflito com o estado atual
do recurso — repetir depois pode funcionar; **422** é requisição bem formada porém semanticamente
inadmissível — repetir sem mudar os dados nunca vai funcionar.

Toda resposta de erro tem o mesmo formato, e o campo `rule` liga a resposta de volta à regra
numerada da especificação. É rastreabilidade que funciona em tempo de execução: quem recebe um `422`
descobre pelo corpo que foi a RN-09, sem abrir o código.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from agendalab.domain.errors import (
    BookingNotFound,
    CapacityExceeded,
    DomainError,
    DuplicateSpaceCode,
    InactiveSpace,
    InvalidStateTransition,
    InvalidTimeSlot,
    MissingRejectionReason,
    PermissionDenied,
    PolicyViolation,
    ScheduleConflict,
    SpaceNotFound,
)

if TYPE_CHECKING:
    from fastapi import FastAPI, Request

# A tabela da §7.2, uma entrada por erro. Escrita por extenso, e não deduzida de alguma hierarquia
# de "erros 4xx": agrupar por status esconderia que a escolha entre 409 e 422 é semântica, e a
# revisão de cada linha é o que garante que ela continua certa.
STATUS_BY_ERROR: dict[type[DomainError], HTTPStatus] = {
    SpaceNotFound: HTTPStatus.NOT_FOUND,
    BookingNotFound: HTTPStatus.NOT_FOUND,
    DuplicateSpaceCode: HTTPStatus.CONFLICT,
    ScheduleConflict: HTTPStatus.CONFLICT,
    InvalidStateTransition: HTTPStatus.CONFLICT,
    InactiveSpace: HTTPStatus.UNPROCESSABLE_ENTITY,
    CapacityExceeded: HTTPStatus.UNPROCESSABLE_ENTITY,
    PolicyViolation: HTTPStatus.UNPROCESSABLE_ENTITY,
    InvalidTimeSlot: HTTPStatus.UNPROCESSABLE_ENTITY,
    MissingRejectionReason: HTTPStatus.UNPROCESSABLE_ENTITY,
    PermissionDenied: HTTPStatus.FORBIDDEN,
}

# Um erro de domínio que ninguém traduziu ainda. `422` e não `500`: a requisição chegou bem formada
# e foi o negócio que a recusou, então dizer "erro interno" seria mentir sobre de quem é a culpa.
STATUS_PADRAO = HTTPStatus.UNPROCESSABLE_ENTITY


def status_for(error: DomainError) -> HTTPStatus:
    """O status da §7.2 para este erro.

    A busca desce a hierarquia de classes para que uma subclasse futura de, digamos,
    `PolicyViolation` herde o status da mãe em vez de cair no padrão.
    """
    for classe in type(error).__mro__:
        if classe in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[classe]
    return STATUS_PADRAO


def to_response(error: DomainError) -> JSONResponse:
    """O corpo único da §7.2: o nome da classe, a mensagem em português e a regra violada."""
    return JSONResponse(
        status_code=status_for(error),
        content={
            "error": type(error).__name__,
            "message": error.message,
            "rule": error.rule,
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Um tratador só, para `DomainError`.

    O FastAPI escolhe o tratador pela classe mais específica registrada, e registrar a base cobre as
    onze subclasses de uma vez. Onze tratadores idênticos seriam onze lugares para esquecer de
    atualizar quando um erro novo aparecesse.
    """

    @app.exception_handler(DomainError)
    async def _tratar_erro_de_dominio(_: Request, error: DomainError) -> JSONResponse:
        return to_response(error)
