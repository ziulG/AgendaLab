"""Cada recusa do domínio chegando ao cliente com o status da §7.2.

Os testes unitários já provaram que cada regra recusa o que deve recusar. O que se verifica aqui é o
trajeto: que o `DomainError` levantado lá dentro atravessa a aplicação, encontra o tratador da borda
e volta como o código HTTP certo, com a regra numerada no corpo.

É o `rule` da resposta que faz este arquivo valer a pena. Ele liga cada `422` a uma linha da
especificação — rastreabilidade que funciona em tempo de execução, e que a defesa cita.

A distinção entre `409` e `422` é o que mais se exercita aqui, e ela é semântica: **409** é conflito
com o estado atual, e repetir depois pode funcionar; **422** é requisição bem formada e
inadmissível, e repetir sem mudar os dados nunca vai funcionar.
"""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.value_objects.time_slot import TimeSlot
from agendalab.infrastructure.persistence.sqlalchemy_repositories import (
    SqlAlchemyBookingRepository,
)
from tests.e2e.conftest import (
    DAQUI_A_DUAS_HORAS,
    DAQUI_A_UM_MES,
    DAQUI_A_UM_MES_FIM,
    PASSADO,
    cadastrar_auditorio,
    cadastrar_laboratorio,
    cadastrar_sala,
    solicitar,
    solicitar_com_sucesso,
)

# --- 404: identificador inexistente ---------------------------------------------------------------


def test_consultar_espaco_inexistente(solicitante: TestClient) -> None:
    resposta = solicitante.get("/spaces/NAO-EXISTE")
    assert resposta.status_code == HTTPStatus.NOT_FOUND
    assert resposta.json()["error"] == "SpaceNotFound"


def test_consultar_reserva_inexistente(solicitante: TestClient) -> None:
    resposta = solicitante.get(f"/bookings/{uuid4()}")
    assert resposta.status_code == HTTPStatus.NOT_FOUND
    assert resposta.json()["error"] == "BookingNotFound"


def test_reservar_espaco_inexistente(solicitante: TestClient) -> None:
    assert solicitar(solicitante).status_code == HTTPStatus.NOT_FOUND


def test_consultar_a_agenda_de_espaco_inexistente(solicitante: TestClient) -> None:
    dia = DAQUI_A_UM_MES.date().isoformat()
    resposta = solicitante.get(f"/spaces/NAO-EXISTE/availability?date={dia}")
    assert resposta.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("transicao", ["approval", "rejection", "cancellation"])
def test_decidir_sobre_reserva_inexistente(gestor: TestClient, transicao: str) -> None:
    resposta = gestor.post(f"/bookings/{uuid4()}/{transicao}", json={"reason": "qualquer"})
    assert resposta.status_code == HTTPStatus.NOT_FOUND
    assert resposta.json()["error"] == "BookingNotFound"


# --- 409: conflito com o estado atual do recurso ---------------------------------------------------


def test_codigo_de_espaco_repetido(gestor: TestClient) -> None:
    """RN-16 — e a recusa vem da chave primária do banco, não de uma consulta prévia."""
    cadastrar_laboratorio(gestor, "LAB-01")
    resposta = gestor.post(
        "/spaces", json={"code": "LAB-01", "name": "Outro", "kind": "CLASSROOM", "capacity": 40}
    )
    assert resposta.status_code == HTTPStatus.CONFLICT
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("DuplicateSpaceCode", "RN-16")


def test_reserva_em_horario_ja_ocupado(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-01."""
    cadastrar_laboratorio(gestor)
    solicitar_com_sucesso(solicitante)

    resposta = solicitar(solicitante)
    assert resposta.status_code == HTTPStatus.CONFLICT
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("ScheduleConflict", "RN-01")


def test_sobreposicao_parcial_tambem_conflita(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """RN-02 — não é preciso coincidir: basta invadir."""
    cadastrar_laboratorio(gestor)
    solicitar_com_sucesso(solicitante)

    resposta = solicitar(
        solicitante,
        start_at=DAQUI_A_UM_MES + timedelta(hours=1),
        end_at=DAQUI_A_UM_MES_FIM + timedelta(hours=1),
    )
    assert resposta.status_code == HTTPStatus.CONFLICT


@pytest.mark.parametrize(
    ("primeira", "segunda"),
    [("approval", "approval"), ("approval", "rejection"), ("rejection", "cancellation")],
    ids=["aprovar duas vezes", "rejeitar a aprovada", "cancelar a rejeitada"],
)
def test_transicao_que_a_tabela_nao_permite(
    gestor: TestClient, solicitante: TestClient, primeira: str, segunda: str
) -> None:
    """RN-13 — as células ❌ da §5.5, agora pela API."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)
    gestor.post(f"/bookings/{criada['id']}/{primeira}", json={"reason": "motivo"})

    resposta = gestor.post(f"/bookings/{criada['id']}/{segunda}", json={"reason": "motivo"})

    assert resposta.status_code == HTTPStatus.CONFLICT
    assert (resposta.json()["error"], resposta.json()["rule"]) == (
        "InvalidStateTransition",
        "RN-13",
    )


def test_aprovar_reserva_cujo_horario_foi_tomado(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """RN-01 revalidada no momento da decisão — o passo a mais do UC-05.

    Duas reservas pendentes no mesmo horário não nasceriam pela API, então a concorrente entra pelo
    repositório — a mesma via que o sistema usa, sem `INSERT` à mão, que dependeria de acertar o
    formato de data que o SQLAlchemy grava.
    """
    cadastrar_laboratorio(gestor)
    pendente = solicitar_com_sucesso(solicitante)

    with gestor.app.state.sessions() as sessao:  # type: ignore[attr-defined]
        SqlAlchemyBookingRepository(sessao).add(
            Booking(
                id=uuid4(),
                space_code="LAB-01",
                requester_id="9999",
                slot=TimeSlot(DAQUI_A_UM_MES, DAQUI_A_UM_MES_FIM),
                purpose="Reserva que surgiu no meio-tempo",
                attendees=10,
                status=BookingStatus.APPROVED,
                created_at=DAQUI_A_UM_MES,
            )
        )
        sessao.commit()

    resposta = gestor.post(f"/bookings/{pendente['id']}/approval")

    assert resposta.status_code == HTTPStatus.CONFLICT
    assert resposta.json()["error"] == "ScheduleConflict"
    assert solicitante.get(f"/bookings/{pendente['id']}").json()["status"] == "PENDING"


# --- 422: requisição bem formada, porém inadmissível ------------------------------------------------


def test_reservar_espaco_inativo(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-05. Não há rota para desativar espaço — o cenário é o de um espaço que saiu de operação
    depois de cadastrado, então a inativação vai direto ao banco."""
    cadastrar_laboratorio(gestor)
    with gestor.app.state.sessions() as sessao:  # type: ignore[attr-defined]
        sessao.execute(text("UPDATE spaces SET active = 0 WHERE code = 'LAB-01'"))
        sessao.commit()

    resposta = solicitar(solicitante)

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("InactiveSpace", "RN-05")


def test_participantes_acima_da_capacidade(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-06."""
    cadastrar_laboratorio(gestor, capacity=10)
    resposta = solicitar(solicitante, attendees=50)

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("CapacityExceeded", "RN-06")


def test_lotar_o_espaco_e_permitido(gestor: TestClient, solicitante: TestClient) -> None:
    """A regra é "não exceder": exatamente a capacidade passa."""
    cadastrar_laboratorio(gestor, capacity=10)
    assert solicitar(solicitante, attendees=10).status_code == HTTPStatus.CREATED


def test_teto_semanal_da_sala_de_aula(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-08 — 8h por solicitante na semana, somando a reserva em análise."""
    cadastrar_sala(gestor, "S-01", capacity=40)
    solicitar_com_sucesso(
        solicitante,
        space_code="S-01",
        start_at=DAQUI_A_UM_MES.replace(hour=6),
        end_at=DAQUI_A_UM_MES.replace(hour=13),  # 7h
    )

    resposta = solicitar(solicitante, space_code="S-01")  # mais 2h — passa de 8h

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("PolicyViolation", "RN-08")


def test_laboratorio_sem_antecedencia_minima(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """RN-09 — 24h de aviso."""
    cadastrar_laboratorio(gestor)
    resposta = solicitar(
        solicitante,
        start_at=DAQUI_A_DUAS_HORAS,
        end_at=DAQUI_A_DUAS_HORAS + timedelta(hours=2),
    )

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("PolicyViolation", "RN-09")


def test_laboratorio_com_duracao_excessiva(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-09 — 4h por sessão."""
    cadastrar_laboratorio(gestor)
    resposta = solicitar(solicitante, end_at=DAQUI_A_UM_MES + timedelta(hours=6))

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resposta.json()["rule"] == "RN-09"


def test_auditorio_com_poucos_participantes(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """RN-10 — o auditório é para eventos de porte."""
    cadastrar_auditorio(gestor)
    resposta = solicitar(solicitante, space_code="AUD-01", attendees=5)

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("PolicyViolation", "RN-10")


def test_auditorio_sem_antecedencia_minima(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """RN-10 — 72h de aviso."""
    cadastrar_auditorio(gestor)
    resposta = solicitar(
        solicitante,
        space_code="AUD-01",
        attendees=50,
        start_at=DAQUI_A_DUAS_HORAS,
        end_at=DAQUI_A_DUAS_HORAS + timedelta(hours=2),
    )

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resposta.json()["rule"] == "RN-10"


def test_reserva_no_passado(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-04 — e o `now` comparado é o da borda."""
    cadastrar_laboratorio(gestor)
    resposta = solicitar(
        solicitante, start_at=PASSADO, end_at=PASSADO + timedelta(hours=2)
    )

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("InvalidTimeSlot", "RN-04")


def test_intervalo_invertido(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-03 — recusado na construção do `TimeSlot`, antes de qualquer caso de uso."""
    cadastrar_laboratorio(gestor)
    resposta = solicitar(
        solicitante, start_at=DAQUI_A_UM_MES_FIM, end_at=DAQUI_A_UM_MES
    )

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("InvalidTimeSlot", "RN-03")


def test_rejeitar_com_motivo_em_branco(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-14 — só espaços passa pelo Pydantic e é recusado pelo domínio, que sabe o que "vazio"
    significa."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    resposta = gestor.post(f"/bookings/{criada['id']}/rejection", json={"reason": "   "})

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == (
        "MissingRejectionReason",
        "RN-14",
    )


def test_a_reserva_continua_pendente_apos_a_rejeicao_sem_motivo(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """A RN-14 é verificada antes de transicionar: não existe rejeitada sem motivo."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    gestor.post(f"/bookings/{criada['id']}/rejection", json={"reason": "   "})

    assert solicitante.get(f"/bookings/{criada['id']}").json()["status"] == "PENDING"


# --- o formato único da resposta de erro ------------------------------------------------------------


def test_toda_resposta_de_erro_tem_os_tres_campos(solicitante: TestClient) -> None:
    """§7.2 — e o `rule` é o que liga a resposta de volta à especificação."""
    corpo = solicitante.get("/spaces/NAO-EXISTE").json()
    assert set(corpo) == {"error", "message", "rule"}


def test_a_mensagem_de_erro_e_legivel_em_portugues(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """Quem recebe o erro precisa entender o que houve sem consultar o código-fonte."""
    cadastrar_laboratorio(gestor)
    solicitar_com_sucesso(solicitante)

    mensagem = solicitar(solicitante).json()["message"]

    assert "LAB-01" in mensagem
    assert "reserva ativa" in mensagem


def test_o_erro_sem_regra_numerada_traz_rule_nulo(solicitante: TestClient) -> None:
    """Não existe RN para "esse código não existe" — o campo é nulo, não inventado."""
    assert solicitante.get("/spaces/NAO-EXISTE").json()["rule"] is None
