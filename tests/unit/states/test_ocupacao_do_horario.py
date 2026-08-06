"""Quem ocupa o horário do espaço — RN-01, via padrão State.

O ADR-0005 rejeitou a tabela de transições declarativa por um motivo específico: ela responderia
"esta transição é permitida?" mas não expressaria que `REJECTED` não ocupa horário. Aqui esse
comportamento existe onde o ADR disse que existiria — no estado — em vez de virar uma condicional
sobre `status` espalhada pelos repositórios.

`ACTIVE_STATUSES` é derivado dos próprios estados, e não escrito à mão: é o conjunto que a consulta
SQL da task 10 vai usar num `IN (...)`, e derivá-lo impede que ele divirja das classes.
"""

from __future__ import annotations

import pytest

from agendalab.domain.entities.booking import BookingStatus
from agendalab.domain.states.concrete_states import ACTIVE_STATUSES, state_for

# A definição da RN-01: ativa é `PENDING` ou `APPROVED`.
OCUPA_HORARIO = {
    BookingStatus.PENDING: True,
    BookingStatus.APPROVED: True,
    BookingStatus.REJECTED: False,
    BookingStatus.CANCELLED: False,
}


@pytest.mark.parametrize("status", list(BookingStatus), ids=lambda s: str(s))
def test_quem_ocupa_o_horario_do_espaco(status: BookingStatus) -> None:
    """RN-01 — e uma reserva cancelada libera o intervalo para novas solicitações."""
    assert state_for(status).occupies_slot() is OCUPA_HORARIO[status]


def test_o_conjunto_de_ativas_e_derivado_dos_estados() -> None:
    """RN-01 — o conjunto que o SQL da task 10 vai usar sai das classes, não de uma lista à mão."""
    assert set(ACTIVE_STATUSES) == {BookingStatus.PENDING, BookingStatus.APPROVED}


def test_todo_status_declara_se_ocupa_horario() -> None:
    """Percorrer o enum é o que faz um estado novo aparecer aqui sem ninguém lembrar dele."""
    assert {status for status in BookingStatus if state_for(status).occupies_slot()} == set(
        ACTIVE_STATUSES
    )


def test_estado_terminal_nao_ocupa_horario() -> None:
    """`REJECTED` e `CANCELLED` são os dois estados terminais da §5.5, e nenhum ocupa."""
    terminais = [BookingStatus.REJECTED, BookingStatus.CANCELLED]
    assert not any(state_for(status).occupies_slot() for status in terminais)
