"""A aplicação inteira, montada sobre um banco temporário.

`create_app` recebe a URL do banco por parâmetro justamente para isto: cada teste sobe o sistema
completo — rotas, tratadores, repositórios SQLAlchemy, observadores inscritos — contra um arquivo
que some ao final. Nenhuma variável de ambiente, nenhum estado compartilhado entre testes, nenhum
toque no banco de desenvolvimento.

`with TestClient(...)` não é detalhe: é o que dispara o `lifespan` da aplicação, e é lá que o
esquema é criado. Sem o `with`, as tabelas não existiriam.

**As datas são relativas ao instante da execução**, e não fixas. O relógio da borda é o real
(`datetime.now()` na dependência `get_now`), então uma constante como `2026-12-10` funcionaria hoje
e faria a suíte inteira falhar em 2027 — com uma mensagem que não diria por quê.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agendalab.presentation.main import create_app

SOLICITANTE = "2019001234"
OUTRO_SOLICITANTE = "2020005678"
GESTOR = "1998007766"

# --- os instantes usados pelos testes ------------------------------------------------------------
#
# Longe o bastante no futuro para satisfazer as três políticas: sem antecedência mínima na sala de
# aula (RN-08), 24h no laboratório (RN-09) e 72h no auditório (RN-10).

_AGORA = datetime.now()  # noqa: DTZ005 — datas ingênuas, como a §7.1 da especificação


def _futuro(dias: int, hora: int) -> datetime:
    return (_AGORA + timedelta(days=dias)).replace(
        hour=hora, minute=0, second=0, microsecond=0
    )


DAQUI_A_UM_MES = _futuro(30, 14)
DAQUI_A_UM_MES_FIM = _futuro(30, 16)
DAQUI_A_UM_MES_MANHA = _futuro(30, 8)
DAQUI_A_UM_MES_MANHA_FIM = _futuro(30, 10)

# Menos de 24h de antecedência, e ainda assim no futuro: recusado pela RN-09, aceito pela RN-04.
DAQUI_A_DUAS_HORAS = _AGORA + timedelta(hours=2)
PASSADO = _AGORA - timedelta(days=1)


def iso(momento: datetime) -> str:
    return momento.isoformat()


def cabecalhos(user_id: str, role: str) -> dict[str, str]:
    return {"X-User-Id": user_id, "X-User-Role": role}


# --- clientes ------------------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """A aplicação sem identidade — para exercitar cabeçalho ausente ou inválido."""
    with TestClient(create_app(f"sqlite:///{tmp_path}/agendalab.db")) as cliente:
        yield cliente


@pytest.fixture
def gestor(client: TestClient) -> TestClient:
    client.headers.update(cabecalhos(GESTOR, "MANAGER"))
    return client


@pytest.fixture
def solicitante(client: TestClient) -> TestClient:
    """Um segundo cliente sobre **a mesma aplicação** do `gestor`.

    Os testes precisam dos dois papéis agindo sobre os mesmos dados: o solicitante pede, o gestor
    decide. Como a fixture `client` é a mesma instância, o banco é um só.
    """
    return outro_cliente(client, SOLICITANTE, "REQUESTER")


def outro_cliente(base: TestClient, user_id: str, role: str) -> TestClient:
    """Mais uma identidade sobre a aplicação já montada."""
    cliente = TestClient(base.app)  # type: ignore[arg-type]
    cliente.headers.update(cabecalhos(user_id, role))
    return cliente


# --- atalhos de cenário ---------------------------------------------------------------------------
#
# Os quatro arquivos de e2e montam os mesmos cenários. Estas funções existem para que os testes
# falem de regras de negócio em vez de corpos JSON.


def cadastrar_espaco(
    gestor: TestClient,
    code: str,
    kind: str,
    *,
    capacity: int = 30,
    name: str | None = None,
) -> dict[str, Any]:
    resposta = gestor.post(
        "/spaces",
        json={"code": code, "name": name or f"Espaço {code}", "kind": kind, "capacity": capacity},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def cadastrar_sala(gestor: TestClient, code: str = "S-01", **kwargs: Any) -> dict[str, Any]:
    return cadastrar_espaco(gestor, code, "CLASSROOM", **kwargs)


def cadastrar_laboratorio(gestor: TestClient, code: str = "LAB-01", **kwargs: Any) -> dict[str, Any]:
    return cadastrar_espaco(gestor, code, "LAB", **kwargs)


def cadastrar_auditorio(gestor: TestClient, code: str = "AUD-01", **kwargs: Any) -> dict[str, Any]:
    return cadastrar_espaco(gestor, code, "AUDITORIUM", capacity=kwargs.pop("capacity", 200), **kwargs)


def corpo_de_reserva(
    space_code: str = "LAB-01",
    *,
    start_at: datetime = DAQUI_A_UM_MES,
    end_at: datetime = DAQUI_A_UM_MES_FIM,
    purpose: str = "Aula prática de Redes de Computadores",
    attendees: int = 25,
) -> dict[str, Any]:
    return {
        "space_code": space_code,
        "start_at": iso(start_at),
        "end_at": iso(end_at),
        "purpose": purpose,
        "attendees": attendees,
    }


def solicitar(cliente: TestClient, **alteracoes: Any) -> Any:
    """A resposta crua — os testes de recusa precisam do status, os felizes precisam do corpo."""
    return cliente.post("/bookings", json=corpo_de_reserva(**alteracoes))


def solicitar_com_sucesso(cliente: TestClient, **alteracoes: Any) -> dict[str, Any]:
    resposta = solicitar(cliente, **alteracoes)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()
