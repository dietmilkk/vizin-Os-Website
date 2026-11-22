"""Confere se o painel de criadores/afiliados ficou com o desenho esperado.

Compara o estilo computado de cada bloco do painel com o esperado: antes
do refino varios blocos saiam sem moldura nenhuma (padding 0, fundo
transparente) e a grade de duas colunas nem existia.
"""
import os
import sys

from playwright.sync_api import sync_playwright

SITE = '/home/user/Downloads/app/site'
BASE = 'http://site.local/'


def route_handler(route):
    url = route.request.url
    path = url.replace(BASE, '/').split('?')[0].split('#')[0]
    target = os.path.join(SITE, path.lstrip('/'))
    if os.path.isfile(target):
        ctype = ('text/html' if target.endswith('.html')
                 else 'text/css' if target.endswith('.css')
                 else 'application/javascript' if target.endswith('.js')
                 else 'image/png' if target.endswith('.png')
                 else 'image/webp' if target.endswith('.webp')
                 else 'text/plain')
        route.fulfill(status=200, content_type=ctype, body=open(target, 'rb').read())
    else:
        route.fulfill(status=404, body=b'not found')


# seletor -> (descricao, condicoes que devem ser verdade)
CHECKS = [
    ('.role-switch', 'cartao do convite',
     {'borderTopWidth': '1px', 'backgroundColor': 'rgb(255, 241, 230)'}),
    ('.role-switch .btn', 'botao do convite', {'width': '80px'}),
    ('.panel-flow', 'fluxo do painel', {'display': 'grid'}),
    ('.panel-group__num', 'numero do passo',
     {'backgroundColor': 'rgb(255, 228, 233)', 'borderTopLeftRadius': '50%'}),
    ('.panel-group__title', 'titulo do passo', {'fontFamily': '"Fraunces"'}),
    ('.panel-group__lead', 'texto do passo', {'color': 'rgb(107, 90, 80)'}),
    ('.panel-subsection', 'bloco de apoio', {'borderTopWidth': '1px'}),
    ('.panel-card__title', 'titulo interno', {'fontFamily': '"Fraunces"'}),
    ('.panel-list li', 'item da lista', {'paddingLeft': '26px'}),
    ('.panel-two-col', 'grade em duas colunas',
     {'gridTemplateColumns': '499px 499px'}),
    ('.stat--accent', 'numero em destaque',
     {'backgroundColor': 'rgb(255, 228, 233)'}),
    ('.dashboard-heading', 'cabecalho do painel', {'paddingTop': '40px'}),
]

LANDING_CHECKS = [
    ('.aff-role', 'cartao de papel', {'borderTopLeftRadius': '24px'}),
    ('.aff-why-card', 'cartao deporque', {'borderTopLeftRadius': '24px'}),
    ('.aff-flow-card', 'cartao de passo', {'borderTopLeftRadius': '24px'}),
    ('.revenue-sheet', 'planilha da divisao', {'borderTopLeftRadius': '24px'}),
    ('.aff-cta', 'chamada final',
     {'gridTemplateColumns': '720px 280px', 'alignItems': 'center'}),
]


def probe(pg, checks):
    out = pg.evaluate('''(sels) => {
      const res = {};
      for (const s of sels) {
        const e = document.querySelector(s);
        if (!e) { res[s] = null; continue; }
        const c = getComputedStyle(e);
        const r = e.getBoundingClientRect();
        res[s] = {
          display: c.display, gridTemplateColumns: c.gridTemplateColumns,
          borderTopWidth: c.borderTopWidth, borderTopLeftRadius: c.borderTopLeftRadius,
          backgroundColor: c.backgroundColor, color: c.color,
          fontFamily: c.fontFamily, paddingLeft: c.paddingLeft,
          paddingTop: c.paddingTop, alignItems: c.alignItems,
          width: Math.round(r.width), height: Math.round(r.height)
        };
      }
      return res;
    }''', [c[0] for c in checks])
    fails = []
    for sel, desc, expect in checks:
        got = out.get(sel)
        if not got:
            fails.append('%s (%s): elemento ausente' % (desc, sel))
            continue
        for k, v in expect.items():
            if got.get(k) != v:
                fails.append('%s (%s): %s = %r, esperado %r' % (desc, sel, k, got.get(k), v))
    return fails


def main():
    fails = []
    with sync_playwright() as p:
        b = p.firefox.launch()
        ctx = b.new_context(viewport={'width': 1280, 'height': 1000})
        ctx.route('**/*', route_handler)
        pg = ctx.new_page()
        pg.goto(BASE + 'membros.html')
        pg.wait_for_timeout(1500)
        pg.evaluate('''() => {
          document.querySelectorAll('.hidden').forEach(e => {
            if (e.id && /ashboard/.test(e.id)) e.classList.remove('hidden');
          });
        }''')
        pg.wait_for_timeout(500)
        fails += probe(pg, CHECKS)
        fails += probe(pg, LANDING_CHECKS)
        b.close()

    if fails:
        print('FALHAS (%d):' % len(fails))
        for f in fails:
            print('  -', f)
        sys.exit(1)
    print('OK: %d blocos verificados, todos com o desenho esperado.'
          % (len(CHECKS) + len(LANDING_CHECKS)))


if __name__ == '__main__':
    main()
