"""O que a camada de apresentação faz e nenhuma outra pode fazer.

As regras de negócio estão em `test_regras_de_negocio.py` e a autorização em `test_autorizacao.py`.
Aqui fica o resto do trabalho da borda: fechar a transação, validar o formato antes de o domínio ver
qualquer coisa, e servir as duas rotas que não passam por caso de uso algum.

São propriedades que não aparecem em nenhum outro nível da pirâmide. Um teste unitário não tem
transação para desfazer, e um teste de integração não tem Pydantic no caminho.
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any

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
from tests.e2e.conftest import (
    DAQUI_A_UM_MES,
    GESTOR,
    cabecalhos,
    cadastrar_laboratorio,
    solicitar,
    solicitar_com_sucesso,
)

# --- a transação ----------------------------------------------------------------------------------


def test_a_recusa_nao_deixa_a_reserva_gravada(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """A requisição que falha é desfeita inteira: o horário continua com uma reserva só."""
    cadastrar_laboratorio(gestor)
    solicitar_com_sucesso(solicitante)
    solicitar(solicitante, purpose="Tentativa conflitante")

    dia = DAQUI_A_UM_MES.date().isoformat()
    agenda = solicitante.get(f"/spaces/LAB-01/availability?date={dia}").json()
    assert len(agenda) == 1


def test_a_falha_desfaz_o_que_a_requisicao_ja_tinha_gravado(tmp_path: Path) -> None:
    """O `rollback` de verdade: uma rota que grava e **depois** falha não pode deixar rastro.

    Nenhuma rota real faz isso — todas validam antes de gravar —, então o cenário precisa ser
    montado. A rota é acrescentada a uma aplicação criada só para este teste, e não ao router do
    sistema: é a dependência de sessão que está sob prova.

    Este teste pagou por si: foi ele que revelou que o driver `pysqlite` não abria transação de
    verdade, e que um `SAVEPOINT` dentro dela rodava em autocommit — com o efeito de que um
    `rollback` posterior não tinha o que desfazer.

    Os imports de que a rota depende estão no topo do módulo, e precisam estar: com
    `from __future__ import annotations` as anotações viram strings, e o FastAPI as resolve pelo
    namespace global — um `SessionDep` importado aqui dentro viraria uma query obrigatória.
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

    with TestClient(app, raise_server_exceptions=False) as cliente:
        cliente.headers.update(cabecalhos(GESTOR, "MANAGER"))

        assert cliente.post("/_falha_apos_gravar").status_code == (
            HTTPStatus.INTERNAL_SERVER_ERROR
        )
        assert cliente.get("/spaces/MEIO-GRAVADO").status_code == HTTPStatus.NOT_FOUND


# --- o formato, antes do domínio ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("capacity", 0), ("capacity", -5), ("code", ""), ("kind", "GINASIO"), ("name", "")],
    ids=["capacidade zero", "capacidade negativa", "código vazio", "tipo inexistente", "nome vazio"],
)
def test_corpo_de_espaco_invalido_e_recusado_pelo_pydantic(
    gestor: TestClient, campo: str, valor: Any
) -> None:
    """Validação de formato acontece antes de qualquer caso de uso. O corpo devolvido é o do
    Pydantic, com `detail` — e não o formato de erro de domínio da §7.2, que tem `error` e `rule`."""
    corpo = {"code": "X-01", "name": "Sala", "kind": "CLASSROOM", "capacity": 10}
    resposta = gestor.post("/spaces", json=corpo | {campo: valor})

    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "detail" in resposta.json()
    assert "error" not in resposta.json()


def test_campo_desconhecido_no_corpo_e_recusado(gestor: TestClient) -> None:
    """`extra="forbid"` — um `active` enviado no cadastro é recusado, não ignorado em silêncio.

    Ignorar seria pior: quem enviou acharia que desativou o espaço.
    """
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


def test_identificador_de_reserva_malformado_e_recusado(solicitante: TestClient) -> None:
    assert solicitante.get("/bookings/nao-e-um-uuid").status_code == (
        HTTPStatus.UNPROCESSABLE_ENTITY
    )


def test_data_de_agenda_malformada_e_recusada(gestor: TestClient) -> None:
    cadastrar_laboratorio(gestor)
    resposta = gestor.get("/spaces/LAB-01/availability?date=10-12-2026")
    assert resposta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_rejeitar_sem_corpo_e_recusado(gestor: TestClient, solicitante: TestClient) -> None:
    """O motivo é obrigatório já no formato — RN-14 verificada depois, pelo domínio."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    assert gestor.post(f"/bookings/{criada['id']}/rejection").status_code == (
        HTTPStatus.UNPROCESSABLE_ENTITY
    )


def test_filtro_de_tipo_invalido_e_recusado(gestor: TestClient) -> None:
    """`GINASIO` não é um `SpaceKind`: recusado na query string, sem chegar ao caso de uso."""
    assert gestor.get("/spaces?kind=GINASIO").status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_os_filtros_da_listagem_chegam_pela_query_string(gestor: TestClient) -> None:
    """A rota traduz `?kind=&active=` no `ListSpacesQuery`. Sem parâmetro, sem filtro."""
    cadastrar_laboratorio(gestor, "LAB-01")
    gestor.post(
        "/spaces", json={"code": "S-01", "name": "Sala 101", "kind": "CLASSROOM", "capacity": 40}
    )

    assert sorted(e["code"] for e in gestor.get("/spaces").json()) == ["LAB-01", "S-01"]
    assert [e["code"] for e in gestor.get("/spaces?kind=LAB").json()] == ["LAB-01"]
    assert len(gestor.get("/spaces?active=true").json()) == 2


# --- as rotas sem caso de uso -----------------------------------------------------------------------


def test_health_responde_sem_identidade(client: TestClient) -> None:
    """A única rota que não exige cabeçalho: quem chama uma verificação de saúde é um orquestrador,
    que não tem identidade a declarar."""
    resposta = client.get("/health")
    assert (resposta.status_code, resposta.json()) == (HTTPStatus.OK, {"status": "ok"})


def test_a_caixa_de_notificacoes_comeca_vazia(gestor: TestClient) -> None:
    assert gestor.get("/notifications").json() == []


def test_a_caixa_de_notificacoes_mostra_o_que_aconteceu(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """A evidência visível do Observer — a captura de tela que a task 13 vai usar."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)
    gestor.post(f"/bookings/{criada['id']}/approval")

    notificacoes = gestor.get("/notifications").json()

    assert len(notificacoes) == 2
    assert "solicitada" in notificacoes[0]["message"]  # na ordem em que aconteceram
    assert "aprovada" in notificacoes[1]["message"]
    assert all(n["booking_id"] == criada["id"] for n in notificacoes)


def test_a_operacao_recusada_nao_gera_notificacao(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """RN-15 — o evento registra um fato consumado, e uma recusa não é fato nenhum."""
    cadastrar_laboratorio(gestor)
    solicitar_com_sucesso(solicitante)
    solicitar(solicitante)  # conflito

    assert len(gestor.get("/notifications").json()) == 1


def test_a_caixa_e_da_aplicacao_e_nao_da_requisicao(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """Ela acumula entre requisições — recriá-la a cada uma esvaziaria a demonstração."""
    cadastrar_laboratorio(gestor, "LAB-01")
    cadastrar_laboratorio(gestor, "LAB-02")
    solicitar_com_sucesso(solicitante, space_code="LAB-01")
    solicitar_com_sucesso(solicitante, space_code="LAB-02")

    assert len(gestor.get("/notifications").json()) == 2


# --- a documentação interativa ------------------------------------------------------------------------


def test_o_swagger_esta_no_ar(client: TestClient) -> None:
    """`/docs` é como a demonstração da task 13 exercita o sistema."""
    assert client.get("/docs").status_code == HTTPStatus.OK


def test_o_esquema_openapi_descreve_os_onze_endpoints(client: TestClient) -> None:
    """A §7 promete onze rotas; o contrato publicado precisa ter as onze."""
    caminhos = client.get("/openapi.json").json()["paths"]
    operacoes = {(m.upper(), p) for p, ops in caminhos.items() for m in ops}

    assert operacoes == {
        ("POST", "/spaces"),
        ("GET", "/spaces"),
        ("GET", "/spaces/{code}"),
        ("GET", "/spaces/{code}/availability"),
        ("POST", "/bookings"),
        ("GET", "/bookings/{booking_id}"),
        ("POST", "/bookings/{booking_id}/approval"),
        ("POST", "/bookings/{booking_id}/rejection"),
        ("POST", "/bookings/{booking_id}/cancellation"),
        ("GET", "/notifications"),
        ("GET", "/health"),
    }
