"""Os quatro eventos de reserva — ADR-0006.

Nomeados no particípio porque descrevem algo que **já aconteceu**: são fato consumado, não pedido.
Daí também a imutabilidade — reescrever um evento seria reescrever o passado.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from uuid import uuid4

import pytest

from agendalab.domain.events.booking_events import (
    BookingApproved,
    BookingCancelled,
    BookingEvent,
    BookingRejected,
    BookingRequested,
)

AGORA = datetime(2026, 8, 6, 10, 30)
RESERVA = uuid4()
GESTOR = "chefe.laboratorio"
MOTIVO = "Laboratório em manutenção na data solicitada."

BASE: dict[str, object] = {
    "booking_id": RESERVA,
    "space_code": "LAB-01",
    "requester_id": "2019001234",
    "occurred_at": AGORA,
}

EVENTOS = [
    BookingRequested(**BASE),  # type: ignore[arg-type]
    BookingApproved(**BASE, decided_by=GESTOR),  # type: ignore[arg-type]
    BookingRejected(**BASE, decided_by=GESTOR, reason=MOTIVO),  # type: ignore[arg-type]
    BookingCancelled(**BASE, decided_by=GESTOR),  # type: ignore[arg-type]
]

IDS = [type(evento).__name__ for evento in EVENTOS]


@pytest.mark.parametrize("evento", EVENTOS, ids=IDS)
def test_todo_evento_e_um_evento_de_reserva(evento: BookingEvent) -> None:
    """É o tipo comum que `EventObserver.handle` recebe — um observador só precisa conhecer ele."""
    assert isinstance(evento, BookingEvent)


@pytest.mark.parametrize("evento", EVENTOS, ids=IDS)
def test_todo_evento_identifica_a_reserva_o_espaco_e_o_solicitante(evento: BookingEvent) -> None:
    """O notificador monta a mensagem sem consultar o banco."""
    assert evento.booking_id == RESERVA
    assert evento.space_code == "LAB-01"
    assert evento.requester_id == "2019001234"
    assert evento.occurred_at == AGORA


@pytest.mark.parametrize("evento", EVENTOS, ids=IDS)
def test_todo_evento_e_imutavel(evento: BookingEvent) -> None:
    """Reescrever um evento seria reescrever o passado."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        evento.space_code = "SALA-01"  # type: ignore[misc]


def test_a_solicitacao_nao_tem_decisor() -> None:
    """Ninguém decidiu ainda: quem solicitou já está em `requester_id`."""
    assert not hasattr(BookingRequested(**BASE), "decided_by")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "evento",
    [evento for evento in EVENTOS if not isinstance(evento, BookingRequested)],
    ids=[nome for nome, evento in zip(IDS, EVENTOS, strict=True)
         if not isinstance(evento, BookingRequested)],
)
def test_toda_decisao_registra_quem_decidiu(evento: BookingEvent) -> None:
    """A trilha da §4.1 chega ao notificador junto com o evento."""
    assert evento.decided_by == GESTOR  # type: ignore[attr-defined]


def test_a_rejeicao_carrega_o_motivo() -> None:
    """RN-14 — o motivo é obrigatório na rejeição, e é o que o solicitante precisa saber."""
    rejeitada = BookingRejected(**BASE, decided_by=GESTOR, reason=MOTIVO)  # type: ignore[arg-type]
    assert rejeitada.reason == MOTIVO


def test_os_quatro_eventos_sao_distintos() -> None:
    """Uma transição por evento — o observador reage pelo tipo, sem inspecionar campo algum."""
    assert len({type(evento) for evento in EVENTOS}) == 4
