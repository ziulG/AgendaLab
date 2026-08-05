"""Regra de dependência entre camadas — ADR-0001, RNF-01 e RNF-02.

A verificação é feita sobre a árvore sintática de cada módulo, não sobre o texto do arquivo:
um `import` dentro de comentário ou de string não conta, e um import de verdade é encontrado
onde quer que esteja — dentro de função, de `try` ou de `if TYPE_CHECKING`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "src" / "agendalab"

# O que cada camada NÃO pode importar.
# A apresentação é o composition root: conhece abstrações e implementações, e pode tudo.
FORBIDDEN_IMPORTS: dict[str, tuple[str, ...]] = {
    "domain": (
        "agendalab.application",
        "agendalab.infrastructure",
        "agendalab.presentation",
        "fastapi",
        "sqlalchemy",
        "pydantic",
    ),
    "application": (
        "agendalab.infrastructure",
        "agendalab.presentation",
        "fastapi",
        "sqlalchemy",
    ),
    "infrastructure": ("agendalab.presentation",),
    "presentation": (),
}


def package_of(path: Path) -> str:
    """Pacote que contém o módulo — a base contra a qual imports relativos são resolvidos."""
    return ".".join(path.relative_to(PACKAGE_ROOT.parent).parts[:-1])


def _absolute(package: str, level: int, module: str | None) -> str:
    """Resolve um import relativo: nível 1 é o próprio pacote, nível n sobe n-1 acima dele."""
    parts = package.split(".")
    if level > 1:
        parts = parts[: -(level - 1)]
    base = ".".join(parts)
    if base and module:
        return f"{base}.{module}"
    return module or base


def imported_modules(source: str, package: str) -> set[str]:
    """Módulos importados por `source`, em forma absoluta e com os relativos já resolvidos."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _absolute(package, node.level, node.module) if node.level else node.module
            if not base:
                continue
            found.add(base)
            # `from agendalab import infrastructure` esconde o nome proibido no alias
            found.update(f"{base}.{alias.name}" for alias in node.names if alias.name != "*")
    return found


def forbidden_hits(imports: set[str], layer: str) -> list[str]:
    """Os imports de `imports` que a camada `layer` não tem permissão de fazer."""
    banned = FORBIDDEN_IMPORTS[layer]
    return sorted(
        # comparação por prefixo com ponto, nunca `in`: `pydantic` não reprova `pydantic_settings`
        name
        for name in imports
        if any(name == module or name.startswith(f"{module}.") for module in banned)
    )


def _without_submodules(names: list[str]) -> list[str]:
    """Descarta o que já está coberto por um nome mais curto da lista, para não repetir o óbvio."""
    return [name for name in names if not any(name.startswith(f"{other}.") for other in names)]


def violations(layer: str) -> list[str]:
    """Uma mensagem por par (arquivo, import proibido) encontrado na camada."""
    problems: list[str] = []
    for path in sorted((PACKAGE_ROOT / layer).rglob("*.py")):
        imports = imported_modules(path.read_text(encoding="utf-8"), package_of(path))
        problems.extend(
            f"{path.relative_to(REPO_ROOT)}: importa `{name}` — proibido em `{layer}`"
            for name in _without_submodules(forbidden_hits(imports, layer))
        )
    return problems


@pytest.mark.parametrize("layer", list(FORBIDDEN_IMPORTS))
def test_a_camada_nao_importa_o_que_lhe_e_proibido(layer: str) -> None:
    problems = violations(layer)
    assert not problems, "Regra de dependência violada (ADR-0001):\n  " + "\n  ".join(problems)


def test_as_quatro_camadas_existem_e_sao_analisadas() -> None:
    """Sem esta guarda, um diretório renomeado faria a suíte passar analisando zero arquivos."""
    for layer in FORBIDDEN_IMPORTS:
        directory = PACKAGE_ROOT / layer
        assert (directory / "__init__.py").is_file(), f"a camada `{layer}` não é um pacote"
        assert list(directory.rglob("*.py")), f"nenhum módulo analisado na camada `{layer}`"


def test_import_dentro_de_funcao_tambem_e_detectado() -> None:
    source = "def conectar():\n    import sqlalchemy\n    return sqlalchemy\n"
    assert imported_modules(source, "agendalab.domain") == {"sqlalchemy"}


def test_import_em_comentario_ou_string_nao_conta() -> None:
    source = '# import sqlalchemy\nEXEMPLO = "from fastapi import APIRouter"\n'
    assert imported_modules(source, "agendalab.domain") == set()


def test_import_relativo_e_resolvido_ate_a_camada_de_origem() -> None:
    source = "from ...infrastructure.persistence import models\n"
    imports = imported_modules(source, "agendalab.domain.entities")
    assert "agendalab.infrastructure.persistence" in imports
    assert forbidden_hits(imports, "domain")


def test_o_verificador_reprova_um_import_proibido() -> None:
    """Um teste que nunca falha não prova nada: este exercita o caminho da reprovação."""
    assert forbidden_hits({"sqlalchemy"}, "domain") == ["sqlalchemy"]
    assert forbidden_hits({"sqlalchemy"}, "infrastructure") == []
    assert forbidden_hits({"pydantic_settings"}, "domain") == []
