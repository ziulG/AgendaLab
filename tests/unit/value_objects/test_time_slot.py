"""`TimeSlot` — RN-02 (sobreposição) e RN-03 (integridade do intervalo).

É aqui que nasce a detecção de conflito do sistema inteiro. Todo teste deste arquivo é uma
função pura sobre dois pares de datas: sem banco, sem framework e sem relógio.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from agendalab.domain.errors import InvalidTimeSlot
from agendalab.domain.value_objects.time_slot import TimeSlot


def slot(inicio: int, fim: int) -> TimeSlot:
    """Intervalo em horas cheias do dia 20/08/2026, para encurtar os casos de teste."""
    return TimeSlot(datetime(2026, 8, 20, inicio), datetime(2026, 8, 20, fim))


# --- RN-03: todo intervalo tem início < fim -------------------------------------------------


def test_intervalo_com_fim_antes_do_inicio_e_recusado() -> None:
    """RN-03."""
    with pytest.raises(InvalidTimeSlot) as erro:
        slot(16, 14)
    assert erro.value.rule == "RN-03"


def test_intervalo_de_duracao_zero_e_recusado() -> None:
    """RN-03 — `início == fim` também viola `início < fim`."""
    with pytest.raises(InvalidTimeSlot):
        slot(14, 14)


def test_intervalo_valido_guarda_inicio_e_fim() -> None:
    intervalo = slot(14, 16)
    assert intervalo.start_at == datetime(2026, 8, 20, 14)
    assert intervalo.end_at == datetime(2026, 8, 20, 16)


# --- RN-02: sobreposição ---------------------------------------------------------------------

# Os seis casos da regra. O último é o que distingue esta implementação de uma ingênua:
# uma reserva das 8h às 10h precisa conviver com outra das 10h às 12h.
CASOS_DE_SOBREPOSICAO = [
    ("parcial", slot(14, 16), slot(15, 17), True),
    ("contido", slot(14, 18), slot(15, 16), True),
    ("contem", slot(15, 16), slot(14, 18), True),
    ("identicos", slot(14, 16), slot(14, 16), True),
    ("disjuntos", slot(8, 10), slot(14, 16), False),
    ("tocando_nas_bordas", slot(8, 10), slot(10, 12), False),
]


@pytest.mark.parametrize(
    ("primeiro", "segundo", "esperado"),
    [(a, b, esperado) for _, a, b, esperado in CASOS_DE_SOBREPOSICAO],
    ids=[nome for nome, *_ in CASOS_DE_SOBREPOSICAO],
)
def test_sobreposicao_de_intervalos(primeiro: TimeSlot, segundo: TimeSlot, esperado: bool) -> None:
    """RN-02 — `início_a < fim_b ∧ início_b < fim_a`."""
    assert primeiro.overlaps(segundo) is esperado


@pytest.mark.parametrize(
    ("primeiro", "segundo"),
    [(a, b) for _, a, b, _ in CASOS_DE_SOBREPOSICAO],
    ids=[nome for nome, *_ in CASOS_DE_SOBREPOSICAO],
)
def test_sobreposicao_e_simetrica(primeiro: TimeSlot, segundo: TimeSlot) -> None:
    """RN-02 — a ordem da comparação não pode mudar o resultado."""
    assert primeiro.overlaps(segundo) == segundo.overlaps(primeiro)


def test_intervalo_se_sobrepoe_a_si_mesmo() -> None:
    """RN-02 — reflexividade, o caso degenerado de `idênticos`."""
    intervalo = slot(14, 16)
    assert intervalo.overlaps(intervalo) is True


# --- duração ---------------------------------------------------------------------------------


def test_duracao_em_horas_cheias() -> None:
    assert slot(14, 16).duration_hours() == 2.0


def test_duracao_em_horas_fracionadas() -> None:
    meia_hora = TimeSlot(datetime(2026, 8, 20, 14), datetime(2026, 8, 20, 14, 30))
    assert meia_hora.duration_hours() == 0.5


# --- imutabilidade ---------------------------------------------------------------------------


def test_intervalo_e_imutavel() -> None:
    """Objeto de valor (§4.2): reatribuir campo é erro, não alteração silenciosa."""
    intervalo = slot(14, 16)
    with pytest.raises(dataclasses.FrozenInstanceError):
        intervalo.start_at = datetime(2026, 8, 20, 10)  # type: ignore[misc]


def test_intervalos_com_os_mesmos_limites_sao_iguais() -> None:
    """Objeto de valor não tem identidade própria: os limites são a identidade."""
    assert slot(14, 16) == slot(14, 16)
