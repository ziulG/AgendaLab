"""`SpyObserver` — a dupla de observador dos testes de caso de uso.

Mora aqui, junto das duplas de repositório, pelo mesmo motivo que elas: é dupla de teste, não código
de produção, e o ADR-0003 as coloca em `tests/`. Os observadores de verdade — log e caixa de
entrada — chegam na task 10, em `infrastructure/notifications/`.

O que ele torna possível é a única forma honesta de verificar a RN-15: um caso de uso não devolve
"publiquei um evento", e afirmar que publicou olhando o código é conferência de olho. O espião
guarda o que recebeu, e o teste pergunta a ele.

Guarda os eventos numa lista, e não num conjunto: a ordem de publicação é observável e importa
quando uma operação publica mais de um evento.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agendalab.domain.events.booking_events import BookingEvent


class SpyObserver:
    """Observador que apenas registra o que recebeu, na ordem em que recebeu."""

    def __init__(self, nome: str = "espiao") -> None:
        self.nome = nome
        self.recebidos: list[BookingEvent] = []

    def handle(self, event: BookingEvent) -> None:
        self.recebidos.append(event)

    @property
    def unico(self) -> BookingEvent:
        """O único evento recebido — e a afirmação, no acesso, de que foi mesmo só um.

        A checagem vive aqui porque o erro que ela pega é sutil: um caso de uso que publicasse duas
        vezes passaria num teste que olhasse apenas `recebidos[0]`.
        """
        assert len(self.recebidos) == 1, (
            f"esperado exatamente 1 evento, recebidos {len(self.recebidos)}: "
            f"{[type(e).__name__ for e in self.recebidos]}"
        )
        return self.recebidos[0]
