"""Verificacao visual do painel de afiliado: layout, responsividade e estilos.

Complementa o teste end-to-end conferindo geometria real no navegador
(sobreposicao, estouro de container, contraste e comportamento mobile).

Uso:
    python3 tests/test-layout-afiliado.py
"""

import json
import sys
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

from lib.primeiro_acesso import ja_visitou

BASE = "http://localhost:8099"
API = "https://api.188.166.156.109.sslip.io"
TOKEN_CACHE = "/tmp/vizin-teste-afiliado-token.json"

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


def audit(page, label, width, height):
    print(f"\n[{label}] {width}x{height}")

    data = page.evaluate(
        """() => {
        const out = { overflow: [], overlaps: [], link: null, cards: 0, groups: 0, groupGaps: [] };
        const docWidth = document.documentElement.clientWidth;
        const scrollWidth = document.documentElement.scrollWidth;

        // Cards do fluxo do afiliado (secao principal)
        const cards = Array.from(document.querySelectorAll('.panel-stat, .stat'));
        out.cards = cards.length;

        // Grupos numerados do painel do afiliado
        const groups = Array.from(document.querySelectorAll('.panel-group'));
        out.groups = groups.length;
        for (let i = 1; i < groups.length; i++) {
          const a = groups[i - 1].getBoundingClientRect();
          const b = groups[i].getBoundingClientRect();
          out.groupGaps.push(Math.round(b.top - a.bottom));
        }

        // Link de afiliado: campo e botao sem sobreposicao real
        const input = document.querySelector('#afiliadoLink');
        const btn = document.querySelector('#copyAfiliadoLink');
        if (input && btn) {
          const a = input.getBoundingClientRect();
          const b = btn.getBoundingClientRect();
          // Interseccao real nos dois eixos (funciona em linha e em coluna)
          const overlapX = Math.min(a.right, b.right) - Math.max(a.left, b.left);
          const overlapY = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
          const overlaps = overlapX > 1 && overlapY > 1;
          out.link = {
            inputW: Math.round(a.width),
            inputH: Math.round(a.height),
            btnW: Math.round(b.width),
            btnH: Math.round(b.height),
            sameRow: Math.abs(a.top - b.top) < 24,
            overlap: overlaps,
            stacked: b.top >= a.bottom - 1,
            value: input.value,
          };
        }

        // Textos que transbordam o proprio card
        cards.forEach((el) => {
          if (el.scrollWidth > el.clientWidth + 1) {
            out.overflow.push({
              cls: (el.className || '').toString().slice(0, 40),
              scroll: el.scrollWidth,
              client: el.clientWidth,
            });
          }
          const r = el.getBoundingClientRect();
          el.querySelectorAll('*').forEach((child) => {
            const cr = child.getBoundingClientRect();
            if (cr.width === 0 || cr.height === 0) return;
            if (cr.right > r.right + 1 || cr.left < r.left - 1) {
              out.overlaps.push({
                cls: (child.className || child.tagName || '').toString().slice(0, 40),
                left: Math.round(cr.left),
                right: Math.round(cr.right),
                card: Math.round(r.left) + '-' + Math.round(r.right),
              });
            }
          });
        });

        out.scrollWidth = scrollWidth;
        out.docWidth = docWidth;
        return out;
      }"""
    )

    check(
        "sem estouro horizontal da pagina",
        data["scrollWidth"] <= data["docWidth"] + 1,
        f"scroll={data['scrollWidth']} doc={data['docWidth']}",
    )
    check(
        "nenhum card fora do container",
        not data["overflow"],
        json.dumps(data["overflow"][:2]),
    )
    check(
        "cards renderizados",
        data["cards"] >= 6,
        f"cards={data['cards']}",
    )
    check(
        "painel tem 4 grupos numerados",
        data["groups"] == 4,
        f"groups={data['groups']}",
    )
    check(
        "intervalo uniforme entre os grupos",
        all(gap == 56 for gap in data["groupGaps"]),
        f"gaps={data['groupGaps']}",
    )
    check(
        "sem texto transbordando",
        not data["overlaps"],
        json.dumps(data["overlaps"][:2]),
    )

    if data["link"]:
        link = data["link"]
        check(
            "campo do link preenchido",
            bool(link["value"]),
            link["value"],
        )
        check(
            "campo do link tem largura util",
            link["inputW"] > 120,
            f"inputW={link['inputW']}",
        )
        check(
            "botao copiar visivel com tamanho util",
            link["btnW"] > 60 and link["btnH"] > 24,
            f"btn={link['btnW']}x{link['btnH']}",
        )
        check(
            "campo e botao nao se sobrepoem",
            not link["overlap"],
            json.dumps(link),
        )
        if width > 560:
            check(
                "campo e botao na mesma linha (acima de 560px)",
                link["sameRow"] and not link["overlap"],
                json.dumps(link),
            )
        else:
            check(
                "campo e botao empilhados no mobile (sem sobrepor)",
                link["stacked"] and not link["overlap"],
                json.dumps(link),
            )

    return data


def audit_publica(page, label, width):
    """Confere o ritmo e o ausencia de estouro na pagina publica."""
    print(f"\n[Publica - {label}] {width}px")
    data = page.evaluate(
        """() => {
        const doc = document.documentElement.clientWidth;
        const out = { scrollWidth: document.documentElement.scrollWidth, docWidth: doc,
                      overflow: [], gaps: [] };
        document.querySelectorAll('main *').forEach((el) => {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) return;
          if (r.right > doc + 1) {
            out.overflow.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 40),
                                right: Math.round(r.right) });
          }
        });
        const secs = [...document.querySelectorAll(
          '#partnerMarketing > .creators-hero, #partnerMarketing > .creators-hero-mobile, #partnerMarketing > .creators-guide, #guiaCompleto')]
          .filter(el => {
            const style = getComputedStyle(el);
            return style.display !== 'none' && style.visibility !== 'hidden';
          });
        for (let i = 1; i < secs.length; i++) {
          out.gaps.push(Math.round(secs[i].getBoundingClientRect().top
            - secs[i - 1].getBoundingClientRect().bottom));
        }
        return out;
      }"""
    )
    check(
        "publica sem estouro horizontal",
        data["scrollWidth"] <= data["docWidth"] + 1,
        f"scroll={data['scrollWidth']} doc={data['docWidth']}",
    )
    check(
        "publica sem elemento fora da viewport",
        not data["overflow"],
        json.dumps(data["overflow"][:2]),
    )
    check(
        "publica com intervalo uniforme entre secoes (56px)",
        len(data["gaps"]) == 3 and all(gap == 56 for gap in data["gaps"]),
        f"gaps={data['gaps']}",
    )
    return data


def main():
    code = "TESTLAY" + str(int(time.time()))[-4:]
    status, created = api_post(
        "/hunters", {"handle": "tlay" + code[-6:].lower(), "code": code}
    )
    if status == 200:
        token = created["token"]
        try:
            with open(TOKEN_CACHE, "w", encoding="utf-8") as handle:
                json.dump({"token": token}, handle)
        except Exception:
            pass
    elif status == 403 and created.get("code") == "IP_BLOCKED_DUPLICATE":
        # A VPS cria uma conta por IP: o teste reaproveita o token em cache.
        try:
            with open(TOKEN_CACHE, encoding="utf-8") as handle:
                token = json.load(handle).get("token", "")
        except Exception:
            token = ""
        if not token:
            print(f"Este IP ja criou conta e nao ha token em cache: teste pulado.")
            return 0
        print("Este IP ja criou conta: reaproveitando o afiliado de teste em cache.")
    else:
        print(f"Falha ao criar afiliado de teste: {status} {created}")
        return 1
    print(f"\nAfiliado de teste: code={code}")

    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()

        for width, height, label in [
            (1440, 1000, "Desktop"),
            (1024, 900, "Tablet"),
            (768, 900, "Tablet estreito"),
            (390, 844, "Mobile"),
            (320, 700, "Mobile pequeno"),
        ]:
            page = browser.new_page(viewport={"width": width, "height": height})
            ja_visitou(page)
            page.goto(
                f"{BASE}/afiliados/?afiliado_token={token}", wait_until="networkidle"
            )
            page.wait_for_timeout(600)
            audit(page, label, width, height)
            page.close()

        # Pagina publica em varias larguras
        for width, height, label in [
            (1440, 1000, "Desktop"),
            (768, 900, "Tablet estreito"),
            (320, 700, "Mobile pequeno"),
        ]:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(f"{BASE}/afiliados/", wait_until="networkidle")
            page.wait_for_timeout(1200)
            audit_publica(page, label, width)
            page.close()

        # Painel em tema escuro
        page = browser.new_page(
            viewport={"width": 1440, "height": 1000}, color_scheme="dark"
        )
        ja_visitou(page)
        page.goto(f"{BASE}/afiliados/?afiliado_token={token}", wait_until="networkidle")
        page.wait_for_selector("#afiliadoDashboardView:not(.hidden)", timeout=20000)
        page.wait_for_timeout(600)
        print("\n[Dark mode]")
        colors = page.evaluate(
            """() => {
            const card = document.querySelector('#afiliadoDashboardView .form-card');
            const cs = getComputedStyle(card);
            const parse = (value) => (value.match(/[\\d.]+/g) || []).map(Number);
            return {
              cardBg: cs.backgroundColor,
              cardText: cs.color,
              bg: parse(cs.backgroundColor),
              fg: parse(cs.color),
            };
        }"""
        )
        # No tema escuro o fundo do card deve ser mais escuro que o texto.
        check(
            "card usa fundo escuro",
            colors["bg"][0] < 60 and colors["bg"][1] < 60,
            colors["cardBg"],
        )
        check(
            "texto claro no card",
            colors["fg"][0] > 200,
            colors["cardText"],
        )
        page.close()

        browser.close()

    print(f"\n{'=' * 52}")
    print(f"  {checks - len(failures)}/{checks} verificacoes passaram")
    if failures:
        print("  Falhas:")
        for failure in failures:
            print(f"    - {failure}")
        return 1
    print("  Layout OK em todas as larguras!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
