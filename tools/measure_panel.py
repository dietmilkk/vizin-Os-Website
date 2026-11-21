"""Mede o painel de criadores/afiliados com o CSS do site realmente aplicado.

file:// quebra os caminhos absolutos (/assets/...), então as requisicoes
sao interceptadas e servidas do disco.
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


MEASURE = '''() => {
  const sels = %s;
  const res = {};
  for (const s of sels) {
    const els = [...document.querySelectorAll(s)];
    res[s] = els.slice(0, 4).map(e => {
      const r = e.getBoundingClientRect();
      const c = getComputedStyle(e);
      return {
        w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x),
        disp: c.display, cols: c.gridTemplateColumns, gap: c.gap,
        pad: c.padding, mar: c.margin, fs: c.fontSize, fw: c.fontWeight,
        ff: c.fontFamily.split(',')[0], col: c.color,
        bt: c.borderTopWidth, br: c.borderTopLeftRadius, bg: c.backgroundColor,
        ls: c.letterSpacing, lh: c.lineHeight
      };
    });
  }
  return res;
}'''


def measure(pg, sels):
    return pg.evaluate(MEASURE % sels)


def main():
    sels = ['.dashboard-heading', '.role-switch', '.form-card', '.stats-grid',
            '.stat', '.panel-flow', '.panel-group__head', '.panel-group__num',
            '.panel-two-col', '.panel-subsection', '.panel-card__title',
            '.withdraw-panel', '.aff-section__head', '.aff-role', '.aff-flow-card',
            '.aff-why-card', '.aff-money-panel', '.aff-cta', '.aff-splitbar']
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
        out = measure(pg, sels)
        for k, v in out.items():
            print('==', k)
            for e in v:
                print('   ', {kk: vv for kk, vv in e.items() if vv not in ('none', 'normal', 'rgba(0, 0, 0, 0)')})
        b.close()


if __name__ == '__main__':
    main()
