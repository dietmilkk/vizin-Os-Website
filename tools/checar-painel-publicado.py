#!/usr/bin/env python3
"""Auditoria visual do painel: mede no Chromium como a página ficou de fato.

Imprime a geometria de cada bloco (posição, tamanho), o preenchimento das
barras, o arco do anel e a sparkline, em desktop e celular. Serve para
conferir alinhamento, proporção e ausência de estouro sem depender de olho.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8090").rstrip("/")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/auditoria-painel")
OUT.mkdir(parents=True, exist_ok=True)

JS_AUDIT = """
() => {
  const out = {blocos: [], barras: [], anel: null, spark: null, overflow: 0, largura: 0};
  out.largura = document.documentElement.clientWidth;
  out.overflow = document.documentElement.scrollWidth - out.largura;
  for (const card of document.querySelectorAll('.stat')) {
    const r = card.getBoundingClientRect();
    const label = card.querySelector('.label');
    const value = card.querySelector('.value, .barra-valor, .anel-numero');
    out.blocos.push({
      rotulo: label ? label.textContent.trim() : '',
      valor: value ? value.textContent.trim() : '',
      x: Math.round(r.left), y: Math.round(r.top),
      w: Math.round(r.width), h: Math.round(r.height),
    });
  }
  for (const fill of document.querySelectorAll('.barra-fill, .pilha-fill')) {
    out.barras.push({
      id: fill.id,
      pct: fill.style.width || '0%',
     larguraPx: Math.round(fill.getBoundingClientRect().width),
    });
  }
  const anel = document.getElementById('painelAnelArco');
  if (anel) {
    out.anel = {
      texto: document.getElementById('painelTaxa').textContent.trim(),
      dashoffset: anel.style.strokeDashoffset || getComputedStyle(anel).strokeDashoffset,
    };
  }
  const spark = document.getElementById('painelLatenciaGrafo');
  if (spark) {
    const poly = spark.querySelector('polyline');
    out.spark = {
      latencia: document.getElementById('painelLatencia').textContent.trim(),
      pontos: poly ? poly.getAttribute('points') : null,
      altura: Math.round(spark.getBoundingClientRect().height),
    };
  }
  return out;
}
"""


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for nome, viewport, mobile in [
            ("desktop", {"width": 1280, "height": 1000}, False),
            ("celular", {"width": 390, "height": 844}, True),
        ]:
            context = browser.new_context(viewport=viewport, is_mobile=mobile, has_touch=mobile)
            page = context.new_page()
            page.goto(f"{BASE}/painel", wait_until="networkidle")
            page.wait_for_function(
                "() => document.getElementById('painelStatusTexto')"
                "?.textContent?.startsWith('Atualizado')",
                timeout=30_000,
            )
            page.wait_for_timeout(800)
            dados = page.evaluate(JS_AUDIT)
            print(f"\n=== {nome} ({viewport['width']}px) ===")
            print(f"status: {page.inner_text('#painelStatusTexto').strip()}")
            print(f"erro visível: {page.locator('#painelErro').is_visible()}")
            print(f"overflow horizontal: {dados['overflow']}px")
            print("\nblocos (rótulo | valor | x,y w×h):")
            for b in dados["blocos"]:
                print(f"  {b['rotulo'][:26]:28} {b['valor'][:22]:24} ({b['x']:4},{b['y']:4}) {b['w']:4}×{b['h']:3}")
            print("\nbarras:")
            for barra in dados["barras"]:
                print(f"  {barra['id']:28} {barra['pct']:>8}  ({barra['larguraPx']}px)")
            print(f"\nanel: {dados['anel']}")
            print(f"sparkline: {dados['spark']}")
            page.screenshot(path=str(OUT / f"painel-{nome}.png"), full_page=True)
            context.close()
        browser.close()
    print(f"\ncapturas em {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
