"""`Actor` — quem age sobre uma reserva.

Não existe entidade `User` no sistema (§4.1): a identidade chega pelos cabeçalhos `X-User-Id` e
`X-User-Role` e o domínio confia nela — a decisão e seus riscos estão no ADR-0007. O que o domínio
faz com essa identidade é autorização, e essa está implementada por inteiro: RN-11 e RN-12.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    REQUESTER = "REQUESTER"
    MANAGER = "MANAGER"


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: str
    role: Role
