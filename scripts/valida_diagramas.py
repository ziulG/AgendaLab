#!/usr/bin/env python3
"""Valida todos os diagramas Mermaid embutidos na documentação do projeto.

Extrai cada bloco ```mermaid dos arquivos Markdown do repositório e submete cada um ao
mermaid-cli. Um diagrama com erro de sintaxe aparece no GitHub como um bloco quebrado,
e este script existe para que isso seja detectado antes do commit, e não pelo avaliador.

Uso:
    python3 scripts/valida_diagramas.py

Requer Node.js disponível no PATH; o mermaid-cli é baixado sob demanda via npx.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
BLOCO_MERMAID = re.compile(r"^```mermaid\n(.*?)^```", re.DOTALL | re.MULTILINE)
VERSAO_CLI = "@mermaid-js/mermaid-cli@11"


def extrair_blocos(markdown: Path) -> list[str]:
    return BLOCO_MERMAID.findall(markdown.read_text(encoding="utf-8"))


def validar(codigo: str, destino: Path) -> tuple[bool, str]:
    entrada = destino.with_suffix(".mmd")
    entrada.write_text(codigo, encoding="utf-8")
    resultado = subprocess.run(
        ["npx", "-y", "-q", VERSAO_CLI, "-i", str(entrada), "-o", str(destino.with_suffix(".svg"))],
        capture_output=True,
        text=True,
    )
    saida = destino.with_suffix(".svg")
    if resultado.returncode == 0 and saida.exists() and saida.stat().st_size > 0:
        return True, ""
    return False, (resultado.stderr or resultado.stdout).strip()


def main() -> int:
    markdowns = sorted(DOCS.rglob("*.md"))
    raiz_readme = RAIZ / "README.md"
    if raiz_readme.exists():
        markdowns.insert(0, raiz_readme)
    if not markdowns:
        print(f"Nenhum arquivo Markdown encontrado em {DOCS}")
        return 1

    total = 0
    falhas: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        area = Path(tmp)
        for md in markdowns:
            blocos = extrair_blocos(md)
            if not blocos:
                continue
            relativo = md.relative_to(RAIZ)
            for indice, codigo in enumerate(blocos, start=1):
                total += 1
                rotulo = f"{relativo}#{indice}"
                ok, erro = validar(codigo, area / f"{md.stem}-{indice:02d}")
                if ok:
                    print(f"  OK     {rotulo}")
                else:
                    print(f"  FALHA  {rotulo}")
                    if erro:
                        print("         " + erro.replace("\n", "\n         "))
                    falhas.append(rotulo)

    print("-" * 60)
    if falhas:
        print(f"{len(falhas)} de {total} diagrama(s) com erro: {', '.join(falhas)}")
        return 1

    print(f"{total} diagrama(s) validado(s) com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
