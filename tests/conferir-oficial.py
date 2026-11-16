"""Confere o conteudo publicado no dominio oficial, como um visitante."""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://vizin-os.page.gd"

with sync_playwright() as playwright:
    browser = playwright.firefox.launch()
    contexto = browser.new_context(viewport={"width": 1280, "height": 900})
    pagina = contexto.new_page()
    erros = []
    pagina.on("pageerror", lambda e: erros.append(str(e)))

    pagina.goto(f"{BASE}/afiliados/", wait_until="networkidle")
    pagina.wait_for_timeout(1500)

    dados = pagina.evaluate(
        """() => {
          const dev = document.querySelector('#divisao .split-item--dev p');
          const hero = document.querySelector('.creators-hero');
          return {
            url: location.href,
            breadcrumbNoSite: document.querySelectorAll('.breadcrumb').length,
            breadcrumbTexto: document.querySelector('.breadcrumb')?.innerText.replace(/\\s+/g,' '),
            heroTexto: hero ? hero.innerText.replace(/\\s+/g, ' ').slice(0, 260) : null,
            devTexto: dev ? dev.innerText.trim() : null,
            devNoGuia: document.querySelector('#guiaDivisao .split-item--dev p')?.innerText.trim(),
            heroParagrafos: hero ? hero.querySelectorAll('p').length : 0,
            modalIntro: document.getElementById('createIntro')?.textContent,
            guiaAcordeao: document.querySelectorAll('[data-guide-target]').length,
            temObservacoes: !!document.getElementById('outreachNotes'),
            temEyebrow: document.querySelectorAll('.eyebrow').length,
            withdrawHistory: !!document.querySelector('.withdraw-history'),
            withdrawPadding: document.querySelector('.withdraw-history')
              ? getComputedStyle(document.querySelector('.withdraw-history')).paddingLeft : null,
            withdrawBorda: document.querySelector('.withdraw-history')
              ? getComputedStyle(document.querySelector('.withdraw-history')).borderLeftWidth : null,
          };
        }"""
    )
    for chave, valor in dados.items():
        print(f"  {chave}: {valor}")
    print("  ERROS JS:", erros)
    browser.close()
