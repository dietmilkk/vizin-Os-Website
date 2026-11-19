"""
Jornada real de usuário na Comunidade — contra a API local.
Cobre: cadastro/login/logout, publicação, votos (ida e volta), comentários,
edição de placar, ordenação, filtro por tag, aba implementadas, exclusão,
limites de campo, unicode/emoji, XSS (renderização inert no cliente), 404s,
trava de login por falhas e o selo de administração.
"""
import json
import urllib.request
import urllib.error
import sys

import sys
API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8810"
falhas = []
passos = []


def req(caminho, metodo="GET", corpo=None, token=None):
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    r = urllib.request.Request(API + caminho, data=dados, method=metodo)
    r.add_header("content-type", "application/json")
    if token:
        r.add_header("authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=15) as resposta:
            return resposta.status, json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}


def checar(descricao, condicao, detalhe=""):
    if condicao:
        passos.append(descricao)
    else:
        falhas.append(f"{descricao} {detalhe}")


# ---------- 1. cadastro de tres usuarios reais ----------
contas = {}
for apelido in ["ana.souza", "bruno-lima", "carla_99"]:
    status, dados = req("/forum/register", "POST", {"username": apelido, "password": "senha-forte-123"})
    checar(f"cadastro {apelido}", status == 201 and dados.get("token"), f"-> {status} {dados}")
    contas[apelido] = dados.get("token")

# cadastro duplicado (case-insensitive)
status, dados = req("/forum/register", "POST", {"username": "ANA.SOUZA", "password": "senha-forte-123"})
checar("cadastro duplicado recusado (409)", status == 409, f"-> {status}")

# cadastro com apelido inválido
for ruim in ["ab", "tem espaço", "nome.super.longo.demais.aqui", "silva&co", ""]:
    status, _ = req("/forum/register", "POST", {"username": ruim, "password": "senha-forte-123"})
    checar(f"apelido invalido recusado: '{ruim[:16]}'", status == 400, f"-> {status}")

# senha curta
status, _ = req("/forum/register", "POST", {"username": "curta", "password": "12345678"})
checar("senha com 8 chars aceita (limite minimo)", status == 201, f"-> {status}")
status, _ = req("/forum/register", "POST", {"username": "curtinha", "password": "1234567"})
checar("senha com 7 chars recusada", status == 400, f"-> {status}")

# ---------- 2. login e sessão ----------
status, dados = req("/forum/login", "POST", {"username": "ANA.SOUZA", "password": "senha-forte-123"})
checar("login case-insensitive", status == 200 and dados.get("token"), f"-> {status}")
status, dados = req("/forum/login", "POST", {"username": "ana.souza", "password": "errada-12345"})
checar("senha errada -> 401", status == 401, f"-> {status}")
status, dados = req("/forum/session", token=contas["ana.souza"])
checar("sessão válida", status == 200 and dados.get("username") == "ana.souza", f"-> {status}")
status, _ = req("/forum/session", token="token-falso-999")
checar("sessão falsa -> 401", status == 401, f"-> {status}")

# ---------- 3. publicação de propostas ----------
propostas = [
    ("Encontros por categoria", "Adicionar filtro de categoria e horário na lista de encontros do bairro.", "melhoria", "ana.souza"),
    ("Modo escuro completo", "Tema escuro em todas as telas, inclusive nos grupos e nos encontros.", "ideia", "bruno-lima"),
    ("Erro ao abrir o mapa", "O mapa fecha sozinho quando toco no marcador de encontro em algumas regiões.", "bug", "carla_99"),
    ("Café dos vizinhos mensal", "Um encontro fixo todo primeiro sábado, num café do bairro, sem organização formal.", "ideia", "ana.souza"),
]
ids = {}
for titulo, texto, tag, autor in propostas:
    status, dados = req("/forum/posts", "POST",
                        {"title": titulo, "body": texto, "tag": tag},
                        token=contas[autor])
    checar(f"publicar '{titulo}'", status == 201 and dados.get("post", {}).get("id"), f"-> {status}")
    ids[titulo] = dados.get("post", {}).get("id")

# publicação sem login
status, _ = req("/forum/posts", "POST", {"title": "Sem login aqui", "body": "texto com dez letras", "tag": "ideia"})
checar("publicar sem sessão -> 401", status == 401, f"-> {status}")

# validação de campos
status, _ = req("/forum/posts", "POST", {"title": "curt", "body": "texto com dez letras", "tag": "ideia"}, token=contas["ana.souza"])
checar("titulo curto -> 400", status == 400, f"-> {status}")
status, _ = req("/forum/posts", "POST", {"title": "Titulo valido aqui", "body": "curto", "tag": "ideia"}, token=contas["ana.souza"])
checar("texto curto -> 400", status == 400, f"-> {status}")
status, _ = req("/forum/posts", "POST", {"title": "Titulo valido aqui", "body": "texto com dez letras", "tag": "inexistente"}, token=contas["ana.souza"])
checar("tag inválida -> 400", status == 400, f"-> {status}")

# limite máximo de título (120) e texto (4000) — com outra conta, porque a
# ana.souza já usou a cota anti-spam de publicação (5 por hora)
status, dados = req("/forum/posts", "POST",
                    {"title": "T" * 120, "body": "B" * 4000, "tag": "outro"},
                    token=contas["bruno-lima"])
checar("limites máximos aceitos (120/4000)", status == 201, f"-> {status}")
status, _ = req("/forum/posts", "POST",
                {"title": "T" * 121, "body": "B" * 10, "tag": "outro"},
                token=contas["carla_99"])
checar("titulo com 121 chars -> 400", status == 400, f"-> {status}")
# enche a cota da bruno-lima (3 publicações até aqui) e testa o bloqueio
# a cota anti-spam (5/hora) é testada no fim, para não bloquear a bruno-lima
# nas outras etapas (ver seção 12)

# unicode + emoji
status, dados = req("/forum/posts", "POST",
                    {"title": "Encontro na praça do bairro ☕",
                     "body": "Quem curte um café? Vamos marcar na praça — família e pets bem-vindos 🐶🎉",
                     "tag": "ideia"},
                    token=contas["bruno-lima"])
checar("unicode + emoji na publicação", status == 201, f"-> {status}")
id_unicode = dados.get("post", {}).get("id")

# XSS: o API guarda o texto cru; o cliente renderiza via textContent (inert).
# Aqui validamos que a API NÃO faz escaping destrutivo e devolve o texto cru
# (a proteção é no cliente), e que o texto não vaza em outra codificação.
status, dados = req("/forum/posts", "POST",
                    {"title": "<script>alert('xss')</script>",
                     "body": "Tentativa de <img src=x onerror=alert(1)> em texto",
                     "tag": "outro"},
                    token=contas["carla_99"])
checar("XSS armazenado sem erro 500 (proteção é no cliente)", status == 201, f"-> {status}")
id_xss = dados.get("post", {}).get("id")
if id_xss:
    status, dados = req(f"/forum/posts/{id_xss}")
    checar("XSS: título devolvido intacto (cliente renderiza inert)",
           dados.get("post", {}).get("title") == "<script>alert('xss')</script>")

# ---------- 4. votos: sobe, troca, repete, zera ----------
alvo = ids["Encontros por categoria"]
tokens_votantes = [contas["bruno-lima"], contas["carla_99"]]


def votar(token, valor):
    return req(f"/forum/posts/{alvo}/vote", "POST", {"value": valor}, token=token)


s, d = votar(tokens_votantes[0], 1)
checar("voto +1", s == 200 and d.get("score") == 1, f"-> {s} {d}")
s, d = votar(tokens_votantes[0], 1)
checar("voto repetido não duplica", d.get("score") == 1, f"-> {d}")
s, d = votar(tokens_votantes[0], -1)
checar("trocar voto para -1", d.get("score") == -1 and d.get("up") == 0 and d.get("down") == 1, f"-> {d}")
s, d = votar(tokens_votantes[0], 0)
checar("zerar voto", d.get("score") == 0 and d.get("my_vote") == 0, f"-> {d}")
s, d = votar(tokens_votantes[0], 1)
s2, d2 = votar(tokens_votantes[1], 1)
checar("dois usuários votam", d2.get("score") == 2, f"-> {d2}")
s, d = req(f"/forum/posts/{alvo}/vote", "POST", {"value": 5}, token=tokens_votantes[0])
checar("valor de voto inválido -> 400", s == 400, f"-> {s}")
s, d = req(f"/forum/posts/{alvo}/vote", "POST", {"value": 1})
checar("votar sem sessão -> 401", s == 401, f"-> {s}")
s, d = req(f"/forum/posts/id-que-nao-existe/vote", "POST", {"value": 1}, token=tokens_votantes[0])
checar("votar em post inexistente -> 404", s == 404, f"-> {s}")

# ---------- 5. comentários ----------
s, d = req(f"/forum/posts/{alvo}/comments", "POST", {"body": "Topo demais! Podia ter lembrete no dia."}, token=tokens_votantes[1])
checar("comentar", s == 201 and d.get("comment", {}).get("id"), f"-> {s}")
s, d = req(f"/forum/posts/{alvo}/comments", "POST", {"body": "x"}, token=tokens_votantes[1])
checar("comentário de 1 char -> 400", s == 400, f"-> {s}")
s, d = req(f"/forum/posts/{alvo}/comments", "POST", {"body": "C" * 1000}, token=tokens_votantes[1])
checar("comentário de 1000 chars aceito", s == 201, f"-> {s}")
s, d = req(f"/forum/posts/{alvo}/comments", "POST", {"body": "C" * 1001}, token=tokens_votantes[1])
checar("comentário de 1001 chars -> 400", s == 400, f"-> {s}")
s, d = req(f"/forum/posts/{alvo}/comments", "POST", {"body": "emoji 😊 e acentuação: coração ❤"}, token=tokens_votantes[0])
checar("comentário com emoji/acentos", s == 201, f"-> {s}")
s, d = req(f"/forum/posts/{alvo}/comments", "POST", {"body": "anônimo"}, token=None)
checar("comentar sem sessão -> 401", s == 401, f"-> {s}")
s, d = req(f"/forum/posts/{alvo}")
checar("contador de comentários = 3", d.get("post", {}).get("comment_count") == 3,
       f"-> {d.get('post', {}).get('comment_count')}")

# ---------- 6. ordenação e filtro ----------
s, d = req("/forum/posts?sort=top&status=open")
posts = d.get("posts", [])
scores = [p["score"] for p in posts]
checar("ordenar por popularidade (decrescente)", scores == sorted(scores, reverse=True), f"-> {scores}")
s, d = req("/forum/posts?sort=new&status=open")
criados = [p["created_at"] for p in d.get("posts", [])]
checar("ordenar por novidade (decrescente)", criados == sorted(criados, reverse=True))
s, d = req("/forum/posts?tag=bug&status=open")
checar("filtro por tag bug (1 proposta)", d.get("total") == 1, f"-> {d.get('total')}")
s, d = req("/forum/posts?tag=ideia&status=open")
checar("filtro por tag ideia (3 propostas)", d.get("total") == 3, f"-> {d.get('total')}")
s, d = req("/forum/posts?status=open&limit=2")
checar("paginação: limit=2 devolve 2", len(d.get("posts", [])) == 2 and d.get("total") > 2, f"-> {len(d.get('posts', []))}/{d.get('total')}")
s, d = req("/forum/posts?status=open&limit=2&offset=2")
checar("paginação: offset pula os 2 primeiros", len(d.get("posts", [])) == 2, f"-> {len(d.get('posts', []))}")

# my_vote refletido por usuário
s, d = req("/forum/posts?status=open", token=tokens_votantes[1])
meu = [p for p in d["posts"] if p["id"] == alvo][0]
checar("my_vote visível para quem votou", meu.get("my_vote") == 1, f"-> {meu.get('my_vote')}")
s, d = req("/forum/posts?status=open", token=contas["ana.souza"])
meu = [p for p in d["posts"] if p["id"] == alvo][0]
checar("my_vote zerado para quem não votou", meu.get("my_vote") == 0, f"-> {meu.get('my_vote')}")

# ---------- 7. aba implementadas + selo adm ----------
s, d = req("/forum/admin/status", "POST", {"post_id": alvo, "status": "done", "note": "Entra na versão 1.4"}, token="token-de-admin")
checar("admin marca implementada (com token)", s == 200 and d.get("post", {}).get("status") == "done", f"-> {s}")
s, d = req("/forum/admin/status", "POST", {"post_id": id_unicode, "status": "done"})
checar("admin sem token -> 401", s == 401, f"-> {s}")
s, d = req("/forum/posts?status=done")
checar("aba implementadas tem 1", d.get("total") == 1 and d["posts"][0]["status_note"] == "Entra na versão 1.4", f"-> {d}")
s, d = req("/forum/posts?status=open")
checar("aba discussão perdeu a implementada", all(p["id"] != alvo for p in d.get("posts", [])))

# status geral
s, d = req("/forum/status")
checar("status: open_count e done_count coerentes", d.get("done_count") == 1, f"-> {d}")

# ---------- 8. exclusão (dono sim, outros não) ----------
s, d = req("/forum/posts", "POST", {"title": "Proposta para apagar", "body": "Esta proposta sera apagada pela própria autora.", "tag": "outro"}, token=contas["carla_99"])
id_apagar = d["post"]["id"]
s, d = req(f"/forum/posts/{id_apagar}", "DELETE", token=contas["ana.souza"])
checar("apagar proposta alheia -> 403", s == 403, f"-> {s}")
s, d = req(f"/forum/posts/{id_apagar}", "DELETE", token=contas["carla_99"])
checar("apagar a própria proposta", s == 200, f"-> {s}")
s, d = req(f"/forum/posts/{id_apagar}")
checar("proposta apagada -> 404", s == 404, f"-> {s}")

# comentário: dono apaga o seu
s, d = req(f"/forum/posts/{alvo}/comments", "POST", {"body": "Comentário que vou apagar."}, token=tokens_votantes[0])
cid = d["comment"]["id"]
s, d = req(f"/forum/comments/{cid}", "DELETE", token=tokens_votantes[1])
checar("apagar comentário alheio -> 403", s == 403, f"-> {s}")
s, d = req(f"/forum/comments/{cid}", "DELETE", token=tokens_votantes[0])
checar("apagar o próprio comentário", s == 200, f"-> {s}")
s, d = req(f"/forum/posts/{alvo}")
checar("contador de comentários atualizado após apagar", d.get("post", {}).get("comment_count") == 3,
       f"-> {d.get('post', {}).get('comment_count')}")

# ---------- 9. anti-spam: cota de 5 publicações por hora por conta ----------
# a bruno-lima fez 3 publicações até aqui (modos escuro, limites e unicode);
# as próximas 2 cabem, a 6ª é bloqueada
for n in range(4, 6):
    status, _ = req("/forum/posts", "POST", {"title": f"Cota numero {n} da hora", "body": f"Publicacao numero {n} para encher a cota anti-spam da conta.", "tag": "outro"}, token=contas["bruno-lima"])
    checar(f"{n}ª publicação da mesma conta aceita", status == 201, f"-> {status}")
status, _ = req("/forum/posts", "POST", {"title": "Sexta não passa", "body": "A sexta publicacao na hora deve ser bloqueada pelo anti-spam.", "tag": "outro"}, token=contas["bruno-lima"])
checar("anti-spam: 6ª publicação na hora -> 429", status == 429, f"-> {status}")

# ---------- 10. login: trava por falhas e libera pela senha certa ----------
for i in range(8):
    s, _ = req("/forum/login", "POST", {"username": "carla_99", "password": f"errada-{i}-xxxxx"})
checar("8 falhas registradas", s == 401, f"-> {s}")
s, _ = req("/forum/login", "POST", {"username": "carla_99", "password": "senha-forte-123"})
checar("9ª tentativa (mesmo certa) -> 429", s == 429, f"-> {s}")
s, _ = req("/forum/login", "POST", {"username": "ana.souza", "password": "senha-forte-123"})
checar("outra conta não é afetada", s == 200, f"-> {s}")

# ---------- 11. logout invalida ----------
s, d = req("/forum/logout", "POST", token=contas["bruno-lima"])
s, d = req("/forum/session", token=contas["bruno-lima"])
checar("logout invalida a sessão", s == 401, f"-> {s}")

# ---------- 12. 404 e corpo grande ----------
s, d = req("/forum/rota-inexistente")
checar("rota inexistente -> 404", s == 404, f"-> {s}")
s, d = req(f"/forum/posts/{'x' * 500}")
checar("id gigante -> 404 sem quebrar", s == 404, f"-> {s}")

print()
print(f"PASSOS OK: {len(passos)}")
if falhas:
    print(f"FALHOU ({len(falhas)}):")
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("Jornada real na API: 100% OK")
