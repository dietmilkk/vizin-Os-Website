"""Roda a jornada completa da Comunidade sem depender da VPS.

Sobe uma API da Comunidade em memoria (tests/lib/api_comunidade_mock.py),
sobe o site local com as rotas reais e executa tests/test-comunidade.py
contra ambos. Serve para desenvolvimento offline e para conferir, a cada
mudanca no front, que o caminho do usuario continua inteiro:

  criar conta -> publicar proposta -> ordenar -> votar -> comentar ->
  marcar como implementada -> sair -> entrar como administracao.

Uso:
    python3 site/tests/test-comunidade-local.py
"""

from __future__ import annotations

import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tests"))

from lib.api_comunidade_mock import servir_api  # noqa: E402

API_PORTA = 8791
SITE_PORTA = 8901


def main() -> int:
    httpd_api, api_base = servir_api(API_PORTA)
    print(f"API da Comunidade (mock) em {api_base}")

    comando = [
        sys.executable,
        os.path.join(RAIZ, "tests", "test-comunidade.py"),
        "--api",
        api_base,
        "--port",
        str(SITE_PORTA),
    ]
    try:
        resultado = subprocess.run(comando, cwd=RAIZ, check=False)
        codigo = resultado.returncode
    finally:
        httpd_api.shutdown()

    if codigo == 0:
        print("Comunidade: tudo certo no navegador de verdade.")
    else:
        print("Comunidade: FALHOU (veja o relatorio acima).")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
