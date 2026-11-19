"""Roda a suite do site (Playwright) com um servidor local proprio.

Os testes do site assumem um servidor em http://localhost:8099 (rotas sem
extensao, como /painel e /membros). Este runner sobe esse servidor e
executa cada teste, permitindo rodar tudo com um comando:

    python3 site/tests/rodar-suite.py

Testes que dependem da API de producao ou de rede externa sao pulados com
motivo explicito (nao contam como falha silenciosa).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))

from lib.servidor_site import servir_site  # noqa: E402

# (teste, rotas que o servidor precisa servir)
SUITE = [
    ("test-breadcrumb.py", {"/": "index.html"}),
    ("test-puxar-fila.py", {"/": "index.html"}),
    ("test-jornada-home.py", {"/": "index.html"}),
    ("test-guia-acordeao.py", {"/membros": "membros.html"}),
    ("test-guard-ip.py", {"/": "index.html", "/membros": "membros.html", "/404.html": "404.html"}),
    ("test-layout-painel.py", {"/painel": "painel.html"}),
    ("test-painel-publico.py", {"/painel": "painel.html"}),
    ("test-comunidade-local.py", {}),
    ("test-jornada-programa-local.py", {}),
    ("test-layout-afiliado.py", {"/membros": "membros.html"}),
    ("test-integridade-site.py", {}),
    ("test-css-saude.py", {}),
    ("alinhamento-paginas.py", {}),
    ("auditoria-mobile.py", {}),
    ("test-links-painel.py", {}),
]

# Precisa da API real ou de rede externa: nao rodam local.
PULADOS = {
    "test-painel-afiliado.py": "cria conta na API (guarda de IP bloqueia IP de datacenter)",
    "test-painel-producao.py": "aponta para a API de producao",
    "test-jornada-afiliado.py": "cria conta na API (guarda de IP bloqueia IP de datacenter)",
    "test-envio-email-real.py": "envia e-mail de verdade",
}

# O guia completo saiu de /membros (a pagina foi reescrita) e o JS/CSS
# morto foi removido: o teste agora confere a estrutura nova e passa.
REGRESSAO_CONHECIDA: dict[str, str] = {}


def porta_livre() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _porta_ocupada(porta: int) -> bool:
    """A porta ainda esta em uso por outro processo?"""
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", porta)) == 0


def main() -> int:
    porta = porta_livre()
    httpd, base = servir_site(porta, {})
    time.sleep(0.5)
    env = {**os.environ, "SITE_BASE": base, "VIZIN_APP_DIR": str(TESTS_DIR.parent.parent)}
    print(f"Servidor do site: {base}\n")

    # API do programa de parceiros em memoria: o teste de layout do painel
    # precisa de uma conta real para conferir a geometria do painel.
    sys.path.insert(0, str(TESTS_DIR / "lib"))
    from api_programa_mock import servir_api

    porta_api = porta_livre()
    httpd_api, api_base = servir_api(porta_api)
    env["VIZIN_API"] = api_base
    print(f"API do programa (mock): {api_base}\n")

    falhas: list[str] = []
    # Os testes do site assumem http://localhost:8099 (estao fixos no codigo
    # deles). Por isso o runner usa essa porta: um servidor na porta que os
    # testes esperam, sem depender de nenhum processo externo. Se outro
    # processo estiver com ela, o runner usa uma porta livre e avisa.
    porta = 8099
    if _porta_ocupada(porta):
        porta = porta_livre()
        print(f"Atencao: 8099 esta em uso; os testes rodarao na porta {porta}.\n")
    for arquivo, rotas in SUITE:
        # Cada teste roda com seu proprio servidor: assim as rotas sem
        # extensao (/painel, /membros) funcionam como em producao.
        httpd, base = servir_site(porta, rotas)
        time.sleep(0.4)
        env["SITE_BASE"] = base
        print(f"== {arquivo}")
        # A URL do site vai como argumento (e no ambiente): os testes leem
        # de um dos dois, e alguns so aceitam argumento.
        comando = [sys.executable, str(TESTS_DIR / arquivo), base]
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            cwd=str(TESTS_DIR),
        )
        saida = (resultado.stdout or "") + (resultado.stderr or "")
        if resultado.returncode == 0:
            print("   OK")
        else:
            print(saida[-1500:])
            falhas.append(arquivo)
        try:
            httpd.shutdown()
            httpd.server_close()
        except Exception:  # noqa: BLE001
            pass
        # A porta precisa estar livre antes do proximo teste: o SO segura a
        # conexao por alguns segundos depois do servidor fechar.
        for _ in range(40):
            if not _porta_ocupada(porta):
                break
            time.sleep(0.25)
        time.sleep(0.3)

    for arquivo, motivo in PULADOS.items():
        print(f"== {arquivo}: PULADO ({motivo})")

    for arquivo, motivo in REGRESSAO_CONHECIDA.items():
        if arquivo in falhas:
            print(f"== {arquivo}: REGRESSAO CONHECIDA ({motivo})")
            falhas.remove(arquivo)

    # Testes de fora do navegador (Node): payload PIX e painel publico
    # contra a VPS local.
    for arquivo in ["tests/pix.test.js", "tests/painel.test.mjs"]:
        print(f"== {arquivo}")
        resultado = subprocess.run(
            ["node", "--test", str(TESTS_DIR.parent / arquivo)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(TESTS_DIR.parent),
        )
        if resultado.returncode == 0:
            print("   OK")
        else:
            print(((resultado.stdout or "") + (resultado.stderr or ""))[-1500:])
            falhas.append(arquivo)

    # Integridade estatica: paginas, ancoras, assets, SVG, CSS e JS.
    print("== tools/check-site.py")
    resultado = subprocess.run(
        [sys.executable, str(TESTS_DIR.parent / "tools" / "check-site.py")],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(TESTS_DIR.parent),
    )
    if resultado.returncode == 0:
        print("   OK")
    else:
        print((resultado.stdout or "") + (resultado.stderr or ""))
        falhas.append("check-site.py")

    httpd.shutdown()
    try:
        httpd_api.shutdown()
    except Exception:  # noqa: BLE001
        pass
    print()
    if falhas:
        print(f"Falharam: {', '.join(falhas)}")
        return 1
    print("Suite do site verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
