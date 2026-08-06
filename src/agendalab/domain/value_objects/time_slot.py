"""`TimeSlot` — o intervalo pretendido por uma reserva.

Objeto de valor: não tem identidade própria, é imutável, e dois intervalos com os mesmos limites
são o mesmo intervalo. É aqui que mora a detecção de conflito do sistema (RN-02), e é por ela ser
uma função pura sobre dois pares de datas que se testa sem banco, sem framework e sem rede.

As datas são ingênuas, sem fuso, conforme os exemplos ISO da §7.1 da especificação.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from agendalab.domain.errors import InvalidTimeSlot

SECONDS_PER_HOUR = 3600


@dataclass(frozen=True, slots=True)
class TimeSlot:
    start_at: datetime
    end_at: datetime

    def __post_init__(self) -> None:
        """RN-03 — todo intervalo deve ter `início < fim`."""
        if self.start_at >= self.end_at:
            raise InvalidTimeSlot(
                f"O fim do intervalo ({self.end_at:%d/%m/%Y %H:%M}) precisa vir depois "
                f"do início ({self.start_at:%d/%m/%Y %H:%M})."
            )

    def overlaps(self, other: TimeSlot) -> bool:
        """RN-02 — `início_a < fim_b ∧ início_b < fim_a`.

        A fórmula é simétrica por construção, e é ela que faz intervalos que apenas se tocam nas
        bordas conviverem: uma reserva das 8h às 10h não conflita com outra das 10h às 12h.
        """
        return self.start_at < other.end_at and other.start_at < self.end_at

    def duration_hours(self) -> float:
        return (self.end_at - self.start_at).total_seconds() / SECONDS_PER_HOUR

    def iso_week(self) -> tuple[int, int]:
        """Ano e número da semana ISO — segunda a domingo — em que o intervalo **começa**.

        O ano vem junto porque a semana ISO não coincide com o ano civil: 31/12/2025 pertence à
        semana 1 de 2026. Um intervalo que atravesse a virada pertence à semana do início, que é o
        que a RN-08 diz ao contar "reservas cuja data de início cai na mesma semana".
        """
        return self.start_at.isocalendar()[:2]
