"""Teste de uso real do programa de parceiros, contra a producao.

Percorre o caminho inteiro como um visitante faria, em um navegador limpo
(sem cache nem cookies de execucoes anteriores):

1. abre a pagina publica /afiliados e confere o conteudo;
2. abre a janela de criacao de conta de afiliado;
3. cria a conta de verdade (clica no botao) e confere a confirmacao;
4. entra no painel pelo botao "Ir para o painel" e confere os numeros;
5. recarrega a pagina com o link do painel e confere que o acesso persiste;
6. tenta criar uma segunda conta do MESMO papel e confere o aviso de IP
   duplicado (na API e dentro da janela de criacao);
7. cria uma conta do OUTRO papel no mesmo IP e confere que ela passa — um
   mesmo endereco pode ter uma conta de criador e uma de afiliado;
8. tenta acessar a pagina com IP de datacenter e confere o 404.

O `handle` da conta criada pelo navegador e carimbado com o prefixo `usrreal`
antes de chegar na API (o resto da requisicao vai intacto). Sem isso o
`@` da conta seria aleatorio — o codigo do afiliado e sorteado pelo
navegador — e a conta de teste nao poderia ser reconhecida pela ferramenta
de limpeza (`tools/limpar-teste.sh`), deixando o IP da maquina bloqueado.

Uso:
    python3 tests/test-usuario-real.py
    tools/limpar-teste.sh --aplicar   # depois do teste
"""

import json
import sys
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

from lib.primeiro_acesso import ja_visitou

SITE = "https://site.188.166.156.109.sslip.io"
API = "https://api.188.166.156.109.sslip.io"

failures = []
checks = 0


def check(label, condition, detail=""):
    global checks
    checks += 1
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label}" + (f" -> {detail}" if detail else ""))
        failures.append(label)


def api_post(path, payload):
    request = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def main():
    codigo = "USR" + str(int(time.time()))[-6:]
    handle_teste = "usrreal" + codigo[-6:].lower()
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        contexto = browser.new_context(viewport={"width": 1366, "height": 900})
        ja_visitou(contexto)
        pagina = contexto.new_page()
        erros_js = []
        pagina.on("pageerror", lambda erro: erros_js.append(str(erro)))

        # Carimba o handle da conta de teste (o resto da requisicao vai intacto)
        # para que a ferramenta de limpeza reconheca e apague a conta.
        def carimba_handle(rota):
            try:
                corpo = rota.request.post_data_json
            except Exception:
                corpo = None
            if isinstance(corpo, dict):
                corpo["handle"] = handle_teste
                rota.continue_(post_data=json.dumps(corpo))
            else:
                rota.continue_()

        pagina.route(f"{API}/hunters", carimba_handle)

        # ---------------------------------------------------------- 1. pagina
        print("\n[1] Pagina publica /afiliados")
        pagina.goto(f"{SITE}/afiliados/", wait_until="domcontentloaded")
        pagina.wait_for_timeout(3500)
        check("url correta", "/afiliados" in pagina.url, pagina.url)
        check("titulo do programa", "criadores" in pagina.title().lower(), pagina.title())
        check("hero visivel", pagina.locator("h1").first.is_visible())
        for secao in ("divisao", "participar"):
            check(
                f"secao #{secao} presente",
                pagina.locator(f"#{secao}").count() == 1,
            )
        # A secao curta (#porDentro) foi substituida pelo guia completo. O
        # teste roda contra o site publicado, entao os dois formatos sao
        # aceitos: o que nao pode e os dois visiveis ao mesmo tempo.
        guia_visivel = (
            pagina.locator("#guiaCompleto").count() == 1
            and pagina.locator("#guiaCompleto").first.is_visible()
        )
        curta_visivel = (
            pagina.locator("#porDentro").count() == 1
            and pagina.locator("#porDentro").first.is_visible()
        )
        check(
            "guia completo e secao curta nao aparecem ao mesmo tempo",
            not (guia_visivel and curta_visivel),
            f"guia={guia_visivel} curta={curta_visivel}",
        )
        check(
            "pagina publica mostra o guia (ou a secao curta, ate a publicacao)",
            guia_visivel or curta_visivel,
            f"guia={guia_visivel} curta={curta_visivel}",
        )
        check(
            "secao #movimento removida da pagina publica",
            pagina.locator("#movimento").count() == 0,
        )
        check("sem erros de JavaScript", not erros_js, "; ".join(erros_js))

        # ------------------------------------------------------ 2. abrir janela
        print("\n[2] Janela de criacao de conta")
        pagina.locator("[data-open-create='afiliado']").first.click()
        pagina.wait_for_timeout(700)
        check("janela aberta", pagina.locator("#createModal").is_visible())
        check("titulo de afiliado", pagina.locator("#createTitle").inner_text().strip() == "Criar conta")
        check(
            "campo de codigo escondido para afiliado",
            pagina.locator("#code").is_hidden(),
        )
        check(
            "sem aviso no inicio (IP ainda livre)",
            pagina.locator("#createWarning").is_hidden(),
        )

        # ------------------------------------------------------ 3. criar conta
        print("\n[3] Criar conta (clique no botao)")
        pagina.locator("#createButton").click()
        # Espera o texto do link mudar: o `href` de um `<a href="#">` ja resolve
        # para uma URL valida, entao comparar o atributo nao prova que a conta
        # foi criada. O texto so e reescrito quando a API responde.
        try:
            pagina.wait_for_function(
                """() => {
                  const link = document.getElementById('dashboardLink');
                  return link && /\\?p=/.test(link.textContent || '');
                }""",
                timeout=60000,
            )
        except Exception:
            # A conta nao foi criada: a API recusou. O aviso aparece na janela.
            pass
        check(
            "confirmacao de conta criada",
            pagina.locator("#createdView").is_visible(),
            pagina.locator("#createError").inner_text()
            or pagina.locator("#createWarning").inner_text(),
        )
        link_painel = pagina.locator("#dashboardLink").inner_text().strip()
        # Link curto atual (?p=) ou link antigo (?afiliado_token=).
        check(
            "link do painel gerado",
            link_painel and ("?p=" in link_painel or "afiliado_token=" in link_painel),
            link_painel,
        )

        # ------------------------------------------------------ 4. ir ao painel
        print("\n[4] Entrar no painel")
        pagina.locator("#openDashboard").click()
        pagina.wait_for_timeout(5000)
        check("painel aberto", pagina.locator("#afiliadoDashboardView").is_visible())
        check("link de afiliado em destaque", pagina.locator("#copyAfiliadoLink").count() == 1)
        link_afiliado = pagina.locator("#afiliadoLink").input_value()
        check("link de afiliado preenchido", "?a=" in link_afiliado, link_afiliado)
        check("sem erros de JavaScript ate aqui", not erros_js, "; ".join(erros_js))

        # ------------------------------------------- 5. recarregar com o link
        print("\n[5] Recarregar a pagina com o link do painel")
        pagina.goto(link_painel, wait_until="domcontentloaded")
        pagina.wait_for_timeout(5000)
        check("painel continua aberto apos recarregar", pagina.locator("#afiliadoDashboardView").is_visible())
        check(
            "guia completo aparece com o painel",
            pagina.locator("#guiaCompleto").first.is_visible(),
        )

        # ------------------------- 6. segunda conta do mesmo papel: aviso
        print("\n[6] Criar uma segunda conta do MESMO papel (mesmo IP)")
        status, dados = api_post(
            "/hunters", {"handle": handle_teste + "b", "code": codigo + "B"}
        )
        check("API recusa a segunda conta", status == 403, str(status))
        check("codigo do bloqueio", dados.get("code") == "IP_BLOCKED_DUPLICATE", str(dados))
        check(
            "mensagem com o texto pedido",
            "já criou uma conta" in str(dados.get("error", "")),
            str(dados.get("error")),
        )

        # mesma coisa pela interface: o aviso tem que aparecer na janela
        pagina.goto(f"{SITE}/afiliados/", wait_until="domcontentloaded")
        pagina.wait_for_timeout(3500)
        pagina.locator("[data-open-create='afiliado']").first.click()
        pagina.wait_for_timeout(700)
        aviso = pagina.locator("#createWarning")
        check("aviso visivel na janela", aviso.is_visible())
        check(
            "texto do aviso",
            "já criou uma conta" in aviso.inner_text(),
            aviso.inner_text(),
        )
        caixa = aviso.bounding_box()
        check("aviso pequeno", bool(caixa) and caixa["height"] < 160, str(caixa))

        # ------------------------- 7. conta do OUTRO papel: deve ser aceita
        print("\n[7] Criar conta do OUTRO papel no mesmo IP (deve funcionar)")
        pagina.locator("#createModal .modal-close").first.click()
        pagina.wait_for_timeout(400)
        pagina.locator("[data-open-create='creator']").first.click()
        pagina.wait_for_timeout(700)
        check(
            "sem aviso para o papel ainda livre",
            pagina.locator("#createWarning").is_hidden(),
            pagina.locator("#createWarning").inner_text(),
        )
        codigo_criador = "USR" + str(int(time.time()))[-6:]
        pagina.locator("#code").fill(codigo_criador)
        pagina.locator("#createButton").click()
        # Mesma espera do passo 3: o texto do link só muda quando a API responde.
        pagina.wait_for_function(
            """() => {
              const link = document.getElementById('dashboardLink');
              return link && /\\?p=/.test(link.textContent || '');
            }""",
            timeout=60000,
        )
        check(
            "conta de criador criada no mesmo IP",
            pagina.locator("#createdView").is_visible(),
            pagina.locator("#createError").inner_text(),
        )
        link_criador = pagina.locator("#dashboardLink").inner_text().strip()
        check(
            "link do painel do criador gerado",
            "?p=C" in link_criador,
            link_criador,
        )

        # os dois papeis avisam a partir de agora
        pagina.goto(f"{SITE}/afiliados/", wait_until="domcontentloaded")
        pagina.wait_for_timeout(3500)
        pagina.locator("[data-open-create='afiliado']").first.click()
        pagina.wait_for_timeout(700)
        check(
            "aviso no papel de afiliado",
            pagina.locator("#createWarning").is_visible(),
        )
        pagina.locator("#createModal .modal-close").first.click()
        pagina.wait_for_timeout(400)
        pagina.locator("[data-open-create='creator']").first.click()
        pagina.wait_for_timeout(700)
        check(
            "aviso no papel de criador",
            pagina.locator("#createWarning").is_visible(),
        )
        pagina.locator("#createModal .modal-close").first.click()
        pagina.wait_for_timeout(400)

        # --------------------------------------------- 8. IP de datacenter -> 404
        print("\n[8] IP de datacenter / VPN / fora do pais -> 404")

        def bloqueia(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body='{"ok":true,"allowed":false,"blocked":true,"reason":"IP_DENIED",'
                '"message":"negado"}',
            )

        pagina.route(f"{API}/signup-guard", bloqueia)
        pagina.goto(f"{SITE}/afiliados/", wait_until="domcontentloaded")
        pagina.wait_for_timeout(4000)
        check("vai para a pagina de erro", "/404.html" in pagina.url, pagina.url)
        check("conteudo do programa nao aparece", not pagina.locator("#createModal").is_visible())
        resposta = pagina.request.get(pagina.url)
        check("resposta HTTP 404 de verdade", resposta.status == 404, str(resposta.status))
        check(
            "pagina de erro tem o conteudo do projeto",
            "vizin" in pagina.locator("body").inner_text().lower(),
        )

        contexto.close()
        browser.close()

    print(f"\n{checks - len(failures)}/{checks} verificacoes passaram")
    if failures:
        print("Falhas:")
        for item in failures:
            print(f"  - {item}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
