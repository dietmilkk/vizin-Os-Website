"""Validação estática simples do site: âncoras, IDs, assets e símbolos SVG."""

from html.parser import HTMLParser
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["index.html", "manifesto/index.html", "documento/index.html", "afiliados/index.html", "moderacao/index.html", "painel/index.html", "404.html"]

# Caminhos que nunca existem no repositório: a hospedagem os serve em runtime.
# A Vercel cria /_vercel/insights/* quando o Web Analytics é habilitado.
HOST_ASSETS = ("/_vercel/",)


class Checker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.anchors = []
        self.assets = []
        self.symbols = set()
        self.uses = []
        self.lang = None
        self.title = None
        self._in_title = False
        self._in_style = False
        self._in_script = False
        self.meta_description = False
        self.images_without_alt = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.lang = attrs.get("lang")
        if tag == "title":
            self._in_title = True
        if tag == "style":
            self._in_style = True
        if tag == "script":
            self._in_script = True
        if tag == "meta" and attrs.get("name") == "description":
            self.meta_description = True
        if tag == "img" and "alt" not in attrs:
            self.images_without_alt += 1
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.anchors.append(attrs["href"][1:])
        if tag in ("link", "script", "img", "source"):
            value = attrs.get("href") or attrs.get("src")
            if value and not value.startswith(("http://", "https://", "data:", "#")):
                self.assets.append(value)
        if tag == "symbol" and "id" in attrs:
            self.symbols.add(attrs["id"])
        if tag == "use" and attrs.get("href", "").startswith("#"):
            self.uses.append(attrs["href"][1:])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "style":
            self._in_style = False
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title or "") + data.strip()


def check_page(name):
    path = ROOT / name
    if not path.exists():
        return [f"{name}: arquivo não encontrado"]

    parser = Checker()
    parser.feed(path.read_text(encoding="utf-8"))
    errors = []

    if parser.lang != "pt-BR":
        errors.append(f"{name}: lang deveria ser pt-BR")
    if not parser.title:
        errors.append(f"{name}: title ausente")
    if name == "index.html" and not parser.meta_description:
        errors.append(f"{name}: meta description ausente")
    if parser.images_without_alt:
        errors.append(f"{name}: {parser.images_without_alt} <img> sem alt")

    duplicates = {item for item in parser.ids if parser.ids.count(item) > 1}
    if duplicates:
        errors.append(f"{name}: IDs duplicados: {', '.join(sorted(duplicates))}")

    for anchor in parser.anchors:
        if anchor and anchor not in parser.ids:
            errors.append(f"{name}: âncora #{anchor} sem destino")

    for asset in parser.assets:
        if asset.startswith(HOST_ASSETS):
            continue
        if not (ROOT / asset.lstrip("/")).exists():
            errors.append(f"{name}: asset ausente: {asset}")

    for symbol in parser.uses:
        if symbol not in parser.symbols:
            errors.append(f"{name}: símbolo SVG ausente: #{symbol}")

    return errors


def check_css():
    errors = []
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    if css.count("{") != css.count("}"):
        errors.append("styles.css: chaves desbalanceadas")
    for token in ("--brand", "--bg", "--ink", "--font-display"):
        if token not in css:
            errors.append(f"styles.css: token ausente {token}")
    return errors


def check_js():
    errors = []
    for name in ("assets/app.js", "assets/pix.js", "assets/config.js", "assets/panel.js"):
        text = (ROOT / name).read_text(encoding="utf-8")
        if text.count("{") != text.count("}"):
            errors.append(f"{name}: chaves desbalanceadas")
        if text.count("(") != text.count(")"):
            errors.append(f"{name}: parênteses desbalanceados")
    return errors


def main():
    errors = []
    for page in PAGES:
        errors.extend(check_page(page))
    errors.extend(check_css())
    errors.extend(check_js())

    if errors:
        print("Falhas encontradas:")
        for error in errors:
            print(" -", error)
        return 1

    print("Site válido: páginas, âncoras, assets, SVG, CSS e JS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
