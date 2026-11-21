"""Servidor estático local com rotas sem extensão.

O site em produção é servido por CDN/Caddy, onde `/painel` resolve
`painel.html`. O `http.server` do Python não faz isso, então os testes que
dependem de rotas limpas sobem o próprio servidor por aqui.

Uso:
    from lib.servidor_site import servir_site
    httpd, base = servir_site(PORT, {"/painel": "painel.html"})
"""

import http.server
import os
import socket
import socketserver
import threading

# tests/lib/servidor_site.py -> site/
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Rotas sem extensão -> arquivo real.
# Espelha o rewrite de producao (.htaccess / _redirects): toda URL publica
# sem extensao resolve para o .html correspondente.
PAGES = {
    "/": "index.html",
    "/membros": "membros.html",
    "/comunidade": "comunidade.html",
    "/documento": "documento.html",
    "/download": "download.html",
    "/licenca": "licenca.html",
    "/moderacao": "moderacao.html",
    "/painel": "painel.html",
    "/privacidade": "privacidade.html",
    "/termos": "termos.html",
}


class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, format, *args):
        pass

    def translate_path(self, path):
        clean = path.split("?")[0].split("#")[0]
        if clean in PAGES:
            clean = "/" + PAGES[clean]
        return super().translate_path(clean)


def servir_site(port, pages=None):
    """Sobe o site local na porta e devolve (httpd, base_url)."""

    class Handler(_Handler):
        def translate_path(self, path):
            clean = path.split("?")[0].split("#")[0]
            # Aceita a rota com barra final ("/membros/") como a sem barra.
            if clean.endswith("/") and clean[:-1] in PAGES:
                clean = clean[:-1]
            if pages and clean in pages:
                clean = "/" + pages[clean]
            elif clean in PAGES:
                clean = "/" + PAGES[clean]
            return http.server.SimpleHTTPRequestHandler.translate_path(self, clean)

    socketserver.TCPServer.allow_reuse_address = True

    class DualStackServer(socketserver.ThreadingTCPServer):
        """Escuta em IPv4 e IPv6 (localhost pode resolver para qualquer um)."""

        address_family = socket.AF_INET6

        def server_bind(self):
            try:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except OSError:
                pass
            return super().server_bind()

    try:
        httpd = DualStackServer(("::", port), Handler)
    except OSError:
        httpd = socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}"
