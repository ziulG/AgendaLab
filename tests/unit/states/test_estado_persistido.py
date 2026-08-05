"""Reconstrução do estado a partir do `BookingStatus` persistido — ADR-0005.

O banco guarda um `BookingStatus` simples, não um objeto de estado. Este teste é a mitigação do
risco que o ADR-0005 registra: um estado novo esquecido na conversão quebraria o carregamento em
tempo de execução, e aqui quebra a suíte antes.

Percorrer os membros de `BookingStatus` em vez de listar os quatro à mão é o que faz um estado
novo aparecer neste teste sem que ninguém precise lembrar de acrescentá-lo.
"""

from __future__ import annotations

import pytest

from agendalab.domain.entities.booking import BookingStatus
from agendalab.domain.states.booking_state import BookingState
from agendalab.domain.states.concrete_states import state_for


@pytest.mark.parametrize("status", list(BookingStatus), ids=lambda s: str(s))
def test_todo_status_tem_estado_correspondente(status: BookingStatus) -> None:
    assert isinstance(state_for(status), BookingState)


@pytest.mark.parametrize("status", list(BookingStatus), ids=lambda s: str(s))
def test_o_estado_reconstruido_declara_o_status_de_origem(status: BookingStatus) -> None:
    """Ida e volta: o status vira estado, e o estado devolve o mesmo status."""
    assert state_for(status).status() is status


def test_estados_distintos_para_status_distintos() -> None:
    """Quatro status, quatro classes — nenhuma reaproveitada por engano."""
    classes = {type(state_for(status)) for status in BookingStatus}
    assert len(classes) == len(BookingStatus)
