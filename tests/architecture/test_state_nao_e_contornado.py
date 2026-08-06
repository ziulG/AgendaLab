"""O padrão State não é contornado por condicional de status — ADR-0005.

Existe uma forma de fazer a suíte inteira passar e mesmo assim destruir o padrão: escrever
`if booking.status == BookingStatus.PENDING` dentro de um caso de uso. O comportamento observável
seria o mesmo, e nenhum teste de regra de negócio notaria. O que se perderia é o motivo de o State
existir — a tabela da §5.5 num lugar só, em vez de replicada em cada operação que decide algo.

Por isso a restrição é verificada como a regra de dependência: sobre a árvore sintática, e não sobre
o texto do arquivo. `status ==` dentro de comentário ou de string não conta, e um `match` sobre o
status é encontrado mesmo sem nenhum `==` na linha.

A camada verificada é `application/`. O domínio compara status livremente — é lá que a regra mora.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYER_ROOT = REPO_ROOT / "src" / "agendalab" / "application"


def _e_atributo_status(node: ast.expr) -> bool:
    """Se o nó é um acesso a `.status` — `booking.status`, `self._reserva.status`, etc."""
    return isinstance(node, ast.Attribute) and node.attr == "status"


def comparacoes_de_status(source: str) -> list[int]:
    """As linhas em que um `.status` é usado para decidir alguma coisa.

    Cobre as duas formas de escrever a condicional: comparação — `==`, `!=`, `is`, `is not`, `in` —
    e `match`. Uma sequência de comparações encadeadas é um único nó `Compare`, então basta olhar
    todos os operandos dele.
    """
    encontradas: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Compare):
            if any(_e_atributo_status(lado) for lado in (node.left, *node.comparators)):
                encontradas.append(node.lineno)
        elif isinstance(node, ast.Match) and _e_atributo_status(node.subject):
            encontradas.append(node.lineno)
    return sorted(encontradas)


def violations() -> list[str]:
    """Uma mensagem por ocorrência, com arquivo e linha."""
    problemas: list[str] = []
    for path in sorted(LAYER_ROOT.rglob("*.py")):
        problemas.extend(
            f"{path.relative_to(REPO_ROOT)}:{linha}: decide a partir de `.status` — "
            f"quem responde isso é o estado da reserva"
            for linha in comparacoes_de_status(path.read_text(encoding="utf-8"))
        )
    return problemas


def test_a_camada_de_aplicacao_nao_decide_a_partir_do_status() -> None:
    problemas = violations()
    assert not problemas, "Padrão State contornado (ADR-0005):\n  " + "\n  ".join(problemas)


def test_a_camada_analisada_nao_esta_vazia() -> None:
    """Sem esta guarda, um diretório renomeado faria o teste passar analisando zero arquivos."""
    assert list(LAYER_ROOT.rglob("*.py")), "nenhum módulo analisado em `application/`"


# --- o verificador propriamente dito -----------------------------------------------------------
#
# Um verificador que nunca reprova nada não prova nada. Estes exercitam os dois caminhos.


def test_o_verificador_encontra_as_formas_de_comparar_status() -> None:
    fonte = (
        "if booking.status == BookingStatus.PENDING:\n"
        "    pass\n"
        "if booking.status is not BookingStatus.APPROVED:\n"
        "    pass\n"
        "if BookingStatus.CANCELLED == booking.status:\n"
        "    pass\n"
        "if booking.status in ACTIVE_STATUSES:\n"
        "    pass\n"
    )
    assert comparacoes_de_status(fonte) == [1, 3, 5, 7]


def test_o_verificador_encontra_o_match_sobre_o_status() -> None:
    """A condicional disfarçada: sem um único `==` na linha, e é a mesma coisa."""
    fonte = "match booking.status:\n    case BookingStatus.PENDING:\n        pass\n"
    assert comparacoes_de_status(fonte) == [1]


def test_o_verificador_encontra_a_comparacao_dentro_de_funcao() -> None:
    fonte = "def decidir(booking):\n    return booking.status == 'PENDING'\n"
    assert comparacoes_de_status(fonte) == [2]


def test_comparacao_em_comentario_ou_string_nao_conta() -> None:
    fonte = '# if booking.status == PENDING\nEXEMPLO = "booking.status is PENDING"\n'
    assert comparacoes_de_status(fonte) == []


def test_usar_o_status_sem_decidir_nada_e_permitido() -> None:
    """Atribuir o status devolvido pela política não é condicional — é o UC-04 fazendo seu trabalho."""
    fonte = (
        "booking = Booking(status=policy.initial_status())\n"
        "evento = BookingApproved(status=booking.status)\n"
    )
    assert comparacoes_de_status(fonte) == []


def test_comparar_outro_atributo_nao_e_acusado() -> None:
    """A restrição é sobre o status, não sobre comparar coisa alguma."""
    fonte = "if booking.space_code == space.code:\n    pass\n"
    assert comparacoes_de_status(fonte) == []
