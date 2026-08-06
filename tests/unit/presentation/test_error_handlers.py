"""A tabela de tradução da §7.2, verificada sem subir a aplicação.

Os testes de borda exercitam a tradução por HTTP, um erro de cada vez e com o cenário inteiro
montado. Estes olham a tabela de frente: percorrem **todas** as subclasses de `DomainError` e exigem
que cada uma tenha status declarado. Um erro novo no domínio que ninguém traduzir quebra aqui, no
mesmo dia em que for criado, em vez de aparecer como um `422` genérico numa demonstração.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest

from agendalab.domain import errors
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
from agendalab.presentation.error_handlers import STATUS_BY_ERROR, status_for, to_response

TABELA_DA_ESPECIFICACAO = [
    (SpaceNotFound, HTTPStatus.NOT_FOUND),
    (BookingNotFound, HTTPStatus.NOT_FOUND),
    (DuplicateSpaceCode, HTTPStatus.CONFLICT),
    (ScheduleConflict, HTTPStatus.CONFLICT),
    (InvalidStateTransition, HTTPStatus.CONFLICT),
    (InactiveSpace, HTTPStatus.UNPROCESSABLE_ENTITY),
    (CapacityExceeded, HTTPStatus.UNPROCESSABLE_ENTITY),
    (PolicyViolation, HTTPStatus.UNPROCESSABLE_ENTITY),
    (InvalidTimeSlot, HTTPStatus.UNPROCESSABLE_ENTITY),
    (MissingRejectionReason, HTTPStatus.UNPROCESSABLE_ENTITY),
    (PermissionDenied, HTTPStatus.FORBIDDEN),
]
IDS = [classe.__name__ for classe, _ in TABELA_DA_ESPECIFICACAO]


def subclasses_de_erro() -> list[type[DomainError]]:
    """Todas as subclasses declaradas em `domain/errors.py`, descobertas do próprio módulo."""
    return [
        objeto
        for objeto in vars(errors).values()
        if isinstance(objeto, type)
        and issubclass(objeto, DomainError)
        and objeto is not DomainError
    ]


# --- a tabela ------------------------------------------------------------------------------------


@pytest.mark.parametrize(("classe", "esperado"), TABELA_DA_ESPECIFICACAO, ids=IDS)
def test_o_erro_tem_o_status_da_especificacao(
    classe: type[DomainError], esperado: HTTPStatus
) -> None:
    assert STATUS_BY_ERROR[classe] == esperado


def test_todo_erro_de_dominio_tem_status_declarado() -> None:
    """A guarda contra o erro novo e esquecido — a lista sai do módulo, não de uma cópia."""
    sem_traducao = [c.__name__ for c in subclasses_de_erro() if c not in STATUS_BY_ERROR]
    assert not sem_traducao, f"erros sem status na §7.2: {sem_traducao}"


def test_a_tabela_nao_tem_entrada_a_mais() -> None:
    """O contrário: um erro removido do domínio não pode deixar entrada órfã aqui."""
    conhecidas = set(subclasses_de_erro())
    assert set(STATUS_BY_ERROR) <= conhecidas


# --- a resolução do status -----------------------------------------------------------------------


def test_uma_subclasse_futura_herda_o_status_da_mae() -> None:
    """Especializar `PolicyViolation` para uma política nova não deveria mudar o status."""

    class PolicyViolationEspecifica(PolicyViolation):
        pass

    assert status_for(PolicyViolationEspecifica("recusado", "RN-08")) == (
        HTTPStatus.UNPROCESSABLE_ENTITY
    )


def test_um_erro_sem_traducao_cai_no_padrao() -> None:
    """`422`, e não `500`: a requisição chegou bem formada e foi o negócio que a recusou — dizer
    "erro interno" seria mentir sobre de quem é a culpa."""

    class ErroInedito(DomainError):
        pass

    assert status_for(ErroInedito("algo novo")) == HTTPStatus.UNPROCESSABLE_ENTITY


# --- o corpo da resposta -------------------------------------------------------------------------


def test_o_corpo_tem_o_nome_a_mensagem_e_a_regra() -> None:
    import json

    resposta = to_response(ScheduleConflict("LAB-01", _quinta(), _quinta()))
    corpo = json.loads(bytes(resposta.body))

    assert corpo["error"] == "ScheduleConflict"
    assert corpo["rule"] == "RN-01"
    assert "LAB-01" in corpo["message"]


def test_a_regra_e_nula_quando_o_erro_nao_declara_uma() -> None:
    """`SpaceNotFound` não viola regra numerada — não existe RN para "esse código não existe"."""
    import json

    corpo = json.loads(bytes(to_response(SpaceNotFound("NAO-EXISTE")).body))
    assert corpo["rule"] is None


def _quinta() -> object:
    from datetime import datetime

    return datetime(2026, 8, 20, 14, 0)
