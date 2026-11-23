"""Confere, como quem usa, a pagina de Membros depois da reformulacao.

O guia em acordeao saiu: a explicacao agora esta em secoes sempre
visiveis (escolha do papel, como funciona, divisao do valor). Este teste
confere o que importa para quem chega na pagina:

- o hero explica o programa em uma frase e tem o botao de criar conta;
- as secoes "Escolha seu papel", "Como funciona" e "Como o valor e dividido"
  existem, sao visiveis e tem textos nao vazios;
- a divisao do valor virou uma planilha com os cinco papeis (50/25/10/5/10),
  alimentada por uma configuracao unica que soma 100%;
- a secao "Por que essa divisao e justa" destaca o merito do criador;
- o efeito multiplicador tem diagrama de fluxo e simulacao ilustrativa;
- os botoes de criar conta abrem a janela de cadastro;
- o rodape continua minimalista (icone + titulo ao lado);
- nenhum erro de JavaScript na pagina.

Uso:
    python3 tests/test-guia-acordeao.py [http://127.0.0.1:8099]
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099"
ROOT = Path(__file__).resolve().parents[1]

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


def main() -> int:
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1366, "height": 900})
        erros: list[str] = []
        pagina.on("pageerror", lambda e: erros.append(str(e)))

        pagina.goto(f"{BASE}/membros", wait_until="load")
        pagina.wait_for_timeout(900)
        # A guarda de IP pode esconder os CTAs por alguns segundos. Nos testes,
        # removemos esse estado para medir a pagina real sem corrida de timing.
        pagina.evaluate("document.documentElement.classList.remove('is-guarding')")

        fonte_html = urllib.request.urlopen(f"{BASE}/membros", timeout=10).read().decode("utf-8")
        fallbacks_percentuais = re.findall(
            r'data-revenue-share="[^"]+"[^>]*>\s*[^<\s][^<]*', fonte_html
        )
        check(
            "HTML nao fixa percentuais fora da configuracao",
            not fallbacks_percentuais,
            str(fallbacks_percentuais[:3]),
        )
        bloco_divisao = re.search(
            r'<section\b[^>]*id="divisao".*?</section>',
            fonte_html,
            re.IGNORECASE | re.DOTALL,
        )
        if bloco_divisao:
            sem_campos_dinamicos = re.sub(
                r'<[^>]*data-revenue-(?:share|sim)[^>]*>.*?</[^>]+>',
                '',
                bloco_divisao.group(0),
                flags=re.DOTALL,
            )
            percentuais_fixos = re.findall(r'\b(?:50|25|10|5)%', sem_campos_dinamicos)
            check(
                "prosa da divisao nao repete percentuais fora da config",
                not percentuais_fixos,
                str(percentuais_fixos[:5]),
            )

        rodapes_com_icone_grande = []
        for pagina_html in sorted(ROOT.glob("*.html")):
            fonte = pagina_html.read_text(encoding="utf-8")
            rodape = re.search(r"<footer\b.*?</footer>", fonte, re.IGNORECASE | re.DOTALL)
            if rodape and re.search(
                r'<img\b[^>]*\bwidth=["\']115["\'][^>]*>', rodape.group(0), re.IGNORECASE
            ):
                rodapes_com_icone_grande.append(pagina_html.name)
        check(
            "nenhum rodape usa o icone grande de 115px",
            not rodapes_com_icone_grande,
            ", ".join(rodapes_com_icone_grande),
        )

        # A janela de primeira visita aparece na primeira navegacao: um
        # usuario real fecha antes de continuar.
        if pagina.locator("#firstVisitModal").is_visible():
            pagina.click('.modal-close[data-first-visit-close]')
            pagina.wait_for_timeout(300)

        print("\n[1] O programa se explica na primeira dobra")
        titulo = pagina.locator("h1#aff-title")
        check("titulo principal existe", titulo.count() == 1)
        texto_titulo = titulo.inner_text().strip() if titulo.count() else ""
        check("titulo diz o que a pessoa ganha", len(texto_titulo) > 20, texto_titulo)
        check(
            "hero tem botao para criar conta",
            pagina.locator('[data-open-create="creator"]:visible').count() >= 1,
        )
        lead = pagina.locator(".aff-hero__lead").inner_text().strip()
        check("hero tem um texto de apoio", len(lead) > 40, lead[:60])

        print("\n[2] As secoes que explicam o programa estao visiveis")
        for seletor, rotulo in [
            ('#por-que', "por que esse modelo funciona"),
            ('#how-it-works', "escolha seu papel"),
            ('#divisao', "divisao do valor"),
            ('#justica', "por que essa divisao e justa"),
            ('#efeito-multiplicador', "efeito multiplicador"),
            ('#participar', "chamada final"),
        ]:
            bloco = pagina.locator(seletor)
            check(f"secao '{rotulo}' existe", bloco.count() == 1)
            if bloco.count():
                texto = bloco.inner_text().strip()
                check(f"secao '{rotulo}' tem conteudo", len(texto) > 80, f"{len(texto)} chars")
                box = bloco.bounding_box()
                check(f"secao '{rotulo}' tem altura", bool(box and box["height"] > 120))

        print("\n[3] A divisao do valor virou uma planilha com config unica")
        config = pagina.evaluate("() => window.VIZIN_REVENUE_SPLIT")
        check("configuracao da divisao existe", bool(config), str(config))
        esperado = {
            "creator": 50,
            "user": 25,
            "affiliate": 10,
            "mod": 5,
            "development": 10,
        }
        if config:
            check(
                "configuracao soma 100%",
                config.get("total") == 100,
                str(config.get("total")),
            )
            check(
                "percentuais da config batem com a especificacao",
                config.get("shares") == esperado,
                str(config.get("shares")),
            )
            check(
                "premissas da simulacao ficam na mesma config",
                config.get("simulation") == {
                    "mods": 1,
                    "affiliatesPerMod": 10,
                    "creatorsPerAffiliate": 5,
                    "referencePerCreator": 100,
                },
                str(config.get("simulation")),
            )

        planilha = pagina.locator(".revenue-sheet")
        check(
            "planilha da divisao existe",
            planilha.count() == 1 and planilha.first.is_visible(),
        )
        linhas = pagina.locator(".revenue-sheet__table tbody tr")
        check("planilha tem os cinco papeis", linhas.count() == 5, str(linhas.count()))
        if linhas.count() == 5:
            mapa_planilha = linhas.evaluate_all(
                """rows => rows.map(row => ({
                    papel: row.querySelector('.revenue-role__name')?.textContent?.trim(),
                    divisao: row.querySelector('.revenue-sheet__share [data-revenue-share]')?.textContent?.trim(),
                    funcao: row.querySelector('.revenue-sheet__function-label')?.textContent?.trim(),
                }))"""
            )
            esperado_planilha = [
                ("Criadores de conteúdo", "50%", "Produzem e trazem usuários"),
                ("Usuários", "25%", "Recebem desconto no app"),
                ("Afiliados", "10%", "Recrutam criadores"),
                ("Mods Parceiros", "5%", "Recrutam afiliados"),
                ("Desenvolvimento", "10%", "Manutenção e servidores"),
            ]
            for indice, (papel, divisao, funcao) in enumerate(esperado_planilha):
                linha = mapa_planilha[indice]
                check(f"planilha mapeia {papel} corretamente", linha == {"papel": papel, "divisao": divisao, "funcao": funcao}, str(linha))
            check(
                "total da planilha vem da mesma configuracao",
                pagina.locator(".revenue-sheet__table tfoot [data-revenue-total]").inner_text().strip() == "100%",
            )
        check(
            "barra horizontal antiga removida do HTML",
            pagina.locator(".aff-splitbar, .split-bar, .split-segment, .split-grid").count() == 0,
        )
        css_pagina = "".join(
            urllib.request.urlopen(f"{BASE}/assets/{nome}", timeout=10).read().decode("utf-8")
            for nome in ("styles.css", "affiliates.css", "panel-refine.css", "revenue-split.css")
        )
        check(
            "barra horizontal antiga removida do CSS",
            not re.search(r"aff-splitbar|split-bar|split-segment|split-grid", css_pagina, re.I),
        )

        print("\n[4] A secao de merito e o efeito multiplicador")
        justica = pagina.locator("#justica").inner_text().lower()
        check("secao fala de meritocracia", "meritocracia" in justica, justica[:100])
        check(
            "secao destaca o criador",
            "a base do valor" in justica and "sem criador" in justica,
        )
        check(
            "secao cita o Mod Parceiro e o volume acumulado",
            "mod parceiro" in justica and "volume acumulado" in justica,
        )

        efeito = pagina.locator("#efeito-multiplicador").inner_text()
        check("secao cita o efeito multiplicador", "efeito multiplicador" in efeito.lower())
        check("diagrama de fluxo existe", pagina.locator(".revenue-network").count() == 1)
        check(
            "diagrama usa lista semantica",
            pagina.locator(".revenue-network__levels").evaluate("el => el.tagName") == "OL",
        )
        papeis_fluxo = pagina.locator(".revenue-network__role strong").all_inner_texts()
        check(
            "diagrama preserva a ordem Mod, Afiliados, Criadores e Usuarios",
            papeis_fluxo == ["Mod Parceiro", "Afiliados", "Criadores", "Usuários"],
            str(papeis_fluxo),
        )
        check("simulacao identificada", "simulação ilustrativa" in efeito.lower())
        check(
            "simulacao mostra 1 Mod, 10 Afiliados e 50 Criadores",
            all(trecho in efeito for trecho in ("1", "10", "50")),
        )
        valores_simulacao = pagina.locator("[data-revenue-sim]").evaluate_all(
            """nodes => Object.fromEntries(nodes.map(node => [
                node.getAttribute('data-revenue-sim'), node.textContent.trim()
            ]))"""
        )
        def sem_espaco_fino(valor: str) -> str:
            return (valor or "").replace("\u00a0", " ").strip()

        check("simulacao calcula 50 criadores", valores_simulacao.get("creators") == "50", str(valores_simulacao))
        check(
            "simulacao calcula R$ 5.000,00 de base",
            sem_espaco_fino(valores_simulacao.get("networkReferenceTotal")) == "R$ 5.000,00",
            str(valores_simulacao),
        )
        check(
            "simulacao informa o total efetivamente cobrado",
            sem_espaco_fino(valores_simulacao.get("networkPaidTotal")) == "R$ 3.750,00",
            str(valores_simulacao),
        )
        check(
            "prosa usa os valores por compra vindos da config",
            all(
                sem_espaco_fino(valores_simulacao.get(chave)) == esperado
                for chave, esperado in {
                    "userDiscountPerCreator": "R$ 25,00",
                    "affiliateRevenuePerCreator": "R$ 10,00",
                    "modRevenuePerCreator": "R$ 5,00",
                    "developmentRevenuePerCreator": "R$ 10,00",
                }.items()
            ),
            str(valores_simulacao),
        )
        check(
            "simulacao calcula R$ 250,00 para o Mod",
            sem_espaco_fino(valores_simulacao.get("modRevenue")) == "R$ 250,00",
            str(valores_simulacao),
        )
        check(
            "simulacao calcula R$ 50,00 para o criador isolado",
            sem_espaco_fino(valores_simulacao.get("creatorRevenue")) == "R$ 50,00",
            str(valores_simulacao),
        )
        check(
            "comparacao usa a mesma base de 50 criadores",
            sem_espaco_fino(valores_simulacao.get("creatorNetworkRevenue")) == "R$ 2.500,00",
            str(valores_simulacao),
        )
        check("simulacao nao promete ganho", "não é promessa de ganho" in efeito)

        proibidas = (
            "pirâmide",
            "esquema",
            "renda passiva garantida",
            "ganhar sem fazer nada",
        )
        pagina_inteira = pagina.locator("body").inner_text().lower()
        check("sem termos proibidos", not any(t in pagina_inteira for t in proibidas))
        for termo in (
            "rede de afiliados",
            "divisão de receita",
            "efeito multiplicador",
            "meritocracia",
        ):
            check(f"termo obrigatorio '{termo}' presente", termo in pagina_inteira)

        print("\n[5] A leitura continua clara em tela estreita")
        pagina.set_viewport_size({"width": 320, "height": 800})
        pagina.wait_for_timeout(250)
        medidas_mobile = pagina.evaluate(
            """() => {
              const doc = document.documentElement;
              const nivel = document.querySelector('.revenue-network__level');
              const papel = nivel?.querySelector('.revenue-network__role');
              const base = nivel?.querySelector('.revenue-network__basis');
              const ledger = document.querySelector('.revenue-simulation__ledger');
              return {
                scrollWidth: doc.scrollWidth,
                clientWidth: doc.clientWidth,
                nivelColunas: nivel ? getComputedStyle(nivel).gridTemplateColumns : '',
                baseAoLado: papel && base ? base.getBoundingClientRect().left >= papel.getBoundingClientRect().right - 1 : false,
                linhasConta: ledger ? ledger.querySelectorAll('.revenue-simulation__row').length : 0,
              };
            }"""
        )
        check(
            "sem estouro horizontal em 320px",
            medidas_mobile["scrollWidth"] <= medidas_mobile["clientWidth"] + 1,
            str(medidas_mobile),
        )
        check(
            "fluxo da rede permanece em duas colunas legiveis",
            len(medidas_mobile["nivelColunas"].split()) == 2,
            str(medidas_mobile),
        )
        check(
            "base de calculo fica ao lado do papel no celular",
            medidas_mobile["baseAoLado"],
            str(medidas_mobile),
        )
        check(
            "conta da simulacao tem apenas tres linhas",
            medidas_mobile["linhasConta"] == 3,
            str(medidas_mobile),
        )
        check(
            "rotulo da fatia aparece na tabela mobile",
            pagina.locator(".revenue-sheet__mobile-label").first.is_visible(),
        )
        pagina.set_viewport_size({"width": 1366, "height": 900})
        pagina.wait_for_timeout(150)

        print("\n[6] Criar conta abre a janela certa")
        pagina.click('[data-open-create="afiliado"]:visible')
        pagina.wait_for_timeout(500)
        check(
            "janela de criacao abriu",
            pagina.locator("#createModal").is_visible(),
        )
        check(
            "campo de codigo existe",
            pagina.locator("#code").count() == 1,
        )
        pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(400)

        print("\n[7] Rodape minimalista")
        rodape = pagina.locator(".site-footer")
        check("rodape presente", rodape.count() == 1)
        cartoes = pagina.locator(".explore-card")
        check("cartoes de exploracao presentes", cartoes.count() >= 4, str(cartoes.count()))
        icone = cartoes.first.locator(".explore-card__icon")
        titulo_card = cartoes.first.locator("span").first
        box_i = icone.bounding_box()
        box_t = titulo_card.bounding_box()
        check(
            "icone e titulo ficam lado a lado",
            bool(box_i and box_t and abs(box_i["y"] - box_t["y"]) < 24),
        )

        print("\n[7] Sem erros de JavaScript")
        check("nenhum erro de runtime", not erros, "; ".join(erros[:3]))

        navegador.close()

    print(f"\n{verificacoes} verificacoes · {len(falhas)} falha(s)")
    for falha in falhas:
        print(f"  - {falha}")
    if falhas:
        return 1
    print("A pagina de Membros se explica sozinha, do jeito que o usuario precisa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
