"""`SpyObserver` satisfaz o contrato de observador do domínio.

Mesma razão de existir do teste de conformidade dos repositórios: um espião que divergisse de
`EventObserver` faria os testes de caso de uso passarem contra um contrato que os notificadores
reais da task 10 não implementam.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from agendalab.domain.events.booking_events import BookingApproved, BookingRequested
from agendalab.domain.events.publisher import EventObserver, EventPublisher
from tests.doubles.spy_observer import SpyObserver

AGORA = datetime(2026, 8, 5, 9, 0)


def evento(occurred_at: datetime = AGORA) -> BookingRequested:
    return BookingRequested(
        booking_id=uuid4(),
        space_code="SALA-01",
        requester_id="2019001234",
        occurred_at=occurred_at,
    )


def test_o_espiao_satisfaz_o_protocolo_de_observador() -> None:
    """Estrutural, sem herança — como as duplas de repositório."""
    assert isinstance(SpyObserver(), EventObserver)


def test_o_espiao_registra_o_que_recebe_pelo_publicador() -> None:
    espiao = SpyObserver()
    publicador = EventPublisher()
    publicador.subscribe(espiao)

    publicado = evento()
    publicador.publish(publicado)

    assert espiao.recebidos == [publicado]


def test_o_espiao_preserva_a_ordem_de_publicacao() -> None:
    espiao = SpyObserver()
    primeiro, segundo = evento(), evento(datetime(2026, 8, 5, 10, 0))

    espiao.handle(primeiro)
    espiao.handle(segundo)

    assert espiao.recebidos == [primeiro, segundo]


def test_espiao_recem_criado_nao_recebeu_nada() -> None:
    assert SpyObserver().recebidos == []


# --- o atalho `unico` --------------------------------------------------------------------------


def test_unico_devolve_o_evento_quando_houve_exatamente_um() -> None:
    espiao = SpyObserver()
    publicado = evento()
    espiao.handle(publicado)
    assert espiao.unico is publicado


@pytest.mark.parametrize("quantidade", [0, 2, 3])
def test_unico_acusa_quando_a_quantidade_nao_e_um(quantidade: int) -> None:
    """A guarda que dá sentido ao atalho: publicar duas vezes não pode passar despercebido."""
    espiao = SpyObserver()
    for _ in range(quantidade):
        espiao.handle(evento())

    with pytest.raises(AssertionError, match="exatamente 1 evento"):
        _ = espiao.unico


def test_unico_nomeia_os_eventos_recebidos_na_mensagem() -> None:
    """Quem lê a falha precisa saber o que chegou a mais, não só que chegou a mais."""
    espiao = SpyObserver()
    espiao.handle(evento())
    espiao.handle(
        BookingApproved(
            booking_id=uuid4(),
            space_code="SALA-01",
            requester_id="2019001234",
            occurred_at=AGORA,
            decided_by="1998007766",
        )
    )

    with pytest.raises(AssertionError, match="BookingRequested.*BookingApproved"):
        _ = espiao.unico
