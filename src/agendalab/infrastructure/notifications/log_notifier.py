"""`LogNotifier` — o observador que registra o evento no log da aplicação.

Não herda de `EventObserver` nem o importa: a conformidade é estrutural, como nas políticas e nas
duplas de repositório. Um observador que não precisa importar nada para servir é a forma mais direta
de dizer que o domínio não depende dele.

É o canal "de produção" do MVP. A `NotificationInbox` existe ao lado dele por demonstrabilidade, não
por redundância — log não aparece em captura de tela.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agendalab.infrastructure.notifications.notification import notification_from

if TYPE_CHECKING:
    from agendalab.domain.events.booking_events import BookingEvent

logger = logging.getLogger(__name__)


class LogNotifier:
    def handle(self, event: BookingEvent) -> None:
        """Registra a mensagem. Um canal a mais no sistema é uma classe como esta e uma linha de
        inscrição no composition root — nenhum caso de uso muda."""
        logger.info(notification_from(event).message)
