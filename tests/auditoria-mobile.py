"""Auditoria de layout no celular: mede, em todas as paginas do site, o que
uma pessoa ve no telefone — estouro horizontal, altura das fontes, tamanho
das areas tocáveis e o aproveitamento da tela.

Uso:
    python3 tests/auditoria-mobile.py [http://127.0.0.1:8099]
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099"
PAGINAS = ["/", "/afiliados/", "/painel/", "/documento/", "/moderacao/", "/404.html"]

MOBILE = {"width": 390, "height": 844}
PEQUENO = {"width": 320, "height": 640}

problemas: list[str] = []


def auditar(page, largura: int) -> list[str]:
    achados: list[str] = []
    dados = page.evaluate(
        """(largura) => {
          const doc = document.documentElement;
          const fora = [];
          document.querySelectorAll('body *').forEach((el) => {
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return;
            const estilo = getComputedStyle(el);
            if (estilo.position === 'fixed' || estilo.visibility === 'hidden') return;
            if (r.right > largura + 1 || r.left < -1) {
              fora.push({
                tag: el.tagName,
                cls: (el.className || '').toString().slice(0, 44),
                left: Math.round(r.left),
                right: Math.round(r.right),
              });
            }
          });

          // Textos pequenos demais para leitura no celular.
          const textosPequenos = [];
          document.querySelectorAll('p, li, span, a, small, label, td, th, button').forEach((el) => {
            if (!el.textContent || !el.textContent.trim()) return;
            if (el.children.length) return;
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return;
            const estilo = getComputedStyle(el);
            if (estilo.visibility === 'hidden' || estilo.display === 'none') return;
            const tamanho = parseFloat(estilo.fontSize);
            if (tamanho < 12) {
              textosPequenos.push({
                tag: el.tagName,
                cls: (el.className || '').toString().slice(0, 44),
                tamanho,
                texto: el.textContent.trim().slice(0, 40),
              });
            }
          });

          // Areas tocaveis pequenas (alvo minimo recomendado: 40px).
          // Link de dentro do texto nao conta: ele vive dentro da linha do
          // paragrafo e nao pode virar bloco sem quebrar o texto.
          const alvosPequenos = [];
          document.querySelectorAll('a, button, input, select, textarea').forEach((el) => {
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return;
            const estilo = getComputedStyle(el);
            if (estilo.visibility === 'hidden' || estilo.display === 'none') return;
            if (el.tagName === 'A' && el.closest('p, li, figcaption, td, th')) return;
            if (r.height < 32) {
              alvosPequenos.push({
                tag: el.tagName,
                cls: (el.className || '').toString().slice(0, 44),
                altura: Math.round(r.height),
                texto: (el.textContent || el.value || '').trim().slice(0, 30),
              });
            }
          });

          const alturaConteudo = document.body.scrollHeight;
          return {
            scrollWidth: doc.scrollWidth,
            clientWidth: doc.clientWidth,
            fora: fora.slice(0, 8),
            textosPequenos: textosPequenos.slice(0, 8),
            alvosPequenos: alvosPequenos.slice(0, 8),
            alturaConteudo,
          };
        }""",
        largura,
    )
    if dados["scrollWidth"] > dados["clientWidth"] + 1:
        achados.append(
            f"rolagem horizontal ({dados['scrollWidth']} > {dados['clientWidth']})"
        )
    for item in dados["fora"]:
        achados.append(
            f"fora da tela: <{item['tag']} class='{item['cls']}'> "
            f"({item['left']}..{item['right']})"
        )
    for item in dados["textosPequenos"]:
        achados.append(
            f"fonte pequena: <{item['tag']} class='{item['cls']}'> "
            f"{item['tamanho']}px '{item['texto']}'"
        )
    for item in dados["alvosPequenos"]:
        achados.append(
            f"area tocavel pequena: <{item['tag']} class='{item['cls']}'> "
            f"{item['altura']}px '{item['texto']}'"
        )
    return achados


with sync_playwright() as playwright:
    browser = playwright.firefox.launch()
    for rotulo, viewport in (("celular 390px", MOBILE), ("celular 320px", PEQUENO)):
        contexto = browser.new_context(viewport=viewport, is_mobile=True, has_touch=True)
        page = contexto.new_page()
        print(f"\n=== {rotulo} ===")
        for rota in PAGINAS:
            page.goto(BASE + rota, wait_until="networkidle")
            page.wait_for_timeout(900)
            achados = auditar(page, viewport["width"])
            if achados:
                print(f"  [ATENCAO] {rota}")
                for achado in achados:
                    print(f"      - {achado}")
                    problemas.append(f"{rotulo} {rota}: {achado}")
            else:
                print(f"  [ok] {rota}")
        contexto.close()
    browser.close()

print()
if problemas:
    print(f"{len(problemas)} ponto(s) de atencao")
    sys.exit(1)
print("Layout mobile sem pontos de atencao em todas as paginas.")
