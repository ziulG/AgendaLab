"""Hierarquia de erros de domínio — tabela da §7.2 da especificação.

Dois contratos que a task 11 vai consumir: um `except DomainError` no tradutor HTTP precisa
capturar as onze, e a resposta JSON só consegue preencher `rule` se cada erro souber a sua.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from agendalab.domain.entities.booking import BookingStatus
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

# A tabela da §7.2, linha por linha: cada erro com a regra que a resposta HTTP deve citar.
# `None` nos dois primeiros porque identificador inexistente não viola regra numerada.
ERROS = [
    (SpaceNotFound("LAB-01"), None),
    (BookingNotFound(UUID("8f3a1c22-5d4e-4b8a-9f01-2c6e7d8a9b10")), None),
    (DuplicateSpaceCode("LAB-01"), "RN-16"),
    (ScheduleConflict("LAB-01", datetime(2026, 8, 20, 14), datetime(2026, 8, 20, 16)), "RN-01"),
    (InvalidStateTransition(BookingStatus.APPROVED, "approve"), "RN-13"),
    (InactiveSpace("LAB-01"), "RN-05"),
    (CapacityExceeded("LAB-01", attendees=40, capacity=30), "RN-06"),
    (PolicyViolation("Laboratório exige 24h de antecedência.", "RN-09"), "RN-09"),
    (InvalidTimeSlot("O intervalo precisa começar no futuro.", "RN-04"), "RN-04"),
    (MissingRejectionReason(), "RN-14"),
    (PermissionDenied("Somente o gestor decide sobre reservas.", "RN-11"), "RN-11"),
]

IDS = [type(erro).__name__ for erro, _ in ERROS]


@pytest.mark.parametrize(("erro", "regra"), ERROS, ids=IDS)
def test_todo_erro_de_dominio_carrega_mensagem_e_regra(erro: DomainError, regra: str | None) -> None:
    """§7.2 — os três campos da resposta de erro saem daqui: classe, `message` e `rule`."""
    assert isinstance(erro, DomainError)
    assert erro.message.strip(), "a mensagem precisa ser legível, não vazia"
    assert str(erro) == erro.message
    assert erro.rule == regra


@pytest.mark.parametrize(("erro", "_regra"), ERROS, ids=IDS)
def test_um_unico_except_captura_toda_a_hierarquia(erro: DomainError, _regra: str | None) -> None:
    """É o que permite ao tradutor da task 11 ser um único tratador."""
    with pytest.raises(DomainError):
        raise erro


def test_a_hierarquia_tem_exatamente_onze_subclasses() -> None:
    """A §7.2 mapeia onze erros para HTTP. Um erro fora da tabela chegaria ao cliente como 500."""
    assert len(DomainError.__subclasses__()) == 11
    assert len(ERROS) == 11


# --- mensagens ------------------------------------------------------------------------------


def test_mensagem_de_conflito_segue_o_formato_da_especificacao() -> None:
    """§7.2 — a mensagem publicada no exemplo da especificação, reproduzida literalmente."""
    erro = ScheduleConflict("LAB-01", datetime(2026, 8, 20, 14), datetime(2026, 8, 20, 16))
    assert erro.message == (
        "O espaço LAB-01 já possui reserva ativa entre 14:00 e 16:00 em 20/08/2026."
    )


def test_mensagem_de_transicao_invalida_nomeia_estado_e_operacao() -> None:
    """RN-13 — quem recebe o 409 precisa saber de que estado para qual operação."""
    erro = InvalidStateTransition(BookingStatus.CANCELLED, "approve")
    assert "CANCELLED" in erro.message
    assert "approve" in erro.message


def test_mensagem_de_capacidade_mostra_os_dois_numeros() -> None:
    """RN-06."""
    erro = CapacityExceeded("SALA-01", attendees=45, capacity=40)
    assert "45" in erro.message
    assert "40" in erro.message


@pytest.mark.parametrize(
    "erro",
    [SpaceNotFound("LAB-01"), DuplicateSpaceCode("LAB-01"), InactiveSpace("LAB-01")],
    ids=["SpaceNotFound", "DuplicateSpaceCode", "InactiveSpace"],
)
def test_mensagem_cita_o_espaco_envolvido(erro: DomainError) -> None:
    assert "LAB-01" in erro.message


# --- regras com mais de uma origem na §7.2 ---------------------------------------------------


def test_regra_padrao_vale_quando_nenhuma_e_informada() -> None:
    """`InvalidTimeSlot` cobre RN-03 e RN-04; RN-03 é o caso da própria construção do intervalo."""
    assert InvalidTimeSlot("O fim precisa vir depois do início.").rule == "RN-03"


def test_informar_a_regra_nao_altera_o_padrao_da_classe() -> None:
    """A regra informada vira atributo de instância — a classe não pode ser contaminada."""
    InvalidTimeSlot("O intervalo precisa começar no futuro.", "RN-04")
    assert InvalidTimeSlot.rule == "RN-03"
    assert InvalidTimeSlot("O fim precisa vir depois do início.").rule == "RN-03"
