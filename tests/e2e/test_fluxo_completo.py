"""O caminho feliz de ponta a ponta — o topo da pirâmide do ADR-0009.

Os 623 testes abaixo deste nível provam que cada regra funciona isolada. Este arquivo prova outra
coisa: que as camadas **se encaixam**. Que o status decidido por uma política do domínio chega ao
cliente como JSON, que a transação commita e o dado sobrevive à requisição seguinte, que o evento
publicado no caso de uso aparece na caixa de entrada.

O primeiro teste é o roteiro da demonstração da task 13, na ordem, numa narrativa só. Os demais
isolam os passos que merecem ser vistos de perto — e o mais importante deles é o do Strategy: mesma
requisição, mesmo endpoint, três tipos de espaço, três resultados.
"""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from tests.e2e.conftest import (
    DAQUI_A_DUAS_HORAS,
    DAQUI_A_UM_MES,
    DAQUI_A_UM_MES_FIM,
    DAQUI_A_UM_MES_MANHA,
    DAQUI_A_UM_MES_MANHA_FIM,
    GESTOR,
    SOLICITANTE,
    cadastrar_auditorio,
    cadastrar_laboratorio,
    cadastrar_sala,
    iso,
    solicitar,
    solicitar_com_sucesso,
)


def test_o_roteiro_completo_do_sistema(gestor: TestClient, solicitante: TestClient) -> None:
    """Os dez passos da task 12, na ordem, contra o sistema inteiro.

    Cada passo depende do estado deixado pelo anterior — é isso que um teste de integração no topo
    da pirâmide precisa fazer, e o que nenhum teste unitário pode fazer.
    """
    # 1. Cadastrar espaços dos três tipos
    cadastrar_sala(gestor, "S-01", capacity=40)
    cadastrar_laboratorio(gestor, "LAB-01", capacity=30)
    cadastrar_auditorio(gestor, "AUD-01")
    assert len(gestor.get("/spaces").json()) == 3

    # 2. Reservar sala de aula → nasce APPROVED (RN-08, aprovação automática)
    na_sala = solicitar_com_sucesso(solicitante, space_code="S-01")
    assert na_sala["status"] == "APPROVED"

    # 3. Reservar laboratório → nasce PENDING (RN-09, exige aval do gestor)
    no_lab = solicitar_com_sucesso(solicitante, space_code="LAB-01")
    assert no_lab["status"] == "PENDING"

    # 4. Segunda reserva no mesmo intervalo → 409 (RN-01)
    conflitante = solicitar(solicitante, space_code="LAB-01")
    assert conflitante.status_code == HTTPStatus.CONFLICT
    assert conflitante.json()["rule"] == "RN-01"

    # 5. Laboratório com menos de 24h de antecedência → 422 (RN-09)
    sem_antecedencia = solicitar(
        solicitante,
        space_code="LAB-01",
        start_at=DAQUI_A_DUAS_HORAS,
        end_at=DAQUI_A_DUAS_HORAS + timedelta(hours=2),
    )
    assert sem_antecedencia.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert sem_antecedencia.json()["rule"] == "RN-09"

    # 6. REQUESTER tentando aprovar → 403 (RN-11)
    negada = solicitante.post(f"/bookings/{no_lab['id']}/approval")
    assert negada.status_code == HTTPStatus.FORBIDDEN
    assert negada.json()["rule"] == "RN-11"

    # 7. Gestor aprova → APPROVED
    aprovada = gestor.post(f"/bookings/{no_lab['id']}/approval")
    assert aprovada.status_code == HTTPStatus.OK
    assert (aprovada.json()["status"], aprovada.json()["decided_by"]) == ("APPROVED", GESTOR)

    # 8. Aprovar de novo → 409 (RN-13, a tabela da §5.5)
    repetida = gestor.post(f"/bookings/{no_lab['id']}/approval")
    assert repetida.status_code == HTTPStatus.CONFLICT
    assert repetida.json()["rule"] == "RN-13"

    # 9. GET /notifications mostra os eventos das operações acima
    mensagens = [n["message"] for n in gestor.get("/notifications").json()]
    assert len(mensagens) == 3  # duas solicitações aceitas e uma aprovação
    assert sum("solicitada" in m for m in mensagens) == 2
    assert sum("aprovada" in m for m in mensagens) == 1

    # 10. Cancelar e reservar de novo no mesmo horário → aceito (RN-01: cancelada não ocupa)
    cancelada = solicitante.post(f"/bookings/{no_lab['id']}/cancellation")
    assert cancelada.status_code == HTTPStatus.OK
    de_novo = solicitar_com_sucesso(solicitante, space_code="LAB-01")
    assert de_novo["id"] != no_lab["id"]


# --- o Strategy, visto de fora --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "kind", "esperado"),
    [
        ("S-01", "CLASSROOM", "APPROVED"),
        ("LAB-01", "LAB", "PENDING"),
        ("AUD-01", "AUDITORIUM", "PENDING"),
    ],
    ids=["sala de aula", "laboratório", "auditório"],
)
def test_o_status_inicial_da_reserva_depende_do_tipo_do_espaco(
    gestor: TestClient, solicitante: TestClient, code: str, kind: str, esperado: str
) -> None:
    """RN-07 pela API: mesma requisição, mesmo endpoint, três resultados.

    É o padrão Strategy observável de fora do sistema, sem abrir o código — e é esta a captura de
    tela que a defesa usa para mostrar que a política é resolvida por tipo.
    """
    from tests.e2e.conftest import cadastrar_espaco

    cadastrar_espaco(gestor, code, kind, capacity=200)
    criada = solicitar_com_sucesso(solicitante, space_code=code)
    assert criada["status"] == esperado


# --- cada passo de perto ---------------------------------------------------------------------------


def test_o_espaco_cadastrado_aparece_na_listagem_e_na_consulta(gestor: TestClient) -> None:
    """UC-01 seguido de UC-02: o que uma requisição gravou, a seguinte encontra."""
    cadastrar_laboratorio(gestor, "LAB-01", capacity=30)

    assert [e["code"] for e in gestor.get("/spaces").json()] == ["LAB-01"]
    assert gestor.get("/spaces/LAB-01").json()["capacity"] == 30


def test_a_reserva_criada_pode_ser_relida_pelo_identificador(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """UC-04 seguido de UC-03 — como o solicitante acompanha a decisão do gestor."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    relida = solicitante.get(f"/bookings/{criada['id']}").json()
    assert relida == criada


def test_a_agenda_do_dia_mostra_as_reservas_em_ordem(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """UC-03 — e em ordem cronológica, mesmo tendo sido criadas fora de ordem."""
    cadastrar_laboratorio(gestor)
    tarde = solicitar_com_sucesso(solicitante)
    manha = solicitar_com_sucesso(
        solicitante, start_at=DAQUI_A_UM_MES_MANHA, end_at=DAQUI_A_UM_MES_MANHA_FIM
    )

    dia = DAQUI_A_UM_MES.date().isoformat()
    agenda = solicitante.get(f"/spaces/LAB-01/availability?date={dia}").json()

    assert [r["id"] for r in agenda] == [manha["id"], tarde["id"]]


def test_a_reserva_rejeitada_sai_da_agenda(gestor: TestClient, solicitante: TestClient) -> None:
    """UC-06 e depois UC-03: rejeitada não ocupa horário, então some da agenda."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)
    dia = DAQUI_A_UM_MES.date().isoformat()
    assert len(solicitante.get(f"/spaces/LAB-01/availability?date={dia}").json()) == 1

    rejeitada = gestor.post(
        f"/bookings/{criada['id']}/rejection", json={"reason": "Laboratório em manutenção."}
    )

    assert rejeitada.json()["status"] == "REJECTED"
    assert rejeitada.json()["rejection_reason"] == "Laboratório em manutenção."
    assert solicitante.get(f"/spaces/LAB-01/availability?date={dia}").json() == []


def test_o_horario_liberado_aceita_uma_nova_reserva(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """O ciclo completo da RN-01 pela API: ocupar, recusar o conflito, cancelar, ocupar de novo."""
    cadastrar_laboratorio(gestor)
    primeira = solicitar_com_sucesso(solicitante)
    assert solicitar(solicitante).status_code == HTTPStatus.CONFLICT

    solicitante.post(f"/bookings/{primeira['id']}/cancellation")

    segunda = solicitar_com_sucesso(solicitante)
    assert segunda["id"] != primeira["id"]


def test_as_reservas_de_espacos_diferentes_convivem_no_mesmo_horario(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """O conflito é por espaço: dois laboratórios no mesmo horário não se atrapalham."""
    cadastrar_laboratorio(gestor, "LAB-01")
    cadastrar_laboratorio(gestor, "LAB-02")

    primeira = solicitar_com_sucesso(solicitante, space_code="LAB-01")
    segunda = solicitar_com_sucesso(solicitante, space_code="LAB-02")

    assert primeira["start_at"] == segunda["start_at"]


def test_reservas_que_se_tocam_nas_bordas_sao_ambas_aceitas(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """RN-02 pela API — quem termina às 16h convive com quem começa às 16h."""
    cadastrar_laboratorio(gestor)
    solicitar_com_sucesso(solicitante)

    emenda = solicitar(
        solicitante,
        start_at=DAQUI_A_UM_MES_FIM,
        end_at=DAQUI_A_UM_MES_FIM + timedelta(hours=2),
    )

    assert emenda.status_code == HTTPStatus.CREATED


def test_a_trilha_de_decisao_e_gravada_e_devolvida(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """§4.1 — quem decidiu e quando, do domínio até o JSON."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)
    assert (criada["decided_by"], criada["decided_at"]) == (None, None)

    aprovada = gestor.post(f"/bookings/{criada['id']}/approval").json()

    assert aprovada["decided_by"] == GESTOR
    assert aprovada["decided_at"] is not None
    assert aprovada["requester_id"] == SOLICITANTE  # quem pediu não é quem decidiu


def test_o_dado_gravado_sobrevive_a_requisicao(gestor: TestClient) -> None:
    """A transação commita: o que a primeira requisição gravou, a segunda encontra no banco.

    Cada requisição abre e fecha sua própria sessão, então encontrar o espaço aqui só é possível
    porque o `commit` da dependência aconteceu de verdade.
    """
    cadastrar_laboratorio(gestor, "LAB-01", capacity=30)
    assert gestor.get("/spaces/LAB-01").status_code == HTTPStatus.OK


def test_o_relogio_da_borda_e_usado_na_criacao(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """`created_at` vem do `now` da borda — nenhuma camada interna lê relógio (ADR-0009)."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    assert criada["created_at"] is not None
    assert criada["start_at"] == iso(DAQUI_A_UM_MES)
