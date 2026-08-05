"""`Booking` — os quatro estados e os campos da §4.1 da especificação.

Nesta etapa a reserva é estrutura de dados: `approve`, `reject` e `cancel` chegam na task 03,
com o padrão State.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.value_objects.time_slot import TimeSlot


def nova_reserva(**alteracoes: object) -> Booking:
    campos: dict[str, object] = {
        "id": uuid4(),
        "space_code": "LAB-01",
        "requester_id": "2019001234",
        "slot": TimeSlot(datetime(2026, 8, 20, 14), datetime(2026, 8, 20, 16)),
        "purpose": "Aula prática de Redes de Computadores",
        "attendees": 25,
        "status": BookingStatus.PENDING,
        "created_at": datetime(2026, 8, 5, 9, 12, 33),
    }
    return Booking(**(campos | alteracoes))  # type: ignore[arg-type]


def test_os_quatro_estados_existem() -> None:
    """§5.5 — e `CANCELLED` com dois `L`, conforme o glossário."""
    assert [estado.value for estado in BookingStatus] == [
        "PENDING",
        "APPROVED",
        "REJECTED",
        "CANCELLED",
    ]


def test_reserva_guarda_os_campos_da_especificacao() -> None:
    reserva = nova_reserva()
    assert isinstance(reserva.id, UUID)
    assert reserva.space_code == "LAB-01"
    assert reserva.requester_id == "2019001234"
    assert reserva.slot.duration_hours() == 2.0
    assert reserva.purpose == "Aula prática de Redes de Computadores"
    assert reserva.attendees == 25
    assert reserva.status is BookingStatus.PENDING
    assert reserva.created_at == datetime(2026, 8, 5, 9, 12, 33)


def test_trilha_de_decisao_nasce_vazia() -> None:
    """§4.1 — `decided_by`, `decided_at` e `rejection_reason` são nulos até haver decisão."""
    reserva = nova_reserva()
    assert reserva.decided_by is None
    assert reserva.decided_at is None
    assert reserva.rejection_reason is None


def test_trilha_de_decisao_aceita_ser_preenchida() -> None:
    reserva = nova_reserva(
        status=BookingStatus.REJECTED,
        decided_by="chefe.laboratorio",
        decided_at=datetime(2026, 8, 6, 10, 0),
        rejection_reason="Laboratório em manutenção na data solicitada.",
    )
    assert reserva.decided_by == "chefe.laboratorio"
    assert reserva.decided_at == datetime(2026, 8, 6, 10, 0)
    assert reserva.rejection_reason == "Laboratório em manutenção na data solicitada."
