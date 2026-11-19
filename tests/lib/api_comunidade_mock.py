"""API da Comunidade em memória, para testes locais.

A API real vive na VPS e não está acessível de toda máquina (nem de quem
desenvolve offline). Este mock implementa o mesmo contrato HTTP usado por
`assets/comunidade.js`, com os mesmos caminhos, códigos de status e formato
de resposta, para que a jornada completa do usuário (criar conta, publicar
proposta, votar, comentar, sair) possa ser testada sem rede.

Uso:
    from lib.api_comunidade_mock import servir_api
    httpd, base = servir_api(8791)
"""

from __future__ import annotations

import hashlib
import hmac
import http.server
import json
import secrets
import socketserver
import threading
import time

AGORA = lambda: time.time()  # noqa: E731

# tag -> rotulo usado pelo front
TAGS = {"ideia": "ideia", "melhoria": "melhoria", "problema": "problema"}

# Token de administracao aceito pelo mock (o painel usa o mesmo contrato).
TOKEN_ADMIN = "token-de-admin"


class Estado:
    """Estado compartilhado do mock (usuários, propostas, votos)."""

    def __init__(self) -> None:
        self.usuarios: dict[str, dict] = {}
        self.posts: dict[str, dict] = {}
        self.comentarios: dict[str, dict] = {}
        self.votos: dict[str, int] = {}
        self.sessoes: dict[str, str] = {}  # token -> username
        self.seq = 0
        self.criar_admin("maidsupremacy", "maid-supremacia")

    def novo_id(self, prefixo: str) -> str:
        self.seq += 1
        return f"{prefixo}_{self.seq}_{secrets.token_hex(4)}"

    def criar_admin(self, username: str, senha: str) -> None:
        """Conta de administracao usada pelo painel (mesma da producao)."""
        salt = secrets.token_hex(8)
        self.usuarios[username.lower()] = {
            "username": username,
            "salt": salt,
            "hash": _hash_senha(senha, salt),
            "admin": True,
        }

    def usuario_por_token(self, token: str | None):
        if not token:
            return None
        # Token fixo de administracao, usado pelo painel e pelos testes.
        if token == TOKEN_ADMIN:
            return self.usuarios.get("maidsupremacy")
        username = self.sessoes.get(token)
        if not username:
            return None
        return self.usuarios.get(username)

    def posts_ordenados(self, status: str, sort: str):
        posts = [p for p in self.posts.values() if p["status"] == status]
        if sort == "top":
            posts.sort(key=lambda p: (-p["score"], -p["created_at"]))
        else:
            posts.sort(key=lambda p: -p["created_at"])
        return posts


def _hash_senha(senha: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 120_000).hex()


class Handler(http.server.BaseHTTPRequestHandler):
    estado: Estado = Estado()

    # ------------------------------------------------------------- infra --

    def log_message(self, *args):  # noqa: D102
        pass

    def _json(self, status: int, dados) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(corpo)))
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-headers", "authorization, content-type")
        self.send_header("access-control-allow-methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(corpo)

    def _erro(self, status: int, mensagem: str) -> None:
        self._json(status, {"error": mensagem})

    def _corpo(self):
        length = int(self.headers.get("content-length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _token(self):
        auth = self.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return None

    def _usuario(self):
        return self.estado.usuario_por_token(self._token())

    def _exigir_login(self):
        usuario = self._usuario()
        if usuario is None:
            self._erro(401, "faça login para continuar")
            return None
        return usuario

    def do_OPTIONS(self):  # noqa: N802
        self._json(204, {})

    # ------------------------------------------------------------- GET ----

    def do_GET(self):  # noqa: N802
        caminho = self.path.split("?")[0].rstrip("/") or "/"
        consulta = self.path.split("?")[1] if "?" in self.path else ""
        params = dict(p.split("=", 1) for p in consulta.split("&") if "=" in p)

        if caminho == "/forum/status":
            abertos = len([p for p in self.estado.posts.values() if p["status"] == "open"])
            feitas = len([p for p in self.estado.posts.values() if p["status"] == "done"])
            return self._json(200, {"open_count": abertos, "done_count": feitas})

        if caminho == "/forum/session":
            usuario = self._usuario()
            if usuario is None:
                return self._erro(401, "sessão expirada")
            return self._json(200, {"username": usuario["username"], "admin": usuario["admin"]})

        if caminho == "/forum/posts":
            status = params.get("status", "open")
            sort = params.get("sort", "top")
            usuario = self._usuario()
            lista = self.estado.posts_ordenados(status, sort)
            serializados = [self._serializar(p, usuario) for p in lista]
            return self._json(200, {"total": len(serializados), "posts": serializados})

        if caminho.startswith("/forum/posts/"):
            post_id = caminho.split("/forum/posts/", 1)[1]
            post = self.estado.posts.get(post_id)
            if not post:
                return self._erro(404, "proposta não encontrada")
            usuario = self._usuario()
            # O detalhe vem embrulhado: { post, comments } (contrato do front).
            dados = self._serializar(post, usuario)
            comentarios = [
                self._serializar_comentario(c, usuario)
                for c in self.estado.comentarios.values()
                if c["post_id"] == post_id
            ]
            return self._json(200, {"post": dados, "comments": comentarios})

        return self._erro(404, "rota não encontrada")

    # ------------------------------------------------------------- POST ---

    def do_POST(self):  # noqa: N802
        caminho = self.path.split("?")[0].rstrip("/") or "/"
        dados = self._corpo()

        if caminho in ("/forum/register", "/forum/login"):
            return self._autenticar(caminho, dados)

        if caminho == "/forum/logout":
            token = self._token()
            if token:
                self.estado.sessoes.pop(token, None)
            return self._json(200, {"ok": True})

        if caminho == "/forum/admin/status":
            usuario = self._usuario()
            if usuario is None or not usuario["admin"]:
                return self._erro(403, "somente administracao pode marcar propostas")
            post_id = dados.get("post_id")
            post = self.estado.posts.get(post_id)
            if not post:
                return self._erro(404, "proposta não encontrada")
            status = dados.get("status")
            if status not in ("open", "done"):
                return self._erro(400, "status invalido")
            post["status"] = status
            post["status_note"] = (dados.get("note") or "").strip()
            return self._json(200, {"ok": True, "post_id": post_id, "status": status})

        if caminho == "/forum/posts":
            usuario = self._exigir_login()
            if usuario is None:
                return None
            titulo = (dados.get("title") or "").strip()
            texto = (dados.get("body") or "").strip()
            tag = dados.get("tag") or "ideia"
            if len(titulo) < 3:
                return self._erro(400, "o título é muito curto")
            if len(texto) < 10:
                return self._erro(400, "descreva a proposta com mais detalhes")
            post_id = self.estado.novo_id("post")
            self.estado.posts[post_id] = {
                "id": post_id,
                "title": titulo,
                "body": texto,
                "tag": tag if tag in TAGS else "ideia",
                "status": "open",
                "status_note": "",
                "username": usuario["username"],
                "admin": usuario["admin"],
                "created_at": AGORA(),
                "score": 0,
            }
            return self._json(200, {"id": post_id, "ok": True})

        if caminho.endswith("/vote") and "/forum/posts/" in caminho:
            usuario = self._exigir_login()
            if usuario is None:
                return None
            post_id = caminho.split("/forum/posts/", 1)[1].split("/")[0]
            post = self.estado.posts.get(post_id)
            if not post:
                return self._erro(404, "proposta não encontrada")
            valor = dados.get("value")
            if valor not in (1, -1):
                return self._erro(400, "voto inválido")
            chave = f"{usuario['username']}:{post_id}"
            anterior = self.estado.votos.get(chave)
            if anterior == valor:
                # clicar de novo desmarca
                del self.estado.votos[chave]
                post["score"] -= valor
                meu = 0
            else:
                if anterior:
                    post["score"] -= anterior
                self.estado.votos[chave] = valor
                post["score"] += valor
                meu = valor
            return self._json(200, {"score": post["score"], "my_vote": meu})

        if caminho.endswith("/comments") and "/forum/posts/" in caminho:
            usuario = self._exigir_login()
            if usuario is None:
                return None
            post_id = caminho.split("/forum/posts/", 1)[1].split("/")[0]
            if post_id not in self.estado.posts:
                return self._erro(404, "proposta não encontrada")
            texto = (dados.get("body") or "").strip()
            if len(texto) < 2:
                return self._erro(400, "comentário vazio")
            comentario_id = self.estado.novo_id("c")
            self.estado.comentarios[comentario_id] = {
                "id": comentario_id,
                "post_id": post_id,
                "body": texto,
                "username": usuario["username"],
                "admin": usuario["admin"],
                "created_at": AGORA(),
            }
            return self._json(200, {"id": comentario_id, "ok": True})

        return self._erro(404, "rota não encontrada")

    # ------------------------------------------------------------ DELETE --

    def do_DELETE(self):  # noqa: N802
        caminho = self.path.split("?")[0].rstrip("/") or "/"
        usuario = self._exigir_login()
        if usuario is None:
            return None

        if caminho.startswith("/forum/comments/"):
            comentario_id = caminho.split("/forum/comments/", 1)[1]
            comentario = self.estado.comentarios.get(comentario_id)
            if not comentario:
                return self._erro(404, "comentário não encontrado")
            if comentario["username"] != usuario["username"] and not usuario["admin"]:
                return self._erro(403, "você só apaga o que é seu")
            del self.estado.comentarios[comentario_id]
            return self._json(200, {"ok": True})

        if caminho.startswith("/forum/posts/"):
            post_id = caminho.split("/forum/posts/", 1)[1]
            post = self.estado.posts.get(post_id)
            if not post:
                return self._erro(404, "proposta não encontrada")
            if post["username"] != usuario["username"] and not usuario["admin"]:
                return self._erro(403, "você só apaga o que é seu")
            del self.estado.posts[post_id]
            for comentario_id in [c for c, v in self.estado.comentarios.items() if v["post_id"] == post_id]:
                del self.estado.comentarios[comentario_id]
            return self._json(200, {"ok": True})

        return self._erro(404, "rota não encontrada")

    # --------------------------------------------------------- auxiliares --

    def _autenticar(self, caminho: str, dados):
        username = (dados.get("username") or "").strip()
        senha = dados.get("password") or ""

        if caminho == "/forum/register":
            if not (3 <= len(username) <= 20):
                return self._erro(400, "apelido deve ter entre 3 e 20 caracteres")
            if len(senha) < 8:
                return self._erro(400, "a senha precisa de pelo menos 8 caracteres")
            if username.lower() in self.estado.usuarios:
                return self._erro(409, "esse apelido já está em uso")
            salt = secrets.token_hex(8)
            self.estado.usuarios[username.lower()] = {
                "username": username,
                "salt": salt,
                "hash": _hash_senha(senha, salt),
                "admin": False,
            }
        else:
            usuario = self.estado.usuarios.get(username.lower())
            if not usuario:
                return self._erro(401, "apelido ou senha incorretos")
            esperado = _hash_senha(senha, usuario["salt"])
            if not hmac.compare_digest(esperado, usuario["hash"]):
                return self._erro(401, "apelido ou senha incorretos")

        token = secrets.token_urlsafe(24)
        self.estado.sessoes[token] = username.lower()
        return self._json(
            200,
            {"token": token, "username": username, "admin": self.estado.usuarios[username.lower()]["admin"]},
        )

    def _serializar(self, post: dict, usuario) -> dict:
        comentario_count = len(
            [c for c in self.estado.comentarios.values() if c["post_id"] == post["id"]]
        )
        meu = 0
        if usuario:
            meu = self.estado.votos.get(f"{usuario['username'].lower()}:{post['id']}", 0)
        return {
            "id": post["id"],
            "title": post["title"],
            "body": post["body"],
            "tag": post["tag"],
            "status": post["status"],
            "status_note": post["status_note"],
            "username": post["username"],
            "admin": post["admin"],
            "created_at": post["created_at"],
            "score": post["score"],
            "my_vote": meu,
            "mine": bool(usuario and post["username"].lower() == usuario["username"].lower()),
            "comment_count": comentario_count,
        }

    def _serializar_comentario(self, comentario: dict, usuario) -> dict:
        return {
            "id": comentario["id"],
            "post_id": comentario["post_id"],
            "body": comentario["body"],
            "username": comentario["username"],
            "admin": comentario["admin"],
            "created_at": comentario["created_at"],
            "mine": bool(usuario and comentario["username"].lower() == usuario["username"].lower()),
        }


def servir_api(port: int = 8791, estado: Estado | None = None):
    """Sobe a API mock na porta e devolve (httpd, base_url)."""

    class MockHandler(Handler):
        pass

    MockHandler.estado = estado or Estado()
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), MockHandler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}"
