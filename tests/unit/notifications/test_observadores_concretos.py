"""`LogNotifier` e `NotificationInbox` — os dois observadores concretos do ADR-0006.

O que estes testes verificam, além do óbvio, é a promessa que dá sentido ao padrão: **nenhum dos
dois é conhecido pelo domínio**, e acrescentar um terceiro canal seria uma classe a mais e uma linha
de inscrição. Aqui eles aparecem inscritos num `EventPublisher` real, que é como vão viver no
composition root da task 11.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

import pytest

from agendalab.domain.events.booking_events import (
    BookingApproved,
    BookingEvent,
    BookingRequested,
)
from agendalab.domain.events.publisher import EventObserver, EventPublisher
from agendalab.infrastructure.notifications.inbox import NotificationInbox
from agendalab.infrastructure.notifications.log_notifier import LogNotifier

AGORA = datetime(2026, 8, 6, 10, 30)
ESPACO = "LAB-01"
SOLICITANTE = "2019001234"
GESTOR = "1998007766"


def solicitada(space_code: str = ESPACO) -> BookingRequested:
    return BookingRequested(
        booking_id=uuid4(),
        space_code=space_code,
        requester_id=SOLICITANTE,
        occurred_at=AGORA,
    )


def aprovada() -> BookingApproved:
    return BookingApproved(
        booking_id=uuid4(),
        space_code=ESPACO,
        requester_id=SOLICITANTE,
        occurred_at=AGORA,
        decided_by=GESTOR,
    )


# --- conformidade com o contrato do domínio -----------------------------------------------------


@pytest.mark.parametrize("observador", [LogNotifier(), NotificationInbox()], ids=lambda o: type(o).__name__)
def test_o_observador_satisfaz_o_protocolo(observador: EventObserver) -> None:
    """Estrutural, sem herança: nenhum dos dois importa `EventObserver` para funcionar."""
    assert isinstance(observador, EventObserver)


# --- NotificationInbox --------------------------------------------------------------------------


def test_a_caixa_nasce_vazia() -> None:
    assert NotificationInbox().all() == []


def test_a_caixa_guarda_a_notificacao_do_evento() -> None:
    caixa = NotificationInbox()
    caixa.handle(solicitada())

    (notificacao,) = caixa.all()
    assert (notificacao.space_code, notificacao.occurred_at) == (ESPACO, AGORA)
    assert "solicitada" in notificacao.message


def test_a_caixa_preserva_a_ordem_de_chegada() -> None:
    """Uma caixa de entrada fora de ordem não conta a história do que aconteceu."""
    caixa = NotificationInbox()
    caixa.handle(solicitada())
    caixa.handle(aprovada())

    primeira, segunda = caixa.all()
    assert "solicitada" in primeira.message
    assert "aprovada" in segunda.message


def test_a_caixa_recebe_pelo_publicador() -> None:
    """Como ela vai funcionar de verdade: inscrita, sem que o publicador saiba o que ela é."""
    caixa = NotificationInbox()
    publicador = EventPublisher()
    publicador.subscribe(caixa)

    publicador.publish(solicitada())

    assert len(caixa.all()) == 1


def test_a_lista_devolvida_nao_e_a_lista_interna() -> None:
    """Quem consulta a caixa não pode esvaziá-la sem querer — `GET /notifications` é leitura."""
    caixa = NotificationInbox()
    caixa.handle(solicitada())

    caixa.all().clear()

    assert len(caixa.all()) == 1


# --- LogNotifier --------------------------------------------------------------------------------


def test_o_notificador_registra_a_mensagem_no_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        LogNotifier().handle(aprovada())

    assert "aprovada" in caplog.text
    assert ESPACO in caplog.text


def test_o_notificador_registra_pelo_publicador(caplog: pytest.LogCaptureFixture) -> None:
    publicador = EventPublisher()
    publicador.subscribe(LogNotifier())

    with caplog.at_level(logging.INFO):
        publicador.publish(solicitada())

    assert "solicitada" in caplog.text


# --- os dois juntos, como no composition root ---------------------------------------------------


def test_os_dois_canais_recebem_o_mesmo_evento(caplog: pytest.LogCaptureFixture) -> None:
    """Um evento, dois canais, nenhum conhecendo o outro — é o Observer inteiro numa linha."""
    caixa = NotificationInbox()
    publicador = EventPublisher()
    publicador.subscribe(LogNotifier())
    publicador.subscribe(caixa)

    with caplog.at_level(logging.INFO):
        publicador.publish(aprovada())

    assert len(caixa.all()) == 1
    assert "aprovada" in caplog.text


def test_os_dois_canais_dizem_a_mesma_coisa(caplog: pytest.LogCaptureFixture) -> None:
    """A frase é montada num lugar só, então log e caixa não têm como divergir."""
    caixa = NotificationInbox()
    evento: BookingEvent = aprovada()

    with caplog.at_level(logging.INFO):
        LogNotifier().handle(evento)
    caixa.handle(evento)

    assert caixa.all()[0].message in caplog.text


def test_a_falha_de_um_canal_nao_impede_o_outro(caplog: pytest.LogCaptureFixture) -> None:
    """O isolamento que o `EventPublisher` garante, verificado com os observadores de verdade."""

    class CanalQuebrado:
        def handle(self, event: BookingEvent) -> None:
            raise RuntimeError("o canal caiu")

    caixa = NotificationInbox()
    publicador = EventPublisher()
    publicador.subscribe(CanalQuebrado())
    publicador.subscribe(caixa)

    with caplog.at_level(logging.INFO):
        publicador.publish(aprovada())

    assert len(caixa.all()) == 1
