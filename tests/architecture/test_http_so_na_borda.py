"""Só a apresentação conhece HTTP — ADR-0001 e §7.2 da especificação.

O domínio levanta `ScheduleConflict`; que isso seja um `409` é conhecimento de protocolo, e mora num
lugar só: `presentation/error_handlers.py`. Um `raise HTTPException` dentro de um caso de uso
funcionaria perfeitamente e destruiria a propriedade que o resto do projeto passou dez tasks
construindo — aquele caso de uso deixaria de servir a uma CLI, a um worker ou a um teste sem HTTP.

O teste de dependência vizinho já proíbe **importar** `fastapi` nas camadas internas. Este cobre o
que sobra: usar o vocabulário do protocolo sem importar nada — um `403` escrito à mão, um
`status_code` numa constante. A verificação é sintática, então a menção em comentário ou docstring
não conta: explicar a tradução é legítimo, executá-la é que não.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "src" / "agendalab"

CAMADAS_INTERNAS = ("domain", "application", "infrastructure")

# Nomes que só fazem sentido para quem fala HTTP.
NOMES_DE_PROTOCOLO = frozenset(
    {"HTTPStatus", "HTTPException", "status_code", "JSONResponse", "Response"}
)

# A faixa de códigos de status. Um literal nesta faixa numa camada interna é suspeito o bastante
# para pedir revisão — e, se for coincidência legítima, o número não deveria estar solto no código.
FAIXA_DE_STATUS = range(400, 600)


def _e_nome_de_protocolo(node: ast.AST) -> bool:
    """Um identificador do vocabulário HTTP, usado ou acessado como atributo."""
    if isinstance(node, ast.Name):
        return node.id in NOMES_DE_PROTOCOLO
    return isinstance(node, ast.Attribute) and node.attr in NOMES_DE_PROTOCOLO


def _e_codigo_de_status(node: ast.AST) -> bool:
    """Um inteiro na faixa dos status. `bool` é subclasse de `int` e precisa ficar de fora."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
        and node.value in FAIXA_DE_STATUS
    )


def mencoes_a_http(source: str) -> list[int]:
    """As linhas em que o código — não o comentário — fala HTTP."""
    return sorted(
        node.lineno
        for node in ast.walk(ast.parse(source))
        if _e_nome_de_protocolo(node) or _e_codigo_de_status(node)
    )


def violations(layer: str) -> list[str]:
    problemas: list[str] = []
    for path in sorted((PACKAGE_ROOT / layer).rglob("*.py")):
        problemas.extend(
            f"{path.relative_to(REPO_ROOT)}:{linha}: fala HTTP — traduzir erro em status é da "
            f"camada de apresentação"
            for linha in mencoes_a_http(path.read_text(encoding="utf-8"))
        )
    return problemas


@pytest.mark.parametrize("layer", CAMADAS_INTERNAS)
def test_a_camada_interna_nao_fala_http(layer: str) -> None:
    problemas = violations(layer)
    assert not problemas, "HTTP fora da borda (ADR-0001):\n  " + "\n  ".join(problemas)


def test_a_apresentacao_fala_http(layer: str = "presentation") -> None:
    """O contrapeso: se a borda **não** falasse HTTP, a tradução da §7.2 teria sumido de algum
    lugar — e este teste passaria por vacuidade, sem que nada garantisse a regra."""
    assert violations(layer), "a camada de apresentação deveria conter a tradução para HTTP"


# --- o verificador propriamente dito -----------------------------------------------------------


def test_o_verificador_encontra_o_status_escrito_a_mao() -> None:
    """O número solto é o que ele pega — a chave de dicionário é string, e strings não contam."""
    fonte = "def falhar():\n    status_code = 409\n    return status_code\n"
    assert mencoes_a_http(fonte) == [2, 2, 3]  # o nome, o número, e o nome de novo no `return`


def test_o_verificador_encontra_a_excecao_do_framework() -> None:
    fonte = "raise HTTPException(404)\n"
    assert mencoes_a_http(fonte) == [1, 1]


def test_status_em_comentario_ou_docstring_nao_conta() -> None:
    """Explicar que `ScheduleConflict` vira 409 é documentação legítima em qualquer camada."""
    fonte = '# vira 409 na borda\ndef f():\n    """Traduzido em 422 pela §7.2."""\n'
    assert mencoes_a_http(fonte) == []


def test_numero_fora_da_faixa_de_status_nao_conta() -> None:
    """A capacidade de um auditório é 200 e o teto semanal é 8 — números de negócio são livres."""
    fonte = "CAPACIDADE = 200\nTETO = 8\nANO = 2026\n"
    assert mencoes_a_http(fonte) == []
