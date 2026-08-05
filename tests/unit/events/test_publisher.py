"""`EventPublisher` — distribuição e isolamento de falhas (ADR-0006).

O teste central deste arquivo é o do isolamento: uma reserva legitimamente aprovada não pode ser
desfeita porque o log falhou. Notificação é efeito colateral, e efeito colateral não invalida o
fato.

Os espiões são definidos aqui mesmo — nenhum log, HTTP ou banco entra nesta suíte.
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
from agendalab.domain.events.publisher import EventPublisher

AGORA = datetime(2026, 8, 6, 10, 30)


def evento(**alteracoes: object) -> BookingRequested:
    campos: dict[str, object] = {
        "booking_id": uuid4(),
        "space_code": "LAB-01",
        "requester_id": "2019001234",
        "occurred_at": AGORA,
    }
    return BookingRequested(**(campos | alteracoes))  # type: ignore[arg-type]


class Espiao:
    """Observador que apenas guarda o que recebeu, na ordem em que recebeu."""

    def __init__(self, nome: str = "espiao") -> None:
        self.nome = nome
        self.recebidos: list[BookingEvent] = []

    def handle(self, event: BookingEvent) -> None:
        self.recebidos.append(event)


class EspiaoQuebrado:
    """Observador que sempre falha. Existe para provar que a falha fica contida."""

    def __init__(self) -> None:
        self.chamadas = 0

    def handle(self, event: BookingEvent) -> None:
        self.chamadas += 1
        raise RuntimeError("o canal de notificação caiu")


# --- distribuição ----------------------------------------------------------------------------


def test_publicar_sem_observador_nao_quebra() -> None:
    """O publicador é criado vazio no composition root; publicar antes de inscrever é legítimo."""
    EventPublisher().publish(evento())


def test_o_evento_chega_ao_observador_inscrito() -> None:
    publicador = EventPublisher()
    espiao = Espiao()
    publicador.subscribe(espiao)

    publicado = evento()
    publicador.publish(publicado)

    assert espiao.recebidos == [publicado]


def test_o_evento_chega_a_todos_os_inscritos() -> None:
    """RN-15 — um canal novo é uma inscrição a mais, e nenhum canal existente perde o evento."""
    publicador = EventPublisher()
    espioes = [Espiao(f"canal-{i}") for i in range(3)]
    for espiao in espioes:
        publicador.subscribe(espiao)

    publicado = evento()
    publicador.publish(publicado)

    assert all(espiao.recebidos == [publicado] for espiao in espioes)


def test_a_entrega_segue_a_ordem_de_inscricao() -> None:
    ordem: list[str] = []

    class Registrador:
        def __init__(self, nome: str) -> None:
            self.nome = nome

        def handle(self, event: BookingEvent) -> None:
            ordem.append(self.nome)

    publicador = EventPublisher()
    for nome in ("primeiro", "segundo", "terceiro"):
        publicador.subscribe(Registrador(nome))

    publicador.publish(evento())

    assert ordem == ["primeiro", "segundo", "terceiro"]


def test_o_observador_recebe_eventos_sucessivos() -> None:
    publicador = EventPublisher()
    espiao = Espiao()
    publicador.subscribe(espiao)

    solicitada = evento()
    aprovada = BookingApproved(
        booking_id=solicitada.booking_id,
        space_code="LAB-01",
        requester_id="2019001234",
        occurred_at=AGORA,
        decided_by="chefe.laboratorio",
    )
    publicador.publish(solicitada)
    publicador.publish(aprovada)

    assert espiao.recebidos == [solicitada, aprovada]


# --- isolamento de falhas — o teste central da task ------------------------------------------


def test_falha_de_observador_nao_escapa_do_publish() -> None:
    """Uma reserva aprovada não pode ser desfeita porque o notificador caiu."""
    publicador = EventPublisher()
    publicador.subscribe(EspiaoQuebrado())

    publicador.publish(evento())  # não levanta


def test_falha_de_observador_nao_impede_os_seguintes() -> None:
    """O observador quebrado fica no meio: o anterior e o posterior precisam receber assim mesmo."""
    publicador = EventPublisher()
    antes, quebrado, depois = Espiao("antes"), EspiaoQuebrado(), Espiao("depois")
    publicador.subscribe(antes)
    publicador.subscribe(quebrado)
    publicador.subscribe(depois)

    publicado = evento()
    publicador.publish(publicado)

    assert antes.recebidos == [publicado]
    assert depois.recebidos == [publicado]
    assert quebrado.chamadas == 1


def test_a_falha_do_observador_e_registrada(caplog: pytest.LogCaptureFixture) -> None:
    """ADR-0006 — a exceção "é registrada e não se propaga".

    Sem esta asserção, o teste não distingue isolar de engolir em silêncio: a mitigação que o ADR
    promete para a falha silenciosa é justamente a linha de log.
    """
    publicador = EventPublisher()
    publicador.subscribe(EspiaoQuebrado())

    with caplog.at_level(logging.ERROR):
        publicador.publish(evento())

    assert caplog.records, "a falha do observador precisa deixar rastro"
    assert "EspiaoQuebrado" in caplog.text
    assert "o canal de notificação caiu" in caplog.text


def test_varios_observadores_quebrados_nao_se_atrapalham() -> None:
    publicador = EventPublisher()
    sobrevivente = Espiao()
    publicador.subscribe(EspiaoQuebrado())
    publicador.subscribe(EspiaoQuebrado())
    publicador.subscribe(sobrevivente)

    publicado = evento()
    publicador.publish(publicado)

    assert sobrevivente.recebidos == [publicado]


def test_interrupcao_do_processo_nao_e_engolida() -> None:
    """`except Exception`, e não `BaseException`: um Ctrl-C precisa continuar passando."""

    class Interrompe:
        def handle(self, event: BookingEvent) -> None:
            raise KeyboardInterrupt

    publicador = EventPublisher()
    publicador.subscribe(Interrompe())

    with pytest.raises(KeyboardInterrupt):
        publicador.publish(evento())
