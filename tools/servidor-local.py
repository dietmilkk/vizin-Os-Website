#!/usr/bin/env python3
"""Servidor local para os testes do site (com threads).

O `python3 -m http.server` e single-threaded e trava quando o navegador
mantem conexao aberta (keep-alive), o que derruba a suite de Playwright.
Este servidor usa `ThreadingHTTPServer`: cada conexao ganha sua thread.

Uso:
    python3 tools/servidor-local.py [raiz] [porta]

Padroes: raiz = o proprio repositorio, porta = 8099.
Exemplo:
    python3 tools/servidor-local.py /home/user/Downloads/site 8099
"""
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

raiz_padrao = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root = sys.argv[1] if len(sys.argv) > 1 else raiz_padrao
porta = int(sys.argv[2]) if len(sys.argv) > 2 else 8099


class Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, formato, *args):  # silencia o log de cada requisicao
        pass


if __name__ == "__main__":
    handler = partial(Handler, directory=root)
    with Servidor(("127.0.0.1", porta), handler) as srv:
        print(f"site local em http://127.0.0.1:{porta} (raiz: {root})")
        srv.serve_forever()
