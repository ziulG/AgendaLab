#!/usr/bin/env python3
"""Verifica os links internos da documentação.

Percorre os arquivos Markdown do repositório e confere dois tipos de referência:

1. Links para arquivos relativos — o arquivo apontado precisa existir.
2. Âncoras de seção (#titulo) — o cabeçalho correspondente precisa existir no
   arquivo de destino, usando a mesma regra de slug do GitHub.

Um link quebrado num documento de defesa é um clique que falha na frente de quem avalia.

Uso:
    python3 scripts/valida_links.py
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# [texto](destino) — ignora imagens (![...]) e links absolutos
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
CABECALHO = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
BLOCO_CODIGO = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)


def slug_github(titulo: str) -> str:
    """Reproduz a regra de âncora do GitHub: minúsculas, pontuação removida,
    espaços viram hífen. Acentos são preservados."""
    texto = titulo.strip().lower()
    texto = re.sub(r"`([^`]*)`", r"\1", texto)  # remove crases
    texto = re.sub(r"[*_]", "", texto)  # remove ênfase
    texto = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", texto)  # link vira só o texto
    resultado = []
    for caractere in texto:
        if caractere.isalnum() or caractere in "-_ ":
            resultado.append(caractere)
        elif unicodedata.combining(caractere):
            resultado.append(caractere)
    texto = "".join(resultado)
    return texto.replace(" ", "-")


def ancoras_de(markdown: Path) -> set[str]:
    texto = BLOCO_CODIGO.sub("", markdown.read_text(encoding="utf-8"))
    return {slug_github(titulo) for _, titulo in CABECALHO.findall(texto)}


def main() -> int:
    markdowns = sorted(p for p in RAIZ.rglob("*.md") if ".venv" not in p.parts)
    cache_ancoras: dict[Path, set[str]] = {}
    problemas: list[str] = []
    total = 0

    for md in markdowns:
        texto = BLOCO_CODIGO.sub("", md.read_text(encoding="utf-8"))
        for destino in LINK.findall(texto):
            if destino.startswith(("http://", "https://", "mailto:")):
                continue
            total += 1
            origem = md.relative_to(RAIZ)

            caminho, _, ancora = destino.partition("#")
            alvo = md.parent / caminho if caminho else md

            if not alvo.exists():
                problemas.append(f"{origem}: arquivo inexistente -> {destino}")
                continue

            if ancora and alvo.suffix == ".md":
                if alvo not in cache_ancoras:
                    cache_ancoras[alvo] = ancoras_de(alvo)
                if ancora not in cache_ancoras[alvo]:
                    problemas.append(f"{origem}: âncora inexistente -> {destino}")

    print(f"{total} link(s) interno(s) verificado(s) em {len(markdowns)} arquivo(s).")
    print("-" * 60)
    if problemas:
        for p in problemas:
            print(f"  QUEBRADO  {p}")
        print("-" * 60)
        print(f"{len(problemas)} link(s) quebrado(s).")
        return 1

    print("Nenhum link quebrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
