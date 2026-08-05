"""`Actor` — quem age sobre uma reserva.

Não existe entidade `User` (§4.1): a identidade chega por cabeçalho HTTP e o sistema confia nela
(ADR-0007). `Actor` é o par identificador + papel que as regras de autorização RN-11 e RN-12
consultam.
"""

from __future__ import annotations

import dataclasses

import pytest

from agendalab.domain.actor import Actor, Role


def test_os_dois_papeis_existem() -> None:
    """§7 — os valores aceitos no cabeçalho `X-User-Role`."""
    assert [papel.value for papel in Role] == ["REQUESTER", "MANAGER"]


def test_ator_guarda_identificador_e_papel() -> None:
    ator = Actor(user_id="2019001234", role=Role.REQUESTER)
    assert ator.user_id == "2019001234"
    assert ator.role is Role.REQUESTER


def test_ator_e_imutavel() -> None:
    """O papel de quem faz a requisição não muda no meio dela."""
    ator = Actor(user_id="chefe.laboratorio", role=Role.MANAGER)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ator.role = Role.REQUESTER  # type: ignore[misc]
