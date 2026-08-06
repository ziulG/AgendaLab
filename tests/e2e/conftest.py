"""A aplicação montada sobre um banco temporário.

`create_app` recebe a URL do banco por parâmetro justamente para isto: cada teste sobe a aplicação
inteira — rotas, tratadores, repositórios reais, observadores inscritos — contra um arquivo que some
ao final, sem variável de ambiente e sem tocar o banco de desenvolvimento.

A identidade vai por cabeçalho em toda requisição, como manda o ADR-0007. As duas fixtures de
cliente abaixo existem para que os testes digam "como gestor" e "como solicitante" em vez de repetir
um dicionário de cabeçalhos em cada chamada.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from agendalab.presentation.main import create_app

SOLICITANTE = "2019001234"
OUTRO_SOLICITANTE = "2020005678"
GESTOR = "1998007766"


def cabecalhos(user_id: str, role: str) -> dict[str, str]:
    return {"X-User-Id": user_id, "X-User-Role": role}


@pytest.fixture
def client(tmp_path: object) -> Iterator[TestClient]:
    """A aplicação sem identidade — para exercitar cabeçalho ausente ou inválido."""
    with TestClient(create_app(f"sqlite:///{tmp_path}/agendalab.db")) as cliente:
        yield cliente


@pytest.fixture
def gestor(client: TestClient) -> TestClient:
    client.headers.update(cabecalhos(GESTOR, "MANAGER"))
    return client


@pytest.fixture
def solicitante(client: TestClient) -> TestClient:
    """Um segundo cliente sobre **a mesma aplicação** do `gestor`, para os testes que precisam dos
    dois papéis: como a fixture `client` é a mesma instância, os dados de um enxergam os do outro."""
    outro = TestClient(client.app)  # type: ignore[arg-type]
    outro.headers.update(cabecalhos(SOLICITANTE, "REQUESTER"))
    return outro
