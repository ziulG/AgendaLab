"""O mapa tipo → política — ADR-0004.

É um `dict`, e é chamado de mapa: rotulá-lo de Factory Method para elevar a contagem de padrões do
trabalho seria inflar o que existe.

Percorrer os membros de `SpaceKind` em vez de listar os três à mão é a mitigação que o ADR-0004
registra: um tipo de espaço novo sem política daria `KeyError` em tempo de execução, e aqui quebra
a suíte antes.
"""

from __future__ import annotations

import pytest

from agendalab.domain.entities.space import SpaceKind
from agendalab.domain.policies.booking_policy import BookingPolicy
from agendalab.domain.policies.managed_access import ManagedAccessPolicy
from agendalab.domain.policies.open_access import OpenAccessPolicy
from agendalab.domain.policies.registry import POLICY_BY_KIND, policy_for
from agendalab.domain.policies.restricted_access import RestrictedAccessPolicy

# A tabela da §5.3 da especificação, em código.
POLITICA_ESPERADA = {
    SpaceKind.CLASSROOM: OpenAccessPolicy,
    SpaceKind.LAB: ManagedAccessPolicy,
    SpaceKind.AUDITORIUM: RestrictedAccessPolicy,
}


@pytest.mark.parametrize("kind", list(SpaceKind), ids=lambda k: str(k))
def test_todo_tipo_de_espaco_tem_politica(kind: SpaceKind) -> None:
    assert kind in POLICY_BY_KIND


@pytest.mark.parametrize("kind", list(SpaceKind), ids=lambda k: str(k))
def test_cada_tipo_recebe_a_politica_da_especificacao(kind: SpaceKind) -> None:
    """§5.3 — `CLASSROOM` abre, `LAB` gerencia, `AUDITORIUM` restringe."""
    assert isinstance(policy_for(kind), POLITICA_ESPERADA[kind])


@pytest.mark.parametrize("kind", list(SpaceKind), ids=lambda k: str(k))
def test_toda_politica_registrada_satisfaz_o_protocolo(kind: SpaceKind) -> None:
    """As políticas não herdam de `BookingPolicy` — a conformidade é estrutural, e é aqui que
    ela é verificada em vez de imposta por sintaxe.
    """
    assert isinstance(policy_for(kind), BookingPolicy)


def test_politicas_distintas_para_tipos_distintos() -> None:
    """Três tipos, três classes — nenhuma reaproveitada por engano."""
    classes = {type(policy_for(kind)) for kind in SpaceKind}
    assert len(classes) == len(SpaceKind)
