"""`Space` — um recurso físico reservável.

O `kind` não é rótulo decorativo: é ele que determina qual política de admissão se aplica
(RN-08 a RN-10), e é essa variação que o padrão Strategy isola na task 04.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SpaceKind(StrEnum):
    CLASSROOM = "CLASSROOM"
    LAB = "LAB"
    AUDITORIUM = "AUDITORIUM"


@dataclass
class Space:
    code: str
    name: str
    kind: SpaceKind
    capacity: int
    active: bool = True

    def __post_init__(self) -> None:
        """Invariantes da §4.3.

        `ValueError`, e não erro de domínio: a §7.2 não traduz estes casos para HTTP porque a
        validação da borda os recusa antes de chegar aqui. São erro de programação.
        """
        if not self.code.strip():
            raise ValueError("O código do espaço não pode ser vazio.")
        if self.capacity <= 0:
            raise ValueError(f"A capacidade do espaço {self.code} precisa ser positiva.")
