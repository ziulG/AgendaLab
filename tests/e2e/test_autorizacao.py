"""RN-11 e RN-12 pela API — a *Conformidade* do ADR-0007 aponta para este arquivo.

O sistema **não autentica**: a identidade chega por cabeçalho e é aceita como declarada. A
autorização, essa sim, está implementada por inteiro, e é o que estes testes verificam.

O que vale notar é que ela está partida em dois lugares, e por um motivo:

- **RN-11 — só gestor aprova ou rejeita.** Responder "quem é você?" não depende de dado algum do
  sistema, então a verificação é de borda e vive numa dependência do FastAPI.
- **RN-12 — cancela o dono ou um gestor.** Responder "esta reserva é sua?" exige conhecer a reserva,
  e a borda não a conhece. A verificação vive no **domínio**, dentro do estado.

Os dois casos devolvem `403` e são indistinguíveis para o cliente — o que é o correto: a divisão é
interna, não faz parte do contrato.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from tests.e2e.conftest import (
    GESTOR,
    OUTRO_SOLICITANTE,
    SOLICITANTE,
    cabecalhos,
    cadastrar_laboratorio,
    outro_cliente,
    solicitar,
    solicitar_com_sucesso,
)

TRANSICOES_DE_GESTOR = ["approval", "rejection"]


# --- RN-11: a verificação de borda -----------------------------------------------------------------


@pytest.mark.parametrize("transicao", TRANSICOES_DE_GESTOR, ids=["aprovar", "rejeitar"])
def test_solicitante_nao_decide_sobre_reserva(
    gestor: TestClient, solicitante: TestClient, transicao: str
) -> None:
    """RN-11 — um `REQUESTER` que tente aprovar uma reserva recebe `403`."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    resposta = solicitante.post(
        f"/bookings/{criada['id']}/{transicao}", json={"reason": "não pode"}
    )

    assert resposta.status_code == HTTPStatus.FORBIDDEN
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("PermissionDenied", "RN-11")


@pytest.mark.parametrize("transicao", TRANSICOES_DE_GESTOR, ids=["aprovar", "rejeitar"])
def test_a_reserva_nao_muda_quando_o_papel_e_recusado(
    gestor: TestClient, solicitante: TestClient, transicao: str
) -> None:
    """A verificação vem antes de tudo: nem o caso de uso chega a rodar."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    solicitante.post(f"/bookings/{criada['id']}/{transicao}", json={"reason": "não pode"})

    assert solicitante.get(f"/bookings/{criada['id']}").json()["status"] == "PENDING"


@pytest.mark.parametrize("transicao", TRANSICOES_DE_GESTOR, ids=["aprovar", "rejeitar"])
def test_gestor_decide_sobre_reserva(
    gestor: TestClient, solicitante: TestClient, transicao: str
) -> None:
    """O contrapeso: a mesma requisição, com o papel certo, funciona."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    resposta = gestor.post(
        f"/bookings/{criada['id']}/{transicao}", json={"reason": "Em manutenção."}
    )

    assert resposta.status_code == HTTPStatus.OK
    assert resposta.json()["decided_by"] == GESTOR


def test_solicitante_nao_cadastra_espaco(solicitante: TestClient) -> None:
    """§7 — cadastrar espaço é ação de gestor."""
    resposta = solicitante.post(
        "/spaces", json={"code": "X-01", "name": "Sala", "kind": "CLASSROOM", "capacity": 10}
    )
    assert resposta.status_code == HTTPStatus.FORBIDDEN
    assert resposta.json()["rule"] == "RN-11"


def test_o_espaco_nao_e_criado_quando_o_papel_e_recusado(
    solicitante: TestClient, gestor: TestClient
) -> None:
    solicitante.post(
        "/spaces", json={"code": "X-01", "name": "Sala", "kind": "CLASSROOM", "capacity": 10}
    )
    assert gestor.get("/spaces").json() == []


# --- solicitar não tem papel exigido ----------------------------------------------------------------


def test_o_gestor_tambem_solicita_reserva(gestor: TestClient) -> None:
    """Nenhuma RN restringe quem solicita.

    A RN-11 fala de aprovar e rejeitar; proibir um gestor de reservar um laboratório seria restrição
    inventada. Ele pede como qualquer pessoa — e a reserva fica registrada em nome dele.
    """
    cadastrar_laboratorio(gestor)

    criada = solicitar(gestor)

    assert criada.status_code == HTTPStatus.CREATED
    assert criada.json()["requester_id"] == GESTOR


def test_qualquer_papel_consulta_espacos_e_reservas(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """As rotas de leitura exigem identidade, mas não papel — "qualquer" na tabela §7."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    terceiro = outro_cliente(gestor, OUTRO_SOLICITANTE, "REQUESTER")

    assert terceiro.get("/spaces").status_code == HTTPStatus.OK
    assert terceiro.get(f"/bookings/{criada['id']}").status_code == HTTPStatus.OK


# --- RN-12: a verificação de domínio ----------------------------------------------------------------


def test_solicitante_nao_cancela_reserva_alheia(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """RN-12 — e esta recusa vem do domínio, não da borda: depende de saber de quem é a reserva."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    intruso = outro_cliente(gestor, OUTRO_SOLICITANTE, "REQUESTER")
    resposta = intruso.post(f"/bookings/{criada['id']}/cancellation")

    assert resposta.status_code == HTTPStatus.FORBIDDEN
    assert (resposta.json()["error"], resposta.json()["rule"]) == ("PermissionDenied", "RN-12")


def test_a_reserva_alheia_fica_intacta(gestor: TestClient, solicitante: TestClient) -> None:
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    intruso = outro_cliente(gestor, OUTRO_SOLICITANTE, "REQUESTER")
    intruso.post(f"/bookings/{criada['id']}/cancellation")

    relida = solicitante.get(f"/bookings/{criada['id']}").json()
    assert (relida["status"], relida["decided_by"]) == ("PENDING", None)


def test_o_proprio_solicitante_cancela(gestor: TestClient, solicitante: TestClient) -> None:
    """RN-12, primeiro caso permitido."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    resposta = solicitante.post(f"/bookings/{criada['id']}/cancellation")

    assert resposta.status_code == HTTPStatus.OK
    assert (resposta.json()["status"], resposta.json()["decided_by"]) == (
        "CANCELLED",
        SOLICITANTE,
    )


def test_o_gestor_cancela_reserva_de_qualquer_pessoa(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """RN-12, segundo caso permitido — e a rota de cancelamento não exige papel na borda."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)

    resposta = gestor.post(f"/bookings/{criada['id']}/cancellation")

    assert resposta.status_code == HTTPStatus.OK
    assert (resposta.json()["status"], resposta.json()["decided_by"]) == ("CANCELLED", GESTOR)


def test_a_reserva_aprovada_ainda_pode_ser_cancelada(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """§5.5 — `APPROVED` aceita apenas `cancel`, e o dono continua podendo."""
    cadastrar_laboratorio(gestor)
    criada = solicitar_com_sucesso(solicitante)
    gestor.post(f"/bookings/{criada['id']}/approval")

    resposta = solicitante.post(f"/bookings/{criada['id']}/cancellation")

    assert resposta.json()["status"] == "CANCELLED"


# --- a identidade declarada -------------------------------------------------------------------------


def test_sem_cabecalho_de_identidade_a_requisicao_e_recusada(client: TestClient) -> None:
    """`422` do Pydantic: falta um cabeçalho obrigatório, e isso é erro de formato, não de papel."""
    assert client.get("/spaces").status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize("papel", ["ADMIN", "manager", ""], ids=["inexistente", "minúsculo", "vazio"])
def test_papel_desconhecido_e_recusado(client: TestClient, papel: str) -> None:
    """Só `REQUESTER` e `MANAGER` existem. Um papel inventado não vira acesso."""
    resposta = client.get("/spaces", headers=cabecalhos(SOLICITANTE, papel))
    assert resposta.status_code == HTTPStatus.FORBIDDEN
    assert resposta.json()["error"] == "PermissionDenied"


def test_a_identidade_da_reserva_vem_do_cabecalho(
    gestor: TestClient, solicitante: TestClient
) -> None:
    """Aceitar `requester_id` no corpo permitiria reservar em nome de outra pessoa."""
    cadastrar_laboratorio(gestor)
    assert solicitar_com_sucesso(solicitante)["requester_id"] == SOLICITANTE


def test_o_sistema_confia_no_papel_declarado(gestor: TestClient) -> None:
    """ADR-0007, dito em voz alta: qualquer cliente pode se declarar gestor e será aceito.

    Este teste documenta a limitação **de propósito**. Ele não descreve um defeito a corrigir, e sim
    a fronteira desenhada: não há autenticação, e o README avisa que a aplicação não deve ser
    exposta em rede. Se um dia houver autenticação, é este teste que precisa mudar.
    """
    impostor = outro_cliente(gestor, "qualquer-um", "MANAGER")

    resposta = impostor.post(
        "/spaces", json={"code": "X-01", "name": "Sala", "kind": "CLASSROOM", "capacity": 10}
    )

    assert resposta.status_code == HTTPStatus.CREATED
