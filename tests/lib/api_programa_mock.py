"""API do programa de parceiros (criadores e afiliados) em memoria.

A API real vive na VPS. Este mock implementa o mesmo contrato HTTP usado
por `assets/creators.js`, com os mesmos caminhos, codigos de status e
formatos de resposta, para que a jornada completa do usuario (criar
conta de criador e de afiliado, abrir o painel, ver os numeros, sacar)
possa ser testada sem rede e sem criar registro na producao.

Uso:
    from lib.api_programa_mock import servir_api
    httpd, base = servir_api(8792)
"""

from __future__ import annotations

import http.server
import json
import re
import secrets
import socketserver
import threading
import time

AGORA = lambda: time.time()  # noqa: E731

# Token usado pelo painel/admin nos testes.
TOKEN_ADMIN = "token-de-admin"

CPF_TESTE = "52998224725"
EMAIL_TESTE = "ana@example.com"


class Estado:
    """Estado compartilhado do mock (contas, indicacoes, saques)."""

    def __init__(self) -> None:
        self.criadores: dict[str, dict] = {}   # token -> conta
        self.afiliados: dict[str, dict] = {}   # token -> conta
        self.por_code: dict[str, str] = {}     # code -> token
        self.contatos: dict[str, list[dict]] = {}  # token do afiliado -> contatos
        self.saques: dict[str, list[dict]] = {}    # token -> saques
        self.seq = 0

    def novo_id(self, prefixo: str) -> str:
        self.seq += 1
        return f"{prefixo}_{self.seq}_{secrets.token_hex(4)}"

    def conta_por_token(self, token: str | None):
        if not token:
            return None
        return self.criadores.get(token) or self.afiliados.get(token)


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

    def _erro(self, status: int, mensagem: str, extra: dict | None = None) -> None:
        dados = {"error": mensagem}
        if extra:
            dados.update(extra)
        self._json(status, dados)

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
        # A VPS aceita o token por header E por query (transicao): o front
        # usa o header quando a sessao esta na aba e a query quando o link
        # ?p= abre o painel pela primeira vez.
        consulta = self.path.split("?")[1] if "?" in self.path else ""
        for parte in consulta.split("&"):
            if parte.startswith("token="):
                return parte.split("=", 1)[1]
        return None

    def _conta(self, corpo: dict | None = None):
        token = self._token()
        if not token and corpo:
            # A VPS tambem aceita o token no corpo (transicao antiga).
            token = str(corpo.get("token") or "").strip() or None
        return self.estado.conta_por_token(token)

    def do_OPTIONS(self):  # noqa: N802
        self._json(204, {})

    # ------------------------------------------------------------- GET ----

    def do_GET(self):  # noqa: N802
        caminho = self.path.split("?")[0].rstrip("/") or "/"
        consulta = self.path.split("?")[1] if "?" in self.path else ""
        params = dict(p.split("=", 1) for p in consulta.split("&") if "=" in p)

        if caminho == "/signup-guard":
            return self._json(200, {"ok": True, "allowed": True})

        if caminho == "/hunters/public":
            code = params.get("code", "")
            token = self.estado.por_code.get(code.upper())
            if not token:
                return self._erro(404, "codigo de afiliado nao encontrado")
            conta = self.estado.afiliados[token]
            return self._json(200, {"ok": True, "hunter": {"handle": conta["handle"], "name": conta["name"]}})

        if caminho == "/creators/me":
            conta = self._conta()
            if conta is None or conta.get("papel") != "criador":
                return self._erro(401, "token invalido")
            return self._json(200, self._painel_criador(conta))

        if caminho == "/hunters/me":
            conta = self._conta()
            if conta is None or conta.get("papel") != "afiliado":
                return self._erro(401, "token invalido")
            return self._json(200, self._painel_afiliado(conta))

        return self._erro(404, "rota nao encontrada")

    # ------------------------------------------------------------- POST ---

    def do_POST(self):  # noqa: N802
        caminho = self.path.split("?")[0].rstrip("/") or "/"
        dados = self._corpo()

        if caminho in ("/creators", "/hunters"):
            return self._criar(caminho, dados)

        if caminho in ("/creators/withdraw", "/hunters/withdraw"):
            return self._sacar(caminho, dados)

        if caminho == "/hunters/outreach/email":
            return self._contato(dados)

        return self._erro(404, "rota nao encontrada")

    # --------------------------------------------------------- auxiliares --

    def _criar(self, caminho: str, dados):
        papel = "criador" if caminho == "/creators" else "afiliado"
        handle = str(dados.get("handle") or "").strip()
        code = str(dados.get("code") or "").strip().upper()
        cpf = str(dados.get("cpf") or "").strip()
        email = str(dados.get("email") or "").strip()

        if not handle or len(handle) < 3:
            return self._erro(400, "handle invalido")
        if not (3 <= len(code) <= 32):
            return self._erro(400, "codigo invalido")
        if code in self.estado.por_code:
            return self._erro(409, "codigo ja em uso")
        if papel == "criador" and not cpf:
            return self._erro(400, "cpf obrigatorio")

        token = ("C" if papel == "criador" else "A") + secrets.token_hex(8).upper()[:15]
        conta = {
            "papel": papel,
            "token": token,
            "handle": handle,
            "code": code,
            "name": str(dados.get("name") or handle).strip(),
            "cpf": cpf,
            "email": email,
            "pix_key": email,
            "pix_cpf_cnpj": cpf,
            "pix_name": str(dados.get("name") or handle).strip(),
            "referrals": 3,
            "available_cents": 693,
            "pending_cents": 0,
            "withdrawn_cents": 0,
            "created_at": AGORA(),
            "hunter_code": str(dados.get("hunter_code") or "").strip().upper(),
        }
        if papel == "criador":
            self.estado.criadores[token] = conta
        else:
            self.estado.afiliados[token] = conta
        self.estado.por_code[code] = token

        if papel == "criador":
            payload = {
                "ok": True,
                "token": token,
                "creator": {
                    "id": self.estado.novo_id("criador"),
                    "name": conta["name"],
                    "handle": handle,
                    "code": code,
                },
            }
        else:
            payload = {
                "ok": True,
                "token": token,
                "hunter": {
                    "id": self.estado.novo_id("afiliado"),
                    "name": conta["name"],
                    "handle": handle,
                    "code": code,
                },
                "afiliado": {
                    "id": self.estado.novo_id("afiliado"),
                    "name": conta["name"],
                    "handle": handle,
                    "code": code,
                },
            }
        return self._json(200, payload)

    def _sacar(self, caminho: str, dados):
        papel = "criador" if caminho == "/creators/withdraw" else "afiliado"
        conta = self._conta(dados)
        if conta is None or conta.get("papel") != papel:
            return self._erro(401, "token invalido")
        pix = str(dados.get("pix_key") or "").strip()
        nome = str(dados.get("pix_name") or "").strip()
        documento = str(dados.get("pix_cpf_cnpj") or "").strip()
        email = str(dados.get("payer_email") or "").strip()
        if len(pix) < 3:
            return self._erro(400, "chave pix invalida")
        if len(nome) < 2:
            return self._erro(400, "nome do titular invalido")
        if len(documento) not in (11, 14):
            return self._erro(400, "cpf/cnpj invalido")
        if "@" not in email:
            return self._erro(400, "e-mail invalido")
        valor = conta["available_cents"]
        if valor <= 0:
            return self._erro(400, "sem saldo disponivel")
        conta["available_cents"] = 0
        conta["withdrawn_cents"] += valor
        saque = {
            "id": self.estado.novo_id("saque"),
            "amount_cents": valor,
            "status": "requested",
            "created_at": AGORA(),
        }
        self.estado.saques.setdefault(conta["token"], []).append(saque)
        return self._json(200, {"ok": True, "withdrawal": saque})

    def _contato(self, dados):
        conta = self._conta(dados)
        if conta is None or conta.get("papel") != "afiliado":
            return self._erro(401, "token invalido")
        nome = str(dados.get("name") or "").strip()
        email = str(dados.get("email") or "").strip()
        contato_url = str(dados.get("contact_url") or "").strip()
        if len(nome) < 2:
            return self._erro(400, "informe como o criador e conhecido")
        if "@" not in email:
            return self._erro(400, "e-mail invalido")
        if not re.match(r"^@[a-zA-Z0-9._-]{2,60}$", contato_url):
            return self._erro(400, "contato invalido")
        contato = {
            "id": self.estado.novo_id("contato"),
            "name": nome,
            "email": email,
            "contact_url": contato_url,
            "platform": str(dados.get("platform") or "").strip(),
            "created_at": AGORA(),
        }
        self.estado.contatos.setdefault(conta["token"], []).append(contato)
        return self._json(200, {"ok": True, "contact": contato, "recipient": email, "queued": False})

    def _painel_criador(self, conta: dict) -> dict:
        token = conta["token"]
        afiliado = None
        if conta.get("hunter_code"):
            token_afiliado = self.estado.por_code.get(conta["hunter_code"])
            if token_afiliado:
                a = self.estado.afiliados[token_afiliado]
                afiliado = {"handle": a["handle"], "name": a["name"], "code": a["code"]}
        return {
            "ok": True,
            "creator": {
                "id": "criador_" + token,
                "name": conta["name"],
                "handle": conta["handle"],
                "code": conta["code"],
                "pix_key": conta["pix_key"],
                "pix_cpf_cnpj": conta["pix_cpf_cnpj"],
                "pix_name": conta["pix_name"],
                "email": conta["email"],
            },
            "hunter": afiliado,
            "referrals": conta["referrals"],
            "available_cents": conta["available_cents"],
            "pending_cents": conta["pending_cents"],
            "withdrawn_cents": conta["withdrawn_cents"],
            "recent_referrals": [
                {
                    "pubkey": "pub-" + secrets.token_hex(4),
                    "created_at": AGORA() - 86400,
                    "status": "active",
                }
                for _ in range(conta["referrals"])
            ],
            "withdrawals": self.estado.saques.get(token, []),
        }

    def _painel_afiliado(self, conta: dict) -> dict:
        token = conta["token"]
        return {
            "ok": True,
            "afiliado": {
                "id": "afiliado_" + token,
                "name": conta["name"],
                "handle": conta["handle"],
                "code": conta["code"],
                "pix_key": conta["pix_key"],
                "pix_cpf_cnpj": conta["pix_cpf_cnpj"],
                "pix_name": conta["pix_name"],
            },
            "hunter": {
                "id": "afiliado_" + token,
                "name": conta["name"],
                "handle": conta["handle"],
                "code": conta["code"],
            },
            "outreach_count": len(self.estado.contatos.get(token, [])),
            "recruited_creators": 2,
            "referrals": 5,
            "commission_cents": 198,
            "available_cents": conta["available_cents"],
            "pending_cents": conta["pending_cents"],
            "withdrawn_cents": conta["withdrawn_cents"],
            "email_quota": {"used": len(self.estado.contatos.get(token, [])), "limit": 30, "days": 30},
            "recent_outreach": self.estado.contatos.get(token, []),
            "recent_creators": [
                {
                    "handle": "criador" + secrets.token_hex(2),
                    "code": "COD" + secrets.token_hex(2).upper(),
                    "referrals": 2,
                    "commission_cents": 198,
                }
                for _ in range(2)
            ],
            "withdrawals": self.estado.saques.get(token, []),
        }


def servir_api(port: int = 8792, estado: Estado | None = None):
    """Sobe a API mock na porta e devolve (httpd, base_url)."""

    class MockHandler(Handler):
        pass

    MockHandler.estado = estado or Estado()
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), MockHandler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}"
