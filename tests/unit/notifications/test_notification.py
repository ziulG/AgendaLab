"""A tradução de evento de domínio para notificação legível.

Os eventos carregam identificadores; a notificação carrega uma frase. A conversão mora na
infraestrutura, e não no domínio, por uma razão de fronteira: "Reserva em LAB-01 aprovada" é texto
voltado a uma pessoa, e escolher esse texto não é regra de negócio.

Ela é compartilhada por `LogNotifier` e `NotificationInbox` — os dois canais dizem a mesma coisa
porque a frase é montada num lugar só.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from agendalab.domain.events.booking_events import (
    BookingApproved,
    BookingCancelled,
    BookingEvent,
    BookingRejected,
    BookingRequested,
)
from agendalab.infrastructure.notifications.notification import (
    Notification,
    notification_from,
)

AGORA = datetime(2026, 8, 6, 10, 30)
RESERVA = uuid4()
ESPACO = "LAB-01"
SOLICITANTE = "2019001234"
GESTOR = "1998007766"
MOTIVO = "O laboratório estará em manutenção preventiva."

COMUNS = {
    "booking_id": RESERVA,
    "space_code": ESPACO,
    "requester_id": SOLICITANTE,
    "occurred_at": AGORA,
}

SOLICITADA = BookingRequested(**COMUNS)  # type: ignore[arg-type]
APROVADA = BookingApproved(**COMUNS, decided_by=GESTOR)  # type: ignore[arg-type]
REJEITADA = BookingRejected(**COMUNS, decided_by=GESTOR, reason=MOTIVO)  # type: ignore[arg-type]
CANCELADA = BookingCancelled(**COMUNS, decided_by=GESTOR)  # type: ignore[arg-type]

TODOS = [SOLICITADA, APROVADA, REJEITADA, CANCELADA]
IDS = [type(e).__name__ for e in TODOS]


# --- os metadados ------------------------------------------------------------------------------


@pytest.mark.parametrize("evento", TODOS, ids=IDS)
def test_a_notificacao_carrega_os_dados_do_evento(evento: BookingEvent) -> None:
    """Tudo que um canal precisa para montar a mensagem, sem consultar o banco (ADR-0006)."""
    notificacao = notification_from(evento)
    assert (
        notificacao.booking_id,
        notificacao.space_code,
        notificacao.requester_id,
        notificacao.occurred_at,
    ) == (RESERVA, ESPACO, SOLICITANTE, AGORA)


@pytest.mark.parametrize("evento", TODOS, ids=IDS)
def test_a_notificacao_e_imutavel(evento: BookingEvent) -> None:
    """Um evento descreve o passado, e a notificação dele também."""
    notificacao = notification_from(evento)
    with pytest.raises(AttributeError):
        notificacao.message = "outra coisa"  # type: ignore[misc]


# --- a mensagem --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("evento", "verbo"),
    [
        (SOLICITADA, "solicitada"),
        (APROVADA, "aprovada"),
        (REJEITADA, "rejeitada"),
        (CANCELADA, "cancelada"),
    ],
    ids=IDS,
)
def test_cada_evento_tem_o_seu_verbo(evento: BookingEvent, verbo: str) -> None:
    """No particípio, como os próprios eventos: descrevem algo que já aconteceu."""
    assert verbo in notification_from(evento).message


@pytest.mark.parametrize("evento", TODOS, ids=IDS)
def test_a_mensagem_nomeia_o_espaco(evento: BookingEvent) -> None:
    """É a informação que identifica a notificação numa lista — e numa captura de tela."""
    assert ESPACO in notification_from(evento).message


@pytest.mark.parametrize("evento", [APROVADA, REJEITADA, CANCELADA], ids=IDS[1:])
def test_a_mensagem_de_decisao_nomeia_quem_decidiu(evento: BookingEvent) -> None:
    assert GESTOR in notification_from(evento).message


def test_a_solicitacao_nao_menciona_decisor() -> None:
    """Ninguém decidiu nada ainda: `BookingRequested` não tem `decided_by`."""
    assert GESTOR not in notification_from(SOLICITADA).message


def test_a_rejeicao_carrega_o_motivo() -> None:
    """RN-14 — é o que o solicitante precisa saber, e o que justifica o motivo ser obrigatório."""
    assert MOTIVO in notification_from(REJEITADA).message


@pytest.mark.parametrize("evento", [SOLICITADA, APROVADA, CANCELADA], ids=[IDS[0], IDS[1], IDS[3]])
def test_so_a_rejeicao_carrega_motivo(evento: BookingEvent) -> None:
    assert MOTIVO not in notification_from(evento).message


@pytest.mark.parametrize("evento", TODOS, ids=IDS)
def test_a_mensagem_nao_fica_vazia_nem_com_sobras_de_formatacao(evento: BookingEvent) -> None:
    mensagem = notification_from(evento).message
    assert mensagem.strip() == mensagem
    assert mensagem.endswith(".")


def test_um_evento_desconhecido_nao_derruba_a_traducao() -> None:
    """Um evento novo no domínio não pode quebrar a caixa antes de alguém lembrar de traduzi-lo.

    A notificação sai genérica, e é o pior caso aceitável: perder a frase é irritante, perder a
    operação por causa dela seria inaceitável (ADR-0006).
    """

    class BookingArquivado(BookingEvent):
        pass

    notificacao = notification_from(BookingArquivado(**COMUNS))  # type: ignore[arg-type]
    assert isinstance(notificacao, Notification)
    assert ESPACO in notificacao.message
