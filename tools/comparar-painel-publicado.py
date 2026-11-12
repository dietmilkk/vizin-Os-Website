#!/usr/bin/env python3
"""Compara a pagina /painel publicada com a versao local do repositorio.

O page.gd pede verificacao de JavaScript, entao a comparacao e feita no
Chromium (o que um visitante ve) e nao com curl. O script extrai do DOM
publicado a estrutura da grade (classes e ids dos blocos) e compara com o
HTML local.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://vizin-os.page.gd").rstrip("/")
LOCAL = Path(__file__).resolve().parent.parent / "painel" / "index.html"

JS = """
() => {
  const ids = Array.from(document.querySelectorAll('[id]'))
    .map((el) => el.id)
    .filter((id) => id.startsWith('painel'));
  const blocos = Array.from(document.querySelectorAll('.stats-grid--bento .stat')).map((el) => ({
    classes: el.className,
    rotulo: (el.querySelector('.label') || {}).textContent?.trim() || '',
  }));
  return {ids, blocos};
}
"""


def ids_locais() -> list[str]:
    texto = LOCAL.read_text(encoding="utf-8")
    achados = re.findall(r'id="(painel[^"]*)"', texto)
    return sorted(set(achados))


def main() -> int:
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        pagina = navegador.new_page()
        pagina.goto(f"{BASE}/painel", wait_until="networkidle")
        pagina.wait_for_function(
            "() => document.getElementById('painelStatusTexto')"
            "?.textContent?.startsWith('Atualizado')",
            timeout=30_000,
        )
        dados = pagina.evaluate(JS)
        navegador.close()

    ids_publicados = sorted(set(dados["ids"]))
    ids_esperados = ids_locais()
    faltando = [i for i in ids_esperados if i not in ids_publicados]
    sobrando = [i for i in ids_publicados if i not in ids_esperados]

    print(f"ids no HTML local: {len(ids_esperados)}")
    print(f"ids no DOM publicado: {len(ids_publicados)}")
    print(f"faltando no publicado: {faltando if faltando else 'nenhum'}")
    print(f"so no publicado: {sobrando if sobrando else 'nenhum'}")
    print(f"\nblocos na grade bento publicada: {len(dados['blocos'])}")
    for b in dados["blocos"]:
        print(f"  {b['rotulo'][:32]:34} {b['classes']}")

    if faltando:
        print("\nFALHA: a pagina publicada esta desatualizada.")
        return 1
    print("\nOK: a pagina publicada tem todos os blocos do HTML local.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
