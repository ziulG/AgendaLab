"""UC-01 — cadastrar espaço.

O primeiro caso de uso do sistema, e o que fixa o formato dos outros seis: a dependência entra pelo
`__init__` tipada pela **interface** do domínio, e a operação é um único `execute`. Tipar por
`SpaceRepository` em vez de pela classe SQLAlchemy da task 10 é o que permite este caso de uso ser
testado contra uma dupla em memória sem saber que ela existe.

A RN-16 não é verificada aqui. `SpaceRepository.add` declara no contrato que recusa código
repetido, e é ele quem tem visão do conjunto todo — consultar antes e inserir depois seriam duas
operações, com uma janela entre elas. O caso de uso deixa o `DuplicateSpaceCode` subir.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agendalab.domain.entities.space import Space

if TYPE_CHECKING:
    from agendalab.application.dto import RegisterSpaceCommand
    from agendalab.domain.repositories import SpaceRepository


class RegisterSpace:
    def __init__(self, spaces: SpaceRepository) -> None:
        self._spaces = spaces

    def execute(self, command: RegisterSpaceCommand) -> Space:
        """Levanta `DuplicateSpaceCode` (RN-16) se o código já existir, vindo do repositório.

        A capacidade positiva é invariante de `Space` e é verificada na construção: se o comando
        trouxer capacidade inválida, o `ValueError` sobe daqui e nada é guardado.
        """
        space = Space(
            code=command.code,
            name=command.name,
            kind=command.kind,
            capacity=command.capacity,
            active=True,  # UC-01 — o espaço é persistido como ativo
        )
        self._spaces.add(space)
        return space
