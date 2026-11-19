"""Remove do bloco <style> legado de afiliados.html as regras cujas classes
nao existem mais no HTML (guia em acordeao, split-bar, program-grid, etc.).

O script e conservador: so remove a regra se TODAS as classes que ela
menciona nao aparecem no HTML nem sao alternadas pelo JS.

ATENCAO: o bloco e reescrito por inteiro, entao rode apenas uma vez e
confira com "python3 site/tools/check-site.py" + uma comparacao visual
depois. O modo --simular mostra o que seria removido.

Uso:
    python3 site/tools/limpar-css-legado.py [--simular]
"""

from __future__ import annotations

import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO = os.path.join(RAIZ, "afiliados.html")

# Classes que o JS alterna em tempo de execucao: nunca podem sair.
ESTADOS_JS = {
    "js", "hidden", "is-visible", "is-active", "is-current", "is-panel",
    "is-loaded", "is-error", "is-ok", "is-guarding", "is-open",
}


def classes_no_html(html_sem_style: str) -> set[str]:
    usadas: set[str] = set()
    for bloco in re.findall(r'class="([^"]+)"', html_sem_style):
        usadas.update(bloco.split())
    return usadas


def classes_no_js(raiz: str) -> set[str]:
    usadas: set[str] = set()
    for nome in ("creators.js", "app.js", "comunidade.js", "panel.js"):
        caminho = os.path.join(raiz, "assets", nome)
        if not os.path.exists(caminho):
            continue
        codigo = open(caminho, encoding="utf-8").read()
        for classe in re.findall(r"classList\.(?:add|remove|toggle)\('([\w-]+)'", codigo):
            usadas.add(classe)
        for classe in re.findall(r"classList\.(?:add|remove|toggle)\(\"([\w-]+)\"", codigo):
            usadas.add(classe)
        for bloco in re.findall(r'class="([^"]+)"', codigo):
            usadas.update(bloco.split())
        usadas.update(re.findall(r"className\s*=\s*'([^']+)'", codigo))
    return usadas


def main() -> int:
    simular = "--simular" in sys.argv
    fonte = open(ARQUIVO, encoding="utf-8").read()

    estilo = re.search(r"<style[^>]*>(.*?)</style>", fonte, re.S)
    if not estilo:
        print("afiliados.html nao tem <style> legado.")
        return 0

    bloco = estilo.group(1)
    html_sem_style = re.sub(r"<style[^>]*>.*?</style>", "", fonte, flags=re.S)
    vivas = classes_no_html(html_sem_style) | classes_no_js(RAIZ) | ESTADOS_JS

    # Cada regra do bloco: seletor + corpo. Os comentarios sao preservados.
    partes = re.findall(r"([^{}]+)\{([^{}]*)\}", bloco)
    mantidas: list[str] = []
    removidas: list[str] = []
    for seletor, corpo in partes:
        seletor_limpo = seletor.strip()
        if seletor_limpo.startswith("/*"):
            # Comentario solto (sem chaves): e cabecalho de secao — mantem.
            mantidas.append(seletor_limpo)
            continue
        classes = set(re.findall(r"\.([A-Za-z][\w-]*)", seletor_limpo))
        if classes and not (classes & vivas):
            removidas.append(seletor_limpo)
        else:
            mantidas.append(seletor_limpo + "{" + corpo + "}")

    novo_bloco = "\n" + "\n".join(mantidas) + "\n  "
    print(f"regras removidas: {len(removidas)} | mantidas: {len(mantidas)}")
    print(f"bytes: {len(bloco)} -> {len(novo_bloco)}")
    for seletor in removidas[:12]:
        print(f"  - {seletor.splitlines()[0][:70]}")

    if simular:
        return 0

    # Nao reescreve se o resultado nao fechar as chaves (regra malformada).
    if novo_bloco.count("{") != novo_bloco.count("}"):
        print("ABORTADO: o bloco reescrito nao fecha as chaves. Nada foi alterado.")
        return 1

    novo_html = fonte.replace(bloco, novo_bloco, 1)
    open(ARQUIVO, "w", encoding="utf-8").write(novo_html)
    print("afiliados.html atualizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
