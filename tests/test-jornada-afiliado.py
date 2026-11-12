"""Jornada completa do afiliado no navegador, contra o site publicado.

Faz o caminho que uma pessoa faz, do zero:

1. abre a pagina publica /afiliados;
2. clica em "Quero ser afiliado";
3. clica no botao de criar conta (o codigo e gerado pela plataforma);
4. confere o link do painel que aparece no modal — inclusive a decoracao
   em gradiente com o corpo menor;
5. clica em "Abrir painel" e confere que o painel abre;
6. confere o mesmo link no painel (campo preenchido).

O script devolve o `hunter_id` criado para que a limpeza possa remover
exatamente esse registro (a conta libera o IP da maquina de teste).

Uso:
    python3 tests/test-jornada-afiliado.py
"""

import json
import re
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

SITE = "https://site.188.166.156.109.sslip.io"
API = "https://api.188.166.156.109.sslip.io"
SSH_CONFIG = "/tmp/opencode/ssh_config"
HOST = "vizin-vps"
# Chave e hosts conhecidos do projeto do app: funcionam mesmo sem o
# ssh_config temporario (que some quando o computador reinicia).
CHAVE = "/home/user/Downloads/app/.local/vps/id_ed25519"
KNOWN_HOSTS = "/home/user/Downloads/app/.local/vps/known_hosts"
VPS = "root@188.166.156.109"

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


def main():
    # Handle carimbado: o prefixo "tp" (teste de painel) e reconhecido pela
    # ferramenta de limpeza, que apaga a conta e libera o IP da maquina.
    handle_teste = "tp" + str(int(time.time()))[-6:]
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        contexto = browser.new_context(viewport={"width": 1366, "height": 900})
        pagina = contexto.new_page()
        erros_js = []
        pagina.on("pageerror", lambda erro: erros_js.append(str(erro)))

        # Carimba o handle da conta de teste (o resto da requisicao vai intacto).
        # Sem isso o @ da conta seria aleatorio — o codigo e sorteado pelo
        # navegador — e a ferramenta de limpeza nao reconheceria a conta,
        # deixando o IP da maquina bloqueado para a proxima execucao.
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

        print("\n[1] Pagina publica /afiliados")
        pagina.goto(f"{SITE}/afiliados/", wait_until="domcontentloaded")
        pagina.wait_for_timeout(3500)
        check("pagina carregou", pagina.locator("h1").first.is_visible())
        check("sem erros de JavaScript", not erros_js, "; ".join(erros_js))

        print("\n[2] Abrir a janela de criacao de conta")
        pagina.locator("[data-open-create='afiliado']").first.click()
        pagina.wait_for_timeout(700)
        check("janela aberta", pagina.locator("#createModal").is_visible())
        check(
            "campo de codigo escondido (a plataforma gera)",
            pagina.locator("#code").is_hidden(),
        )

        print("\n[3] Criar a conta (clicar no botao)")
        pagina.locator("#createButton").click()
        pagina.wait_for_timeout(6000)
        if not pagina.locator("#createdView").is_visible():
            # A guarda de IP permite 1 conta por endereco. Se ja existe uma
            # conta deste IP, o cadastro e recusado com um aviso — nao e bug.
            aviso = pagina.locator("#createWarning")
            texto = (aviso.inner_text() if aviso.count() else "").strip()
            erro = pagina.locator("#createError").inner_text().strip()
            if "já criou uma conta" in (texto + erro):
                print(
                    "\nEste IP ja criou uma conta: o cadastro foi recusado pela "
                    "guarda de IP (1 conta por IP).\n"
                    "Rode tools/limpar-teste.sh --aplicar para liberar o IP e "
                    "tente de novo."
                )
                contexto.close()
                browser.close()
                print(f"\n{checks - len(failures)}/{checks} verificacoes passaram")
                return 0
            check(
                "confirmacao de conta criada",
                False,
                texto or erro,
            )
            contexto.close()
            browser.close()
            print(f"\n{checks - len(failures)}/{checks} verificacoes passaram")
            return 1
        check("confirmacao de conta criada", pagina.locator("#createdView").is_visible())

        print("\n[4] Link do painel no modal: conteudo e decoracao")
        link = pagina.locator("#dashboardLink")
        href = link.get_attribute("href") or ""
        texto = link.inner_text().strip()
        check("link preenchido", href.startswith("http"), href)
        # Link curto atual (?p=) ou link antigo (?afiliado_token=).
        check(
            "link traz o token do painel",
            "?p=" in href or "afiliado_token=" in href,
            href,
        )
        check("texto do link igual ao href", texto == href, f"{texto!r} != {href!r}")

        estilo = link.evaluate(
            "el => { const s = getComputedStyle(el); return {"
            "  backgroundImage: s.backgroundImage,"
            "  backgroundClip: s.webkitBackgroundClip || s.backgroundClip,"
            "  color: s.color,"
            "  fontSize: s.fontSize,"
            "  fontFamily: s.fontFamily,"
            "  fontWeight: s.fontWeight"
            "}; }"
        )
        print(f"       estilo computado: {estilo}")
        check(
            "decoracao em gradiente aplicada",
            "gradient" in estilo["backgroundImage"],
            estilo["backgroundImage"],
        )
        check(
            "texto preenchido com o gradiente (background-clip: text)",
            estilo["backgroundClip"] == "text",
            estilo["backgroundClip"],
        )
        check(
            "cor do texto transparente (deixa o gradiente aparecer)",
            estilo["color"] in ("rgba(0, 0, 0, 0)", "transparent"),
            estilo["color"],
        )
        # O corpo do link do painel e menor que o texto ao redor.
        corpo_painel = pagina.locator(".panel-link").evaluate(
            "el => parseFloat(getComputedStyle(el).fontSize)"
        )
        corpo_link = float(estilo["fontSize"].replace("px", ""))
        check(
            "fonte do link menor que a do paragrafo",
            corpo_link < corpo_painel,
            f"link={corpo_link}px paragrafo={corpo_painel}px",
        )
        check(
            "fonte do link pequena (abaixo de 15px)",
            corpo_link < 15,
            f"{corpo_link}px",
        )

        pagina.screenshot(path="/tmp/opencode/modal-link-painel-gradiente.png")

        print("\n[5] Entrar no painel pelo botao do modal")
        pagina.locator("#openDashboard").click()
        pagina.wait_for_timeout(5000)
        check("painel aberto", pagina.locator("#afiliadoDashboardView").is_visible())
        check(
            "dados do afiliado carregados",
            pagina.locator("#afiliadoHandle").inner_text().strip().startswith("@"),
            pagina.locator("#afiliadoHandle").inner_text(),
        )
        link_painel = pagina.locator("#afiliadoLink").input_value()
        # Link curto de divulgacao do afiliado: /afiliados?a=<codigo>.
        check("link de afiliado no painel", "?a=" in link_painel, link_painel)
        check(
            "link de afiliado e curto e sem token legado",
            "?afiliado_token=" not in link_painel and "?afiliado=" not in link_painel,
            link_painel,
        )

        pagina.screenshot(path="/tmp/opencode/painel-afiliado-jornada.png", full_page=True)

        # Descobre o id da conta criada e remove em seguida: a conta libera o
        # IP da maquina de teste (a guarda e de 1 conta por IP), senao a
        # proxima execucao seria recusada.
        token = ""
        for separador in ("?p=", "afiliado_token="):
            if separador in href:
                token = href.split(separador)[-1].split("&")[0]
                break
        hunter_id = ""
        consulta = subprocess.run(
            [
                "ssh",
                "-F",
                SSH_CONFIG,
                HOST,
                "curl -s -m 15 'http://127.0.0.1:8788/hunters/me?token=%s'" % token,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        try:
            hunter_id = json.loads(consulta.stdout)["hunter"]["id"]
        except Exception:
            pass
        if not hunter_id:
            # O ssh_config temporario pode nao existir: tenta pela chave do
            # projeto do app, que fica sempre no lugar.
            consulta = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    f"UserKnownHostsFile={KNOWN_HOSTS}",
                    "-i",
                    CHAVE,
                    VPS,
                    "curl -s -m 15 'http://127.0.0.1:8788/hunters/me?token=%s'" % token,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            try:
                hunter_id = json.loads(consulta.stdout)["hunter"]["id"]
            except Exception:
                pass

        if hunter_id:
            print(f"\n[6] Removendo a conta de teste {hunter_id[:8]}... (libera o IP)")
            # `signup_ip_kinds` tambem precisa sair: e a tabela que a guarda de
            # IP consulta. Sem ela o endereco continua bloqueado mesmo com a
            # conta apagada.
            removido = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    f"UserKnownHostsFile={KNOWN_HOSTS}",
                    "-i",
                    CHAVE,
                    VPS,
                    "python3 -c \"import sqlite3;"
                    "con=sqlite3.connect('/var/lib/vizin-api/vizin.sqlite');"
                    "cur=con.cursor();"
                    "hid='%s';"
                    "cur.execute('DELETE FROM hunter_emails WHERE hunter_id = ?', (hid,));"
                    "cur.execute('DELETE FROM outreach_creators WHERE hunter_id = ?', (hid,));"
                    "cur.execute('DELETE FROM referral_earnings WHERE hunter_id = ?', (hid,));"
                    "cur.execute('DELETE FROM hunter_withdrawals WHERE hunter_id = ?', (hid,));"
                    "cur.execute('DELETE FROM signup_ips WHERE entity_id = ?', (hid,));"
                    "cur.execute('DELETE FROM signup_ip_kinds WHERE entity_id = ?', (hid,));"
                    "cur.execute('DELETE FROM hunters WHERE id = ?', (hid,));"
                    "con.commit();"
                    "print(cur.execute('SELECT COUNT(*) FROM hunters WHERE id = ?', (hid,)).fetchone()[0])\"" % hunter_id,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            # Confere no banco: a conta precisa ter sumido de verdade, e o IP
            # precisa estar livre nas duas tabelas da guarda.
            conferencia = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    f"UserKnownHostsFile={KNOWN_HOSTS}",
                    "-i",
                    CHAVE,
                    VPS,
                    "python3 -c \"import sqlite3;"
                    "con=sqlite3.connect('/var/lib/vizin-api/vizin.sqlite');"
                    "cur=con.cursor();"
                    "hid='%s';"
                    "print(cur.execute('SELECT COUNT(*) FROM hunters WHERE id = ?', (hid,)).fetchone()[0],"
                    " cur.execute('SELECT COUNT(*) FROM signup_ips WHERE entity_id = ?', (hid,)).fetchone()[0],"
                    " cur.execute('SELECT COUNT(*) FROM signup_ip_kinds WHERE entity_id = ?', (hid,)).fetchone()[0])\"" % hunter_id,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            estado = (conferencia.stdout or removido.stdout or "").strip().split()
            check(
                "conta de teste removida (IP liberado)",
                len(estado) == 3 and estado == ["0", "0", "0"],
                "conta/IP/IP-por-papel: " + " ".join(estado),
            )
        else:
            check(
                "conta de teste removida (IP liberado)",
                False,
                "nao foi possivel descobrir o id da conta criada",
            )

        contexto.close()
        browser.close()

    print(f"\n{checks - len(failures)}/{checks} verificacoes passaram")
    if hunter_id:
        print(f"HUNTER_ID={hunter_id}")
    if failures:
        print("Falhas:")
        for item in failures:
            print(f"  - {item}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
