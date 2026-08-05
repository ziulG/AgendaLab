"""Os eventos de reserva — o vocabulário do padrão Observer (ADR-0006).

Nomeados no particípio porque descrevem algo que **já aconteceu**: `BookingApproved` é um fato
consumado, não um pedido de aprovação. Daí também a imutabilidade — reescrever um evento seria
reescrever o passado.

Cada evento carrega o que um notificador precisa para montar a mensagem **sem consultar o banco**.
É isso que permite trocar o canal — log, e-mail, webhook — sem que o domínio saiba qual é.

`occurred_at` chega por parâmetro, como o `now` das transições: o domínio não lê relógio.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class BookingEvent(ABC):
    """O que todo evento de reserva carrega, e o tipo que `EventObserver.handle` recebe.

    `ABC` marca a intenção: nenhum código publica um `BookingEvent` genérico. Python só impede a
    instanciação quando há membro abstrato, e não há nenhum que faça sentido aqui — inventar um
    seria maquinaria a serviço de uma anotação.
    """

    booking_id: UUID
    space_code: str
    requester_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class BookingRequested(BookingEvent):
    """A reserva foi solicitada. Ninguém decidiu ainda — quem pediu está em `requester_id`."""


@dataclass(frozen=True)
class BookingApproved(BookingEvent):
    decided_by: str


@dataclass(frozen=True)
class BookingRejected(BookingEvent):
    decided_by: str
    reason: str  # RN-14 — é o que o solicitante precisa saber


@dataclass(frozen=True)
class BookingCancelled(BookingEvent):
    decided_by: str
