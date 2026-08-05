"""Hierarquia de erros de domínio.

Cada erro carrega uma mensagem legível em português e o identificador da regra violada. A
camada de apresentação usa os dois para montar a resposta HTTP da §7.2 da especificação — o
nome da classe vira o campo `error`, e a tradução para o código de status é responsabilidade
dela, não daqui: o domínio não conhece HTTP.

Este módulo não importa nada do próprio domínio em tempo de execução. É deliberado: `TimeSlot`
levanta `InvalidTimeSlot`, e um import de volta fecharia um ciclo.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from agendalab.domain.entities.booking import BookingStatus


class DomainError(Exception):
    """Base de toda regra de negócio violada.

    `rule` é o identificador da regra da §5 da especificação. As subclasses cujo erro nasce de
    uma regra só o declaram como atributo de classe; as que cobrem mais de uma linha da §7.2
    recebem a regra na construção e a guardam na instância.
    """

    rule: str | None = None

    def __init__(self, message: str, rule: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if rule is not None:
            self.rule = rule


# --- identificador inexistente ---------------------------------------------------------------


class SpaceNotFound(DomainError):
    def __init__(self, code: str) -> None:
        super().__init__(f"Espaço {code} não encontrado.")


class BookingNotFound(DomainError):
    def __init__(self, booking_id: UUID | str) -> None:
        super().__init__(f"Reserva {booking_id} não encontrada.")


# --- conflito com o estado atual do recurso (409) ---------------------------------------------


class DuplicateSpaceCode(DomainError):
    """RN-16 — o código de um espaço é único no sistema."""

    rule = "RN-16"

    def __init__(self, code: str) -> None:
        super().__init__(f"Já existe um espaço com o código {code}.")


class ScheduleConflict(DomainError):
    """RN-01 — um espaço não pode ter duas reservas ativas com sobreposição de horário."""

    rule = "RN-01"

    def __init__(self, space_code: str, start_at: datetime, end_at: datetime) -> None:
        super().__init__(
            f"O espaço {space_code} já possui reserva ativa entre "
            f"{start_at:%H:%M} e {end_at:%H:%M} em {start_at:%d/%m/%Y}."
        )


class InvalidStateTransition(DomainError):
    """RN-13 — as transições obedecem estritamente à tabela da §5.5."""

    rule = "RN-13"

    def __init__(self, status: BookingStatus, operation: str) -> None:
        super().__init__(
            f"A operação {operation} não é permitida em uma reserva no estado {status}."
        )


# --- requisição bem formada, porém inadmissível (422) -----------------------------------------


class InactiveSpace(DomainError):
    """RN-05 — espaço inativo não aceita novas reservas."""

    rule = "RN-05"

    def __init__(self, code: str) -> None:
        super().__init__(f"O espaço {code} está inativo e não aceita novas reservas.")


class CapacityExceeded(DomainError):
    """RN-06 — o número de participantes não pode exceder a capacidade do espaço."""

    rule = "RN-06"

    def __init__(self, space_code: str, attendees: int, capacity: int) -> None:
        super().__init__(
            f"O espaço {space_code} comporta {capacity} ocupantes; "
            f"foram informados {attendees} participantes."
        )


class PolicyViolation(DomainError):
    """RN-08 a RN-10 — a política do tipo de espaço recusou a solicitação.

    Qual das três caiu só a política sabe, então ela informa a regra junto com a mensagem.
    """

    rule = "RN-07"


class InvalidTimeSlot(DomainError):
    """RN-03 na construção do intervalo, RN-04 quando o início não está no futuro."""

    rule = "RN-03"


class MissingRejectionReason(DomainError):
    """RN-14 — a rejeição exige um motivo não vazio."""

    rule = "RN-14"

    def __init__(self) -> None:
        super().__init__("A rejeição de uma reserva exige um motivo não vazio.")


# --- autorização (403) ------------------------------------------------------------------------


class PermissionDenied(DomainError):
    """RN-11 (aprovar e rejeitar) e RN-12 (cancelar) — quem chamou informa qual das duas."""

    rule = "RN-11"
