"""A tradução de evento de domínio para notificação legível.

Ela vive na infraestrutura, e não no domínio, por uma questão de fronteira: "Reserva em LAB-01
aprovada por 1998007766" é texto voltado a uma pessoa, e escolher esse texto não é regra de negócio.
O domínio publica fatos; quem os transforma em frase é o canal.

E vive num arquivo só, compartilhado por `LogNotifier` e `NotificationInbox`, porque duas cópias da
mesma frase divergem — e um log dizendo uma coisa e a caixa de entrada dizendo outra sobre o mesmo
evento é o tipo de inconsistência que ninguém percebe até a demonstração.

O despacho é por **tabela**, não por cadeia de `isinstance`. Um evento novo no domínio acrescenta
uma linha ao dicionário, e enquanto ninguém a acrescenta a notificação sai genérica em vez de
estourar — notificação é efeito colateral, e nenhum efeito colateral pode derrubar a operação que o
originou (ADR-0006).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from agendalab.domain.events.booking_events import (
    BookingApproved,
    BookingCancelled,
    BookingEvent,
    BookingRejected,
    BookingRequested,
)

# No particípio, como os próprios eventos: descrevem algo que já aconteceu.
_VERBO: dict[type[BookingEvent], str] = {
    BookingRequested: "solicitada",
    BookingApproved: "aprovada",
    BookingRejected: "rejeitada",
    BookingCancelled: "cancelada",
}
_VERBO_DESCONHECIDO = "atualizada"


@dataclass(frozen=True, slots=True)
class Notification:
    """O que um canal entrega a uma pessoa.

    Carrega os metadados do evento **e** a frase pronta. Os dois: a frase é o que aparece na tela, e
    os identificadores são o que permite a quem consome a caixa filtrar ou navegar sem ter que
    interpretar texto.

    Imutável, como o evento que a originou.
    """

    booking_id: UUID
    space_code: str
    requester_id: str
    occurred_at: datetime
    message: str


def notification_from(event: BookingEvent) -> Notification:
    """A notificação correspondente ao evento."""
    return Notification(
        booking_id=event.booking_id,
        space_code=event.space_code,
        requester_id=event.requester_id,
        occurred_at=event.occurred_at,
        message=_mensagem(event),
    )


def _mensagem(event: BookingEvent) -> str:
    """A frase, montada a partir do que o evento carrega.

    `getattr` em vez de `isinstance`: `decided_by` existe em três dos quatro eventos e `reason` em
    um só, e perguntar pelo campo é mais direto do que perguntar pelo tipo para depois ler o campo.
    """
    verbo = _VERBO.get(type(event), _VERBO_DESCONHECIDO)
    frase = f"Reserva {event.booking_id} em {event.space_code} {verbo}"

    decidida_por = getattr(event, "decided_by", None)
    if decidida_por is not None:
        frase += f" por {decidida_por}"

    motivo = getattr(event, "reason", None)
    if motivo:
        frase += f" — motivo: {motivo.rstrip('.')}"

    return f"{frase}."
