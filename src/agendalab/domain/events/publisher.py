"""Sujeito e observador do padrão Observer (ADR-0006).

O publicador vive no domínio e conhece apenas a interface `EventObserver`. Quem a implementa —
log, caixa de entrada, e-mail — vive na infraestrutura. Um canal novo é uma classe a mais e uma
linha de inscrição no composition root; nenhum caso de uso muda.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from agendalab.domain.events.booking_events import BookingEvent

logger = logging.getLogger(__name__)


@runtime_checkable
class EventObserver(Protocol):
    def handle(self, event: BookingEvent) -> None:
        """Reage ao evento. Uma falha aqui não interrompe a operação que o originou."""


class EventPublisher:
    def __init__(self) -> None:
        # Lista, e não conjunto: a entrega segue a ordem de inscrição.
        self._observers: list[EventObserver] = []

    def subscribe(self, observer: EventObserver) -> None:
        self._observers.append(observer)

    def publish(self, event: BookingEvent) -> None:
        """Entrega o evento a todos os inscritos, isolando a falha de cada um.

        Uma reserva legitimamente aprovada não pode ser desfeita porque o log falhou: notificação
        é efeito colateral, e efeito colateral não invalida o fato. A exceção é registrada e não
        se propaga, e não impede os demais observadores de receberem o evento.

        `Exception`, e não `BaseException`: `KeyboardInterrupt` e `SystemExit` precisam continuar
        subindo, senão um Ctrl-C viraria silêncio.
        """
        for observer in self._observers:
            try:
                observer.handle(event)
            except Exception:
                logger.exception(
                    "Observador %s falhou ao tratar %s; os demais seguem sendo notificados.",
                    type(observer).__name__,
                    type(event).__name__,
                )
