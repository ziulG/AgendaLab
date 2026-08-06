"""Ida e volta entre entidade e modelo, campo a campo.

O ADR-0003 registra como risco de média probabilidade que "mapper e modelo saiam de sincronia ao
evoluir uma entidade", e aponta este teste como mitigação. Ele não confere alguns campos escolhidos
a dedo: percorre os campos declarados na dataclass e exige que **todos** sobrevivam. Um atributo
novo na entidade que ninguém tenha mapeado quebra a suíte no dia em que for acrescentado.

Não toca banco — a conversão é função pura sobre objetos. Fica em `integration/` por vizinhança com
o que testa, já que o modelo que ele converte é o de persistência.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from uuid import uuid4

import pytest

from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.domain.value_objects.time_slot import TimeSlot
from agendalab.infrastructure.persistence.mappers import (
    apply_booking,
    to_booking,
    to_booking_model,
    to_space,
    to_space_model,
)

QUINTA = datetime(2026, 8, 20, 14, 0)
CRIACAO = datetime(2026, 8, 5, 9, 0)
DECISAO = datetime(2026, 8, 6, 10, 30)


def espaco(**alteracoes: object) -> Space:
    campos: dict[str, object] = {
        "code": "LAB-01",
        "name": "Laboratório de Redes",
        "kind": SpaceKind.LAB,
        "capacity": 30,
        "active": True,
    }
    return Space(**(campos | alteracoes))  # type: ignore[arg-type]


def reserva(**alteracoes: object) -> Booking:
    campos: dict[str, object] = {
        "id": uuid4(),
        "space_code": "LAB-01",
        "requester_id": "2019001234",
        "slot": TimeSlot(QUINTA, datetime(2026, 8, 20, 16, 0)),
        "purpose": "Aula prática de Redes de Computadores",
        "attendees": 25,
        "status": BookingStatus.PENDING,
        "created_at": CRIACAO,
        "decided_by": None,
        "decided_at": None,
        "rejection_reason": None,
    }
    return Booking(**(campos | alteracoes))  # type: ignore[arg-type]


DECIDIDA = {
    "status": BookingStatus.REJECTED,
    "decided_by": "1998007766",
    "decided_at": DECISAO,
    "rejection_reason": "O laboratório estará em manutenção preventiva.",
}


# --- Space -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "original",
    [espaco(), espaco(active=False), espaco(kind=SpaceKind.AUDITORIUM, capacity=200)],
    ids=["ativo", "inativo", "auditório"],
)
def test_espaco_sobrevive_a_ida_e_volta(original: Space) -> None:
    assert to_space(to_space_model(original)) == original


def test_nenhum_campo_do_espaco_fica_para_tras() -> None:
    """A guarda contra o campo esquecido: a lista sai da própria dataclass, não de uma cópia."""
    original = espaco(active=False)
    voltou = to_space(to_space_model(original))
    for campo in dataclasses.fields(Space):
        assert getattr(voltou, campo.name) == getattr(original, campo.name), (
            f"o campo `{campo.name}` não sobreviveu ao mapeamento"
        )


def test_o_tipo_do_espaco_volta_como_enum_e_nao_como_texto() -> None:
    """A coluna guarda texto; a entidade precisa do enum, senão `policy_for` falha."""
    voltou = to_space(to_space_model(espaco(kind=SpaceKind.AUDITORIUM)))
    assert voltou.kind is SpaceKind.AUDITORIUM


# --- Booking -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "original",
    [reserva(), reserva(**DECIDIDA), reserva(status=BookingStatus.APPROVED)],
    ids=["pendente", "rejeitada com trilha", "aprovada"],
)
def test_reserva_sobrevive_a_ida_e_volta(original: Booking) -> None:
    assert to_booking(to_booking_model(original)) == original


def test_nenhum_campo_da_reserva_fica_para_tras() -> None:
    """Onze campos, incluindo a trilha de decisão inteira. Um esquecido quebra aqui."""
    original = reserva(**DECIDIDA)
    voltou = to_booking(to_booking_model(original))
    for campo in dataclasses.fields(Booking):
        assert getattr(voltou, campo.name) == getattr(original, campo.name), (
            f"o campo `{campo.name}` não sobreviveu ao mapeamento"
        )


def test_o_intervalo_volta_como_objeto_de_valor() -> None:
    """Duas colunas na tabela, um `TimeSlot` na entidade — e ele precisa voltar operável."""
    original = reserva()
    voltou = to_booking(to_booking_model(original))
    assert isinstance(voltou.slot, TimeSlot)
    assert voltou.slot.duration_hours() == original.slot.duration_hours()


def test_o_status_volta_como_enum_e_nao_como_texto() -> None:
    """`Booking._state` indexa um dicionário por `BookingStatus`: texto ali levantaria `KeyError`."""
    voltou = to_booking(to_booking_model(reserva(status=BookingStatus.APPROVED)))
    assert voltou.status is BookingStatus.APPROVED
    voltou._state  # noqa: B018 — o acesso é a verificação: resolve o estado sem levantar


def test_a_trilha_nula_continua_nula() -> None:
    """Uma reserva sobre a qual ninguém decidiu não pode voltar com campos preenchidos."""
    voltou = to_booking(to_booking_model(reserva()))
    assert (voltou.decided_by, voltou.decided_at, voltou.rejection_reason) == (None, None, None)


# --- apply_booking, usado pelo `update` ---------------------------------------------------------


def test_aplicar_a_entidade_sobre_um_modelo_existente() -> None:
    """O caminho do `update`: a linha já existe e recebe o estado novo, sem virar outra linha."""
    original = reserva()
    modelo = to_booking_model(original)

    decidida = reserva(id=original.id, **DECIDIDA)
    apply_booking(modelo, decidida)

    assert to_booking(modelo) == decidida


def test_aplicar_nao_troca_a_identidade_da_linha() -> None:
    original = reserva()
    modelo = to_booking_model(original)
    apply_booking(modelo, reserva(id=original.id, status=BookingStatus.APPROVED))
    assert modelo.id == original.id
