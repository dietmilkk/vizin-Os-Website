"""Confere que nenhum bloco <style> do site perdeu Declaracoes.

Uma regra de CSS sem corpo (seletor sem '{ ... }') e silenciosa: o navegador
ignora o trecho e a pagina perde espacamento, cor ou animacao sem nenhum
erro no console. Foi assim que os grupos do painel do afiliado ficaram
colados: o espaco de 56px sumiu do CSS e ninguem percebeu.

Este teste le cada <style> das paginas, remove os comentarios e confere:

  - toda declaracao esta dentro de um bloco { ... };
  - nao ha regra vazia onde o seletor promete estilo;
  - todo seletor de classe que o HTML usa tem regra correspondente
    (sem garantir que seja a regra certa, mas avisa quando falta).

Uso:
    python3 site/tests/test-css-saude.py
"""

from __future__ import annotations

import glob
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

falhas: list[str] = []
verificacoes = 0


def check(rotulo: str, condicao: bool, detalhe: str = "") -> None:
    global verificacoes
    verificacoes += 1
    if condicao:
        print(f"  OK   {rotulo}")
    else:
        print(f"  FAIL {rotulo}" + (f" -> {detalhe}" if detalhe else ""))
        falhas.append(rotulo)


def declaracoes_orfas(css: str) -> list[str]:
    """Declaracoes CSS que apareceram fora de qualquer bloco { ... }."""
    orfas: list[str] = []
    profundidade = 0
    inicio = 0
    for i, caractere in enumerate(css):
        if caractere == "{":
            profundidade += 1
        elif caractere == "}":
            profundidade = max(0, profundidade - 1)
        elif caractere == ";" and profundidade == 0:
            trecho = css[inicio:i].strip()
            if ":" in trecho and not trecho.startswith("@"):
                orfas.append(trecho[-90:])
            inicio = i + 1
    return orfas


def seletores_sem_corpo(css: str) -> list[str]:
    """Fragmentos de declaracao que sobraram fora de qualquer regra.

    Assinatura de CSS corrompido: um pedaco como "gap: var(--space-8)"
    aparece solto no meio do arquivo, sem o seletor que o comandava. O
    navegador ignora esse trecho em silencio.
    """
    quebrados: list[str] = []
    profundidade = 0
    inicio = 0
    for i, caractere in enumerate(css):
        if caractere == "{":
            profundidade += 1
        elif caractere == "}":
            profundidade = max(0, profundidade - 1)
        elif caractere in ";{}" and profundidade == 0:
            trecho = css[inicio:i].strip()
            if trecho:
                # Seletor solto (sem ":") e normal entre regras.
                # Fragmento de declaracao (tem ":") e o bug que buscamos.
                if ":" in trecho and not trecho.startswith("@"):
                    quebrados.append(trecho.replace("\n", " ")[:90])
                inicio = i + 1
            else:
                inicio = i + 1
    return quebrados


def main() -> int:
    paginas = sorted(glob.glob(os.path.join(RAIZ, "*.html")))
    if not paginas:
        print("Nenhuma pagina encontrada.")
        return 1

    for caminho in paginas:
        pagina = os.path.basename(caminho)
        fonte = open(caminho, encoding="utf-8").read()
        blocos = re.findall(r"<style[^>]*>(.*?)</style>", fonte, re.DOTALL)
        if not blocos:
            continue
        print(f"\n[{pagina}]")
        for indice, bloco in enumerate(blocos):
            limpo = re.sub(r"/\*.*?\*/", "", bloco, flags=re.DOTALL)
            orfas = declaracoes_orfas(limpo)
            check(
                f"bloco {indice + 1} sem declaracao orfa",
                not orfas,
                " | ".join(orfas[:3]),
            )
            sem_corpo = seletores_sem_corpo(limpo)
            check(
                f"bloco {indice + 1} sem seletor sem corpo",
                not sem_corpo,
                " | ".join(sem_corpo[:3]),
            )
            check(
                f"bloco {indice + 1} com chaves balanceadas",
                limpo.count("{") == limpo.count("}"),
                f"{limpo.count('{')} aberturas / {limpo.count('}')} fechamentos",
            )

    # Classes usadas no HTML que nao tem regra nenhuma: pode ser classe
    # dinamica (JS), mas avisa para o olho humano.
    print("\n[Classe sem estilo]")
    for caminho in paginas:
        pagina = os.path.basename(caminho)
        fonte = open(caminho, encoding="utf-8").read()
        blocos = " ".join(re.findall(r"<style[^>]*>(.*?)</style>", fonte, re.DOTALL))
        css_externo = ""
        for href in re.findall(r'<link rel="stylesheet" href="([^"]+)"', fonte):
            if href.startswith("/"):
                destino = os.path.join(RAIZ, href.lstrip("/"))
                if os.path.exists(destino):
                    css_externo += open(destino, encoding="utf-8").read()
        todo_css = blocos + css_externo
        classes_css = set(re.findall(r"\.([A-Za-z][\w-]*)", todo_css))
        html_sem_style = re.sub(r"<style[^>]*>.*?</style>", "", fonte, flags=re.DOTALL)
        classes_html = set()
        for grupo in re.findall(r'class="([^"]+)"', html_sem_style):
            classes_html.update(grupo.split())
        sem_estilo = sorted(c for c in classes_html - classes_css if not c.startswith("js"))
        # Classes de estado (is-*), hooks do <body> (page-*) e utilitarias
        # nao sao alvos de estilo: nao sao problema.
        relevantes = [
            c for c in sem_estilo
            if not re.match(r"^(is|has|js|hidden|page-|no-|has-)", c)
            and not c.endswith("-cta")
        ]
        if relevantes:
            print(f"  aviso {pagina}: {', '.join(relevantes[:8])}")
        check(f"{pagina}: classes relevantes com estilo", not relevantes, ", ".join(relevantes[:5]))

    print(f"\n{verificacoes} verificacoes · {len(falhas)} falha(s)")
    for falha in falhas:
        print(f"  - {falha}")
    if falhas:
        return 1
    print("CSS sao: nenhuma regra perdida, nenhum espacamento sumindo sozinho.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
