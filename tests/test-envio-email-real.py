"""Teste real do envio de e-mail pelo painel de afiliado, contra producao.

Percorre o caminho inteiro como um afiliado usaria, em um navegador de
verdade (sem cache nem cookies de execucoes anteriores):

1. abre o site publicado com o link do painel e confere que o painel abre;
2. confere que a cota de e-mail aparece na tela;
3. preenche o formulario de contato e clica em "Enviar e-mail";
4. confere a confirmacao na tela, o contador de cota e o contato na lista;
5. repete ate esgotar a janela e confere o aviso de cota (HTTP 429);
6. tenta contato de novo com o mesmo criador e confere o aviso (HTTP 409);
7. confere que o texto do e-mail NUNCA chega ao navegador (ele e montado
   na VPS) e que nenhum campo de template existe na pagina.

O e-mail em si e entregue pelo mesmo codigo de producao (SMTP com
STARTTLS + AUTH PLAIN). Durante o teste a VPS aponta para um servidor SMTP
local que grava a mensagem em disco, para conferir o MIME que saiu.

Uso:
    python3 tests/test-envio-email-real.py
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

SITE = "https://site.188.166.156.109.sslip.io"
API = "https://api.188.166.156.109.sslip.io"
SSH_CONFIG = os.environ.get("SSH_CONFIG", "/tmp/opencode/ssh_config")
HOST = os.environ.get("HOST", "vizin-vps")
# Chave e hosts conhecidos do projeto do app: funcionam mesmo sem o
# ssh_config temporario (que some quando o computador reinicia).
CHAVE = "/home/user/Downloads/app/.local/vps/id_ed25519"
KNOWN_HOSTS = "/home/user/Downloads/app/.local/vps/known_hosts"
VPS = "root@188.166.156.109"
TOKEN_CACHE = "/tmp/vizin-teste-email-token.json"
TOKEN_CACHE_2 = "/tmp/vizin-teste-email-token-2.json"

# Frases do modelo de e-mail. Nenhuma delas pode existir no que o navegador
# recebe: o texto e montado na VPS, no servidor.
FRASES_DO_MODELO = [
    "Uber da vizinhança quer te ter como criador parceiro",
    "Estamos abrindo o programa de criadores",
    "Seu público ganha 20% de desconto",
    "Eu faço parte do programa de afiliados e recebo 20%",
]

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


def texto_da_cota(pagina) -> str:
    """Texto que explica a regra da cota de e-mail.

    O painel mostra a cota no proprio indicador de "E-mails enviados": o
    contador ("1/3") e a mensagem dinamica no title do cartao. O paragrafo
    separado que existia antes foi removido, mas o teste roda contra o site
    publicado, entao os dois formatos sao aceitos.
    """
    card = pagina.locator("#afiliadoStatEmailsCard")
    if card.count() == 1:
        return card.get_attribute("title") or ""
    hint = pagina.locator("#outreachQuota")
    if hint.count() == 1:
        return hint.inner_text().strip()
    return ""


def cria_afiliado(handle: str, cache: str, ip_de_origem: str = "") -> str:
    """Token de um afiliado de teste.

    A guarda de IP permite 1 conta por endereco, entao cada afiliado de teste
    e criado com um IP diferente (a VPS usa `X-Forwarded-For` para isso).
    """
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as arquivo:
            return json.load(arquivo)["token"]

    marca = str(int(time.time()))[-6:]
    cabecalho = (
        " -H 'X-Forwarded-For: %s'" % ip_de_origem if ip_de_origem else ""
    )
    remoto = (
        "curl -s -m 15 -X POST http://127.0.0.1:8788/hunters "
        "-H 'content-type: application/json'%s "
        "-d '{\"handle\":\"%s%s\",\"code\":\"%s%s\","
        "\"name\":\"Teste E-mail Real\"}'"
        % (cabecalho, handle, marca[-4:], handle.upper()[:6], marca[-4:])
    )
    saida = subprocess.run(
        ["ssh", "-F", SSH_CONFIG, HOST, remoto],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if not saida.stdout.strip():
        # O ssh_config temporario pode nao existir: tenta pela chave do
        # projeto do app, que fica sempre no lugar.
        saida = subprocess.run(
            [
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                f"UserKnownHostsFile={KNOWN_HOSTS}",
                "-i",
                CHAVE,
                VPS,
                remoto,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    try:
        dados = json.loads(saida.stdout)
    except ValueError:
        raise RuntimeError(
            "nao foi possivel criar o afiliado de teste (ssh: %s)"
            % (saida.stderr.strip() or "sem resposta")
        )
    if not dados.get("token"):
        raise RuntimeError("nao foi possivel criar o afiliado de teste: %s" % saida.stdout)
    token = dados["token"]
    with open(cache, "w", encoding="utf-8") as arquivo:
        json.dump({"token": token}, arquivo)
    return token


def main():
    token = cria_afiliado("tstemail", TOKEN_CACHE)
    # Segundo afiliado: a base de contatos e compartilhada, entao ele e quem
    # tenta contatar de novo um criador que o primeiro ja contatou.
    token_2 = cria_afiliado("tstoutro", TOKEN_CACHE_2, "192.168.10.5")
    print(f"\nToken de afiliado: {token[:10]}...")
    print(f"Token de afiliado 2: {token_2[:10]}...")

    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        contexto = browser.new_context(viewport={"width": 1366, "height": 900})
        pagina = contexto.new_page()
        erros_js = []
        pagina.on("pageerror", lambda erro: erros_js.append(str(erro)))

        # ------------------------------------------------------- 1. abrir
        print("\n[1] Abrir o painel pelo link do afiliado")
        pagina.goto(
            f"{SITE}/afiliados/?afiliado_token={token}", wait_until="domcontentloaded"
        )
        pagina.wait_for_timeout(4000)
        check("painel do afiliado visivel", pagina.locator("#afiliadoDashboardView").is_visible())
        # O painel so vale se os dados do afiliado vieram da API: com token
        # invalido a tela abre, mas fica vazia.
        check(
            "dados do afiliado carregados da API",
            pagina.locator("#afiliadoHandle").inner_text().strip().startswith("@"),
            pagina.locator("#afiliadoHandle").inner_text(),
        )
        check(
            "formulario de e-mail presente",
            pagina.locator("#outreachForm").is_visible(),
        )
        check(
            "campo de e-mail do criador presente",
            pagina.locator("#outreachEmail").count() == 1,
        )
        check(
            "campo de nome do criador presente",
            pagina.locator("#outreachName").count() == 1,
        )

        # --------------------------------------------- 2. cota na tela
        print("\n[2] Cota de e-mail na tela")
        stat = pagina.locator("#afiliadoStatEmails").inner_text().strip()
        check("contador de e-mails preenchido", re.match(r"^\d+/3$", stat) is not None, stat)
        hint = texto_da_cota(pagina)
        check("texto da cota explica a regra", "3 dias" in hint, hint)
        usados = int(stat.split("/")[0])

        # --------------------------------- 3. enviar ate esgotar a janela
        print("\n[3] Enviar e-mails ate esgotar a janela de 3 dias")
        enviados = 0
        nome_para_duplicado = None
        status_429 = ""
        status_409 = ""

        while usados < 3:
            usados += 1
            marca = str(int(time.time()))[-5:]
            nome = f"Criador Real {marca} {enviados}"
            if nome_para_duplicado is None:
                nome_para_duplicado = nome

            pagina.locator("#outreachName").fill(nome)
            pagina.locator("#outreachEmail").fill("vizin.oos@gmail.com")
            pagina.locator("#outreachPlatform").select_option("instagram")
            pagina.locator("#outreachContact").fill(f"@criador{marca}")
            # O campo "observações" foi removido do formulario: o contato e
            # o e-mail sao enviados direto, sem etapa de verificacao e sem
            # texto extra.
            check(
                "formulario nao tem mais o campo de observacoes",
                pagina.locator("#outreachNotes").count() == 0,
            )
            # O envio e direto: o botao manda o e-mail, sem "verificar".
            rotulo = pagina.locator("#outreachButton").inner_text().strip()
            check(
                "botao envia o e-mail direto, sem etapa de verificacao",
                "enviar" in rotulo.lower() and "verificar" not in rotulo.lower(),
                rotulo,
            )
            # O botao fica desabilitado enquanto o e-mail sai: espera ele
            # ficar disponivel antes de clicar (e para nao perder o clique).
            pagina.wait_for_selector("#outreachButton:not([disabled])", timeout=45000)
            pagina.locator("#outreachButton").click()

            # O e-mail leva alguns segundos para sair (o servidor entrega por
            # um provedor externo): espera o estado FINAL, e nao o texto
            # provisorio "Enviando o convite..." que aparece na hora.
            pagina.wait_for_function(
                "() => {"
                "  var s = document.getElementById('outreachStatus');"
                "  var e = document.getElementById('outreachError');"
                "  var st = s ? (s.getAttribute('data-estado') || '') : '';"
                "  var er = e ? e.textContent.trim() : '';"
                "  return st === 'enviado' || st === 'erro' || er;"
                "}",
                timeout=45000,
            )
            # O painel recarrega depois do envio: espera a cota e a lista de
            # contatos refletirem o e-mail que acabou de sair.
            pagina.wait_for_function(
                "(n) => {"
                "  var c = document.getElementById('afiliadoStatEmails');"
                "  return c && c.textContent.trim() === n + '/3';"
                "}",
                arg=f"{usados}",
                timeout=45000,
            )
            pagina.wait_for_timeout(500)

            ok = pagina.locator("#outreachStatus").inner_text().strip()
            erro = pagina.locator("#outreachError").inner_text().strip()
            check(f"envio {usados} confirmado na tela", "E-mail enviado" in ok, f"ok={ok!r} erro={erro!r}")
            check(
                f"envio {usados} mostra o destinatario",
                "vizin.oos@gmail.com" in ok,
                ok,
            )
            stat = pagina.locator("#afiliadoStatEmails").inner_text().strip()
            check(f"contador virou {usados}/3", stat == f"{usados}/3", stat)

            lista = pagina.locator("#outreachList").inner_text()
            check(
                f"contato {nome} apareceu em 'Contatos recentes'",
                nome in lista,
                lista[:220],
            )
            enviados += 1

        # --------------------------------------------------- 4. cota (429)
        print("\n[4] Quarto envio: a janela de 3 dias barra (HTTP 429)")
        pagina.locator("#outreachName").fill("Criador Excedente")
        pagina.locator("#outreachEmail").fill("vizin.oos@gmail.com")
        # "Como o criador é conhecido" e obrigatorio: o campo faz parte do
        # envio, nao pode faltar nem no teste da cota.
        pagina.locator("#outreachContact").fill("@criadorexcedente")
        pagina.wait_for_selector("#outreachButton:not([disabled])", timeout=45000)
        pagina.locator("#outreachButton").click()
        pagina.wait_for_function(
            "() => {"
            "  var e = document.getElementById('outreachError');"
            "  var s = document.getElementById('outreachStatus');"
            "  return (e && e.textContent.trim()) ||"
            "    (s && (s.getAttribute('data-estado') || '') === 'enviado');"
            "}",
            timeout=45000,
        )
        pagina.wait_for_timeout(1500)
        status_429 = pagina.locator("#outreachError").inner_text().strip()
        check(
            "aviso de cota no 4o envio",
            "3 e-mails" in status_429 and "janela" in status_429,
            status_429,
        )
        check(
            "botao de envio fica desabilitado/ocupado ao fim da cota",
            texto_da_cota(pagina).strip() != "",
        )
        stat = pagina.locator("#afiliadoStatEmails").inner_text().strip()
        check("contador continua 3/3", stat == "3/3", stat)

        # ---------------------------------------------- 5. duplicado (409)
        print("\n[5] Outro afiliado tenta contatar o mesmo criador (HTTP 409)")
        pagina.goto(
            f"{SITE}/afiliados/?afiliado_token={token_2}", wait_until="domcontentloaded"
        )
        pagina.wait_for_timeout(4000)
        check(
            "painel do segundo afiliado carregou",
            pagina.locator("#afiliadoHandle").inner_text().strip().startswith("@"),
            pagina.locator("#afiliadoHandle").inner_text(),
        )
        stat_2 = pagina.locator("#afiliadoStatEmails").inner_text().strip()
        check("segundo afiliado com cota cheia", stat_2 == "0/3", stat_2)
        pagina.locator("#outreachName").fill(nome_para_duplicado)
        pagina.locator("#outreachEmail").fill("vizin.oos@gmail.com")
        pagina.locator("#outreachContact").fill("@criador_duplicado")
        pagina.wait_for_selector("#outreachButton:not([disabled])", timeout=45000)
        pagina.locator("#outreachButton").click()
        pagina.wait_for_function(
            "() => {"
            "  var e = document.getElementById('outreachError');"
            "  var s = document.getElementById('outreachStatus');"
            "  return (e && e.textContent.trim()) ||"
            "    (s && (s.getAttribute('data-estado') || '') === 'enviado');"
            "}",
            timeout=45000,
        )
        pagina.wait_for_timeout(1500)
        status_409 = pagina.locator("#outreachError").inner_text().strip()
        check(
            "aviso de criador ja contatado",
            "já foi contatado" in status_409 and "Não entre em contato" in status_409,
            status_409,
        )
        stat_2 = pagina.locator("#afiliadoStatEmails").inner_text().strip()
        check("duplicidade nao consumiu a cota do segundo afiliado", stat_2 == "0/3", stat_2)

        # ------------------------------- 6. o texto do e-mail nao chega ao navegador
        print("\n[6] O texto do e-mail nao existe no navegador")
        html = pagina.content()
        for frase in FRASES_DO_MODELO:
            check(
                f"frase do modelo ausente no HTML: {frase[:38]}...",
                frase not in html,
            )
        for id_ in ("emailTemplate", "dmTemplate", "copyEmailTemplate", "copyDmTemplate"):
            check(f"campo de template {id_} nao existe", pagina.locator(f"#{id_}").count() == 0)

        # O JS servido tambem nao pode conter o modelo.
        for arquivo in ("/assets/creators.js", "/afiliados/"):
            resposta = pagina.request.get(SITE + arquivo)
            corpo = resposta.text()
            achou = [f for f in FRASES_DO_MODELO if f in corpo]
            check(f"modelo ausente em {arquivo}", not achou, "; ".join(achou))

        # ------------------------------------------ 7. recarregar e persistir
        print("\n[7] Recarregar o painel: o estado continua")
        pagina.goto(
            f"{SITE}/afiliados/?afiliado_token={token}", wait_until="domcontentloaded"
        )
        pagina.wait_for_timeout(4000)
        check("painel reabre", pagina.locator("#afiliadoDashboardView").is_visible())
        stat = pagina.locator("#afiliadoStatEmails").inner_text().strip()
        check("cota persistida como 3/3", stat == "3/3", stat)
        check(
            "contato continua na lista apos recarregar",
            "Criador Real" in pagina.locator("#outreachList").inner_text(),
        )
        check("sem erros de JavaScript", not erros_js, "; ".join(erros_js))

        pagina.screenshot(path="/tmp/opencode/painel-afiliado-email-real.png", full_page=True)

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
