"""Resolução de tipo de espaço para política de admissão.

Isto é um **mapa**, não um Factory Method. É um `dict` de três entradas, e rotulá-lo com nome de
padrão para elevar a contagem de padrões do trabalho seria inflar o que existe — a contenção é
deliberada e está registrada no ADR-0004.

É também o único lugar do pacote `policies/` que menciona um membro de `SpaceKind`. Uma política
que consultasse o tipo do espaço seria a condicional que o Strategy existe para eliminar.
"""

from __future__ import annotations

from agendalab.domain.entities.space import SpaceKind
from agendalab.domain.policies.booking_policy import BookingPolicy
from agendalab.domain.policies.managed_access import ManagedAccessPolicy
from agendalab.domain.policies.open_access import OpenAccessPolicy
from agendalab.domain.policies.restricted_access import RestrictedAccessPolicy

# Uma instância de cada: as políticas não têm dados próprios. Tabela da §5.3 da especificação.
POLICY_BY_KIND: dict[SpaceKind, BookingPolicy] = {
    SpaceKind.CLASSROOM: OpenAccessPolicy(),
    SpaceKind.LAB: ManagedAccessPolicy(),
    SpaceKind.AUDITORIUM: RestrictedAccessPolicy(),
}


def policy_for(kind: SpaceKind) -> BookingPolicy:
    """A política do tipo. Um tipo sem política é erro de programação, e o teste do registro
    garante que nenhum chegue até aqui.
    """
    return POLICY_BY_KIND[kind]
