"""Os critérios de aceite da task 11, como verificação executável.

Não é a bateria ponta a ponta — essa é da task 12, e cobrirá os fluxos completos. O que está aqui é
o que **esta** camada prometeu e ninguém mais pode provar: que cada erro de domínio vira o status da
§7.2, que a RN-11 barra um solicitante na porta, que uma falha no meio da requisição não deixa nada
gravado pela metade, e que a identidade entra por cabeçalho.

Cada teste sobe a aplicação inteira sobre um banco temporário: rotas, tratadores, repositórios reais
e observadores inscritos.
"""

from __future__ import annotations

from http import HTTPStatus
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from agendalab.application.dto import RegisterSpaceCommand
from agendalab.application.use_cases.register_space import RegisterSpace
from agendalab.domain.entities.space import SpaceKind
from agendalab.infrastructure.persistence.sqlalchemy_repositories import (
    SqlAlchemySpaceRepository,
)
from agendalab.presentation.dependencies import SessionDep
from agendalab.presentation.main import create_app
from tests.e2e.conftest import GESTOR, OUTRO_SOLICITANTE, SOLICITANTE, cabecalhos

FUTURO = "2026-12-10T14:00:00"
FUTURO_FIM = "2026-12-10T16:00:00"


def cadastrar_laboratorio(gestor: TestClient, code: str = "LAB-01", capacity: int = 30) -> None:
    resposta = gestor.post(
        "/spaces",
        json={"code": code, "name": "Laboratório de Redes", "kind": "LAB", "capacity": capacity},
    )
    assert resposta.status_code == HTTPStatus.CREATED


def solicitar(cliente: TestClient, **alteracoes: object) -> dict:
    corpo = {
        "space_code": "LAB-01",
        "start_at": FUTURO,
        "end_at": FUTURO_FIM,
        "purpose": "Aula prática de Redes de Computadores",
        "attendees": 25,
    }
    return cliente.post("/bookings", json=corpo | alteracoes).json()


# --- a tradução de erros da §7.2 ---------------------------------------------------------------


def test_espaco_inexistente_devolve_404(client: TestClient) -> None:
    resposta = client.get("/spaces/NAO-EXISTE", headers=cabecalhos(SOLICITANTE, "REQUESTER"))
    assert resposta.status_code == HTTPStatus.NOT_FOUND
    assert resposta.json()["error"] == "SpaceNotFound"


def test_reserva_inexistente_devolve_404(client: TestClient) -> None:
    resposta = client.get(f"/bookings/{uuid4()}", headers=cabecalhos(SOLICITANTE, "REQUESTER"))
    assert resposta.json()["error"] == "BookingNotFound"
    assert resposta.status_code == HTTPStatus.NOT_FOUND


def test_codigo_de_espaco_repetido_devolve_409(gestor: TestClient) -> None:
    cadastrar_laboratorio(gestor)
    resposta = gestor.post(
        "/spaces",
        json={"code": "LAB-01", "name": "Outro", "kind": "CLASSROOM", "capacity": 40},
    )
    assert resposta.status_code == HTTPStatus.CONFLICT
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("DuplicateSpaceCode", "RN-16")


def test_conflito_de_horario_devolve_409(gestor: TestClient, solicitante: TestClient) -> None:
    cadastrar_laboratorio(gestor)
    solicitar(solicitante)

    resposta = solicitante.post(
        "/bookings",
        json={
            "space_code": "LAB-01",
            "start_at": FUTURO,
            "end_at": FUTURO_FIM,
            "purpose": "Outra aula",
            "attendees": 10,
        },
    )
    assert resposta.status_code == HTTPStatus.CONFLICT
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("ScheduleConflict", "RN-01")


def test_transicao_invalida_devolve_409(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-13 — aprovar duas vezes. A segunda cai na tabela da §5.5."""
    cadastrar_laboratorio(gestor)
    criada = solicitar(solicitante)
    gestor.post(f"/bookings/{criada['id']}/approval")

    resposta = gestor.post(f"/bookings/{criada['id']}/approval")
    assert resposta.status_code == HTTPStatus.CONFLICT
    assert (resposta.json()["error"], resposta.json()["rule"]) == (
        "InvalidStateTransition",
        "RN-13",
    )


def test_espaco_inativo_devolve_422(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-05. Não há rota para desativar espaço, então a inativação vai direto ao banco — é
    exatamente o cenário de um espaço que saiu de operação depois de cadastrado."""
    from sqlalchemy import text

    cadastrar_laboratorio(gestor)
    with gestor.app.state.sessions() as sessao:  # type: ignore[attr-defined]
        sessao.execute(text("UPDATE spaces SET active = 0 WHERE code = 'LAB-01'"))
        sessao.commit()

    resposta = solicitante.post(
        "/bookings",
        json={
            "space_code": "LAB-01",
            "start_at": FUTURO,
            "end_at": FUTURO_FIM,
            "purpose": "Aula",
            "attendees": 10,
        },
    )
    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("InactiveSpace", "RN-05")


def test_capacidade_excedida_devolve_422(gestor: TestClient, solicitante: TestClient) -> None:
    cadastrar_laboratorio(gestor, capacity=10)
    resposta = solicitante.post(
        "/bookings",
        json={
            "space_code": "LAB-01",
            "start_at": FUTURO,
            "end_at": FUTURO_FIM,
            "purpose": "Aula",
            "attendees": 50,
        },
    )
    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("CapacityExceeded", "RN-06")


def test_violacao_de_politica_devolve_422(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-10 — auditório exige vinte participantes."""
    gestor.post(
        "/spaces",
        json={
            "code": "AUD-01",
            "name": "Auditório Central",
            "kind": "AUDITORIUM",
            "capacity": 200,
        },
    )
    resposta = solicitante.post(
        "/bookings",
        json={
            "space_code": "AUD-01",
            "start_at": FUTURO,
            "end_at": FUTURO_FIM,
            "purpose": "Reunião pequena",
            "attendees": 5,
        },
    )
    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("PolicyViolation", "RN-10")


def test_reserva_no_passado_devolve_422(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-04 — e o `now` que a compara vem da borda, não do domínio."""
    cadastrar_laboratorio(gestor)
    resposta = solicitante.post(
        "/bookings",
        json={
            "space_code": "LAB-01",
            "start_at": "2020-01-01T14:00:00",
            "end_at": "2020-01-01T16:00:00",
            "purpose": "Aula",
            "attendees": 10,
        },
    )
    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("InvalidTimeSlot", "RN-04")


def test_intervalo_invertido_devolve_422(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-03 — recusada na construção do `TimeSlot`, dentro da própria função de rota."""
    cadastrar_laboratorio(gestor)
    resposta = solicitante.post(
        "/bookings",
        json={
            "space_code": "LAB-01",
            "start_at": FUTURO_FIM,
            "end_at": FUTURO,
            "purpose": "Aula",
            "attendees": 10,
        },
    )
    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("InvalidTimeSlot", "RN-03")


def test_cancelamento_alheio_devolve_403(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-12 — e esta recusa vem do **domínio**, não da borda: depende de saber de quem é a reserva."""
    cadastrar_laboratorio(gestor)
    criada = solicitar(solicitante)

    intruso = TestClient(gestor.app)  # type: ignore[arg-type]
    intruso.headers.update(cabecalhos(OUTRO_SOLICITANTE, "REQUESTER"))
    resposta = intruso.post(f"/bookings/{criada['id']}/cancellation")

    assert resposta.status_code == HTTPStatus.FORBIDDEN
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("PermissionDenied", "RN-12")


def test_os_filtros_da_listagem_chegam_pela_query_string(gestor: TestClient) -> None:
    """A rota traduz `?kind=&active=` no `ListSpacesQuery`. Sem parâmetro, sem filtro."""
    cadastrar_laboratorio(gestor)
    gestor.post(
        "/spaces", json={"code": "S-01", "name": "Sala 101", "kind": "CLASSROOM", "capacity": 40}
    )

    todos = gestor.get("/spaces").json()
    laboratorios = gestor.get("/spaces?kind=LAB").json()
    ativos = gestor.get("/spaces?active=true").json()

    assert sorted(e["code"] for e in todos) == ["LAB-01", "S-01"]
    assert [e["code"] for e in laboratorios] == ["LAB-01"]
    assert len(ativos) == 2  # ambos nascem ativos — UC-01


def test_filtro_de_tipo_invalido_devolve_422(gestor: TestClient) -> None:
    """`GINASIO` não é um `SpaceKind`: recusado no formato, sem chegar ao caso de uso."""
    assert gestor.get("/spaces?kind=GINASIO").status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_espaco_existente_e_devolvido(gestor: TestClient) -> None:
    """O contrapeso do `404`: a mesma rota, com um código que existe."""
    cadastrar_laboratorio(gestor)
    resposta = gestor.get("/spaces/LAB-01")
    assert resposta.status_code == HTTPStatus.OK
    assert resposta.json() == {
        "code": "LAB-01",
        "name": "Laboratório de Redes",
        "kind": "LAB",
        "capacity": 30,
        "active": True,
    }


def test_rejeitar_grava_o_motivo_e_devolve_a_reserva(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """UC-06 pela borda — RN-14 verificada pelo domínio, motivo devolvido na resposta."""
    cadastrar_laboratorio(gestor)
    criada = solicitar(solicitante)

    resposta = gestor.post(
        f"/bookings/{criada['id']}/rejection", json={"reason": "Laboratório em manutenção."}
    )

    assert resposta.status_code == HTTPStatus.OK
    corpo = resposta.json()
    assert (corpo["status"], corpo["rejection_reason"], corpo["decided_by"]) == (
        "REJECTED",
        "Laboratório em manutenção.",
        GESTOR,
    )


def test_o_corpo_de_erro_tem_sempre_os_tres_campos(client: TestClient) -> None:
    """§7.2 — o formato é único, e `rule` liga a resposta de volta à especificação."""
    corpo = client.get(
        "/spaces/NAO-EXISTE", headers=cabecalhos(SOLICITANTE, "REQUESTER")
    ).json()
    assert set(corpo) == {"error", "message", "rule"}
    assert corpo["message"]  # mensagem em português, legível


# --- RN-11: o papel exigido pela rota ------------------------------------------------------------


@pytest.mark.parametrize("transicao", ["approval", "rejection"], ids=["aprovar", "rejeitar"])
def test_solicitante_nao_alcanca_as_rotas_de_decisao(
    gestor: TestClient, solicitante: TestClient, transicao: str
) -> None:
    """RN-11 — a recusa acontece na borda, antes de qualquer caso de uso rodar."""
    cadastrar_laboratorio(gestor)
    criada = solicitar(solicitante)

    resposta = solicitante.post(
        f"/bookings/{criada['id']}/{transicao}", json={"reason": "não pode"}
    )
    assert resposta.status_code == HTTPStatus.FORBIDDEN
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("PermissionDenied", "RN-11")


def test_a_reserva_nao_muda_quando_o_papel_e_recusado(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """A verificação de papel vem antes de tudo: a reserva continua pendente, intacta."""
    cadastrar_laboratorio(gestor)
    criada = solicitar(solicitante)

    solicitante.post(f"/bookings/{criada['id']}/approval")

    assert solicitante.get(f"/bookings/{criada['id']}").json()["status"] == "PENDING"


def test_solicitante_nao_cadastra_espaco(solicitante: TestClient) -> None:
    """§7 — `POST /spaces` exige gestor."""
    resposta = solicitante.post(
        "/spaces", json={"code": "X-01", "name": "Sala", "kind": "CLASSROOM", "capacity": 10}
    )
    assert resposta.status_code == HTTPStatus.FORBIDDEN


def test_gestor_nao_solicita_reserva(gestor: TestClient) -> None:
    """§7 — `POST /bookings` é ação de solicitante, conforme a coluna "papel exigido" da tabela."""
    cadastrar_laboratorio(gestor)
    resposta = gestor.post(
        "/bookings",
        json={
            "space_code": "LAB-01",
            "start_at": FUTURO,
            "end_at": FUTURO_FIM,
            "purpose": "Aula",
            "attendees": 10,
        },
    )
    assert resposta.status_code == HTTPStatus.FORBIDDEN


def test_o_gestor_cancela_reserva_alheia(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-12 pelo outro lado: cancelar não exige papel na borda, e o domínio libera o gestor."""
    cadastrar_laboratorio(gestor)
    criada = solicitar(solicitante)

    resposta = gestor.post(f"/bookings/{criada['id']}/cancellation")

    assert resposta.status_code == HTTPStatus.OK
    assert resposta.json()["status"] == "CANCELLED"
    assert resposta.json()["decided_by"] == GESTOR


# --- a identidade vem do cabeçalho ---------------------------------------------------------------


def test_sem_cabecalho_de_identidade_a_requisicao_e_malformada(client: TestClient) -> None:
    """`422` do Pydantic: falta um cabeçalho obrigatório, e isso é erro de formato."""
    assert client.get("/spaces").status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_papel_desconhecido_e_recusado(client: TestClient) -> None:
    resposta = client.get("/spaces", headers=cabecalhos(SOLICITANTE, "ADMIN"))
    assert resposta.status_code == HTTPStatus.FORBIDDEN
    assert resposta.json()["error"] == "PermissionDenied"


def test_o_solicitante_da_reserva_vem_do_cabecalho_e_nao_do_corpo(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """Aceitar `requester_id` no corpo permitiria reservar em nome de outra pessoa."""
    cadastrar_laboratorio(gestor)
    criada = solicitar(solicitante)
    assert criada["requester_id"] == SOLICITANTE


def test_o_corpo_nao_aceita_campo_desconhecido(gestor: TestClient) -> None:
    """`extra="forbid"` — um `requester_id` enviado no corpo é recusado, não ignorado em silêncio."""
    resposta = gestor.post(
        "/spaces",
        json={
            "code": "X-01",
            "name": "Sala",
            "kind": "CLASSROOM",
            "capacity": 10,
            "active": False,
        },
    )
    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- requisição malformada não chega ao domínio ---------------------------------------------------


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("capacity", 0), ("capacity", -5), ("code", ""), ("kind", "GINASIO")],
    ids=["capacidade zero", "capacidade negativa", "código vazio", "tipo inexistente"],
)
def test_corpo_invalido_devolve_422_do_pydantic(
    gestor: TestClient, campo: str, valor: object
) -> None:
    """Validação de formato acontece antes de qualquer caso de uso — o corpo é o do Pydantic,
    com `detail`, e não o corpo de erro de domínio da §7.2."""
    corpo = {"code": "X-01", "name": "Sala", "kind": "CLASSROOM", "capacity": 10}
    resposta = gestor.post("/spaces", json=corpo | {campo: valor})

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "detail" in resposta.json()


def test_identificador_de_reserva_malformado_devolve_422(solicitante: TestClient) -> None:
    resposta = solicitante.get("/bookings/nao-e-um-uuid")
    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- transação: nada gravado pela metade ----------------------------------------------------------


def test_a_recusa_nao_deixa_a_reserva_gravada(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """A requisição que falha é desfeita inteira. A segunda solicitação conflitante é recusada, e o
    horário continua com uma reserva só."""
    cadastrar_laboratorio(gestor)
    solicitar(solicitante)
    solicitar(solicitante, purpose="Tentativa conflitante")

    agenda = solicitante.get("/spaces/LAB-01/availability?date=2026-12-10").json()
    assert len(agenda) == 1


def test_a_falha_desfaz_o_que_a_requisicao_ja_tinha_gravado(tmp_path: object) -> None:
    """O `rollback` de verdade: uma rota que grava e **depois** falha não pode deixar rastro.

    Nenhuma rota real faz isso — todas validam antes de gravar —, então o cenário precisa ser
    montado. A rota é acrescentada a uma aplicação criada só para este teste, e não ao router do
    sistema: é a dependência de sessão que está sob prova, não a rota.

    Os imports de que a rota depende estão no topo do módulo, e precisam estar: com
    `from __future__ import annotations` as anotações viram strings, e o FastAPI as resolve pelo
    namespace global — um `SessionDep` importado aqui dentro não seria encontrado, e o parâmetro
    viraria uma query obrigatória.
    """
    app = create_app(f"sqlite:///{tmp_path}/rollback.db")

    @app.post("/_falha_apos_gravar", include_in_schema=False)
    def _falha_apos_gravar(session: SessionDep) -> None:
        RegisterSpace(SqlAlchemySpaceRepository(session)).execute(
            RegisterSpaceCommand(
                code="MEIO-GRAVADO", name="Sala", kind=SpaceKind.CLASSROOM, capacity=10
            )
        )
        raise RuntimeError("a requisição falhou depois de gravar")

    cliente = TestClient(app, raise_server_exceptions=False)
    cliente.headers.update(cabecalhos(GESTOR, "MANAGER"))

    assert cliente.post("/_falha_apos_gravar").status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert cliente.get("/spaces/MEIO-GRAVADO").status_code == HTTPStatus.NOT_FOUND


# --- o Observer, visível -------------------------------------------------------------------------


def test_a_caixa_de_notificacoes_mostra_o_que_aconteceu(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """A evidência do Observer que a task 13 vai capturar em tela."""
    cadastrar_laboratorio(gestor)
    criada = solicitar(solicitante)
    gestor.post(f"/bookings/{criada['id']}/approval")

    notificacoes = gestor.get("/notifications").json()
    assert len(notificacoes) == 2
    assert "solicitada" in notificacoes[0]["message"]  # na ordem em que aconteceram
    assert "aprovada" in notificacoes[1]["message"]
    assert all(n["space_code"] == "LAB-01" for n in notificacoes)
    assert all(n["booking_id"] == criada["id"] for n in notificacoes)


def test_a_caixa_comeca_vazia(gestor: TestClient) -> None:
    assert gestor.get("/notifications").json() == []


def test_health_responde_sem_identidade(client: TestClient) -> None:
    resposta = client.get("/health")
    assert (resposta.status_code, resposta.json()) == (HTTPStatus.OK, {"status": "ok"})
