"""As 12 células da tabela de transições — §5.5 da especificação e ADR-0005.

O produto cartesiano de 4 estados × 3 operações é gerado, não escrito à mão: nenhuma célula pode
ser esquecida, e acrescentar um quinto estado ao `BookingStatus` faz aparecerem três casos novos
que ninguém precisou lembrar de escrever.

O mapa `TRANSICOES_PERMITIDAS` é a tabela da especificação em código. O que não está nele é ❌.
"""

from __future__ import annotations

from datetime import datetime
from itertools import product
from uuid import uuid4

import pytest

from agendalab.domain.actor import Actor, Role
from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.errors import InvalidStateTransition, MissingRejectionReason
from agendalab.domain.value_objects.time_slot import TimeSlot

OPERACOES = ("approve", "reject", "cancel")

# A tabela da §5.5: as 6 células ✅. Toda combinação ausente daqui é uma célula ❌.
TRANSICOES_PERMITIDAS = {
    (BookingStatus.PENDING, "approve"): BookingStatus.APPROVED,
    (BookingStatus.PENDING, "reject"): BookingStatus.REJECTED,
    (BookingStatus.PENDING, "cancel"): BookingStatus.CANCELLED,
    (BookingStatus.APPROVED, "cancel"): BookingStatus.CANCELLED,
}

CELULAS = list(product(BookingStatus, OPERACOES))

SOLICITANTE = Actor(user_id="2019001234", role=Role.REQUESTER)
GESTOR = Actor(user_id="chefe.laboratorio", role=Role.MANAGER)
AGORA = datetime(2026, 8, 6, 10, 30)
MOTIVO = "Laboratório em manutenção na data solicitada."


def reserva(status: BookingStatus) -> Booking:
    """Reserva do `SOLICITANTE`, para que o cancelamento por ele passe pela RN-12."""
    return Booking(
        id=uuid4(),
        space_code="LAB-01",
        requester_id=SOLICITANTE.user_id,
        slot=TimeSlot(datetime(2026, 8, 20, 14), datetime(2026, 8, 20, 16)),
        purpose="Aula prática de Redes de Computadores",
        attendees=25,
        status=status,
        created_at=datetime(2026, 8, 5, 9, 12, 33),
    )


def executar(booking: Booking, operacao: str, ator: Actor = GESTOR) -> None:
    """Chama a transição pelo nome da operação, que é a coluna da tabela da §5.5."""
    if operacao == "reject":
        booking.reject(ator, MOTIVO, AGORA)
    elif operacao == "approve":
        booking.approve(ator, AGORA)
    else:
        booking.cancel(ator, AGORA)


def test_a_tabela_tem_doze_celulas() -> None:
    """4 estados × 3 operações. Se este número mudar, a §5.5 mudou junto."""
    assert len(CELULAS) == 12
    assert len(TRANSICOES_PERMITIDAS) == 4


# --- as 6 células ✅ --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("origem", "operacao"),
    [celula for celula in CELULAS if celula in TRANSICOES_PERMITIDAS],
    ids=lambda valor: valor if isinstance(valor, str) else str(valor),
)
def test_transicao_permitida_leva_ao_estado_esperado(origem: BookingStatus, operacao: str) -> None:
    """RN-13 — as células ✅ da §5.5."""
    booking = reserva(origem)
    executar(booking, operacao)
    assert booking.status is TRANSICOES_PERMITIDAS[(origem, operacao)]


@pytest.mark.parametrize(
    ("origem", "operacao"),
    [celula for celula in CELULAS if celula in TRANSICOES_PERMITIDAS],
    ids=lambda valor: valor if isinstance(valor, str) else str(valor),
)
def test_transicao_permitida_registra_quem_decidiu_e_quando(
    origem: BookingStatus, operacao: str
) -> None:
    """A trilha de decisão da §4.1. O instante vem de fora — o domínio não lê relógio."""
    booking = reserva(origem)
    executar(booking, operacao)
    assert booking.decided_by == GESTOR.user_id
    assert booking.decided_at == AGORA


# --- as 6 células ❌ --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("origem", "operacao"),
    [celula for celula in CELULAS if celula not in TRANSICOES_PERMITIDAS],
    ids=lambda valor: valor if isinstance(valor, str) else str(valor),
)
def test_transicao_proibida_e_recusada(origem: BookingStatus, operacao: str) -> None:
    """RN-13 — as células ❌ da §5.5, incluindo tudo a partir dos dois estados terminais."""
    booking = reserva(origem)
    with pytest.raises(InvalidStateTransition) as erro:
        executar(booking, operacao)
    assert erro.value.rule == "RN-13"
    assert operacao in erro.value.message


@pytest.mark.parametrize(
    ("origem", "operacao"),
    [celula for celula in CELULAS if celula not in TRANSICOES_PERMITIDAS],
    ids=lambda valor: valor if isinstance(valor, str) else str(valor),
)
def test_transicao_proibida_nao_altera_a_reserva(origem: BookingStatus, operacao: str) -> None:
    """Recusa não é meia transição: a reserva sai igual a como entrou."""
    booking = reserva(origem)
    with pytest.raises(InvalidStateTransition):
        executar(booking, operacao)
    assert booking.status is origem
    assert booking.decided_by is None
    assert booking.decided_at is None
    assert booking.rejection_reason is None


# --- RN-14: a rejeição exige motivo ----------------------------------------------------------


def test_rejeicao_guarda_o_motivo() -> None:
    """RN-14."""
    booking = reserva(BookingStatus.PENDING)
    booking.reject(GESTOR, MOTIVO, AGORA)
    assert booking.rejection_reason == MOTIVO


@pytest.mark.parametrize("motivo", ["", "   ", "\n"], ids=["vazio", "espacos", "quebra_de_linha"])
def test_rejeicao_sem_motivo_e_recusada(motivo: str) -> None:
    """RN-14 — motivo em branco não é motivo."""
    booking = reserva(BookingStatus.PENDING)
    with pytest.raises(MissingRejectionReason) as erro:
        booking.reject(GESTOR, motivo, AGORA)
    assert erro.value.rule == "RN-14"


def test_rejeicao_sem_motivo_nao_altera_a_reserva() -> None:
    """RN-14 — a validação vem antes da transição, não depois."""
    booking = reserva(BookingStatus.PENDING)
    with pytest.raises(MissingRejectionReason):
        booking.reject(GESTOR, "", AGORA)
    assert booking.status is BookingStatus.PENDING
    assert booking.decided_by is None


def test_aprovacao_e_cancelamento_nao_preenchem_motivo() -> None:
    """Só a rejeição exige motivo; as outras duas transições não o inventam."""
    aprovada = reserva(BookingStatus.PENDING)
    aprovada.approve(GESTOR, AGORA)
    assert aprovada.rejection_reason is None

    cancelada = reserva(BookingStatus.PENDING)
    cancelada.cancel(GESTOR, AGORA)
    assert cancelada.rejection_reason is None
