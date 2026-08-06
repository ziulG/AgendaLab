"""`NotificationInbox` — a caixa de entrada consultável em `GET /notifications`.

Existe por uma razão declarada no ADR-0006: **tornar o efeito do Observer visível**. Sem ela, a
única evidência de que o padrão funciona estaria no log do servidor, e a defesa precisaria pedir que
se acreditasse nela. Com ela, a relação de causa e efeito é demonstrável — aprovar uma reserva,
consultar a caixa, ver a notificação.

**Vive em memória e se perde no reinício, de propósito.** É instrumento de demonstração, não
funcionalidade de produto; está assim registrado no ADR-0006 e no README, e não deve ser "corrigida"
para persistir. Persistir notificações exigiria decidir política de retenção, marcação de lida e
limpeza — problemas de um produto que este MVP não é.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agendalab.infrastructure.notifications.notification import notification_from

if TYPE_CHECKING:
    from agendalab.domain.events.booking_events import BookingEvent
    from agendalab.infrastructure.notifications.notification import Notification


class NotificationInbox:
    def __init__(self) -> None:
        # Lista, e não conjunto: a ordem em que as coisas aconteceram é o que a caixa conta.
        self._notifications: list[Notification] = []

    def handle(self, event: BookingEvent) -> None:
        self._notifications.append(notification_from(event))

    def all(self) -> list[Notification]:
        """As notificações, da mais antiga para a mais recente.

        Devolve uma cópia da lista. Consultar a caixa é leitura, e quem chama não deve conseguir
        esvaziá-la sem querer — nem a rota `GET /notifications`, nem um teste distraído.
        """
        return list(self._notifications)
