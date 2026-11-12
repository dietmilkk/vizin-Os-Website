"""Gera ícones e imagem Open Graph do site em SVG."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

BRAND = "#e63956"


def make_svg_icon(size: int, path: Path):
    """Gera um ícone SVG do logo vizin.Os no tamanho especificado."""
    radius = size // 4
    house_size = size * 0.46
    cx = size / 2
    cy = size / 2 + house_size * 0.04
    h = house_size
    line_width = max(4, int(house_size * 0.1))
    p = size // 4 + 5

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" role="img" aria-label="vizin.Os">
  <rect width="{size}" height="{size}" rx="{radius}" fill="{BRAND}"/>
  <g fill="none" stroke="#ffffff" stroke-width="{line_width}" stroke-linecap="round" stroke-linejoin="round">
    <path d="M{size * 0.30} {size * 0.50} {size / 2 + p} {size * 0.34} {size * 0.70} {size * 0.50}"/>
    <path d="M{size * 0.35} {size * 0.54} v{size * 0.62}h{size * 0.30}"/>
    <path d="M{size * 0.40} {size * 0.6} v{size * 0.34}"/>
  </g>
</svg>'''
    path.write_text(svg.strip())


def make_og_svg():
    """Gera imagem Open Graph em SVG."""
    W, H = 1200, 630
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="vizin.Os - Seu bairro existe.">
  <defs>
    <style>
      .serif{{font-family:'Bricolage Grotesque','Comfortaa',system-ui,sans-serif}}
      .sans{{font-family:'Comfortaa',system-ui,sans-serif}}
    </style>
  </defs>
  <rect width="{W}" height="{H}" fill="#fbf8f5"/>
  <ellipse cx="1125" cy="-150" rx="250" ry="200" fill="#fdecef"/>
  <ellipse cx="50" cy="570" rx="200" ry="200" fill="#e8f2ec"/>
  <ellipse cx="1200" cy="570" rx="130" ry="130" fill="#f3ede7"/>
  <rect x="80" y="66" width="64" height="64" rx="18" fill="{BRAND}"/>
  <rect x="95" y="81" width="34" height="34" fill="#ffffff"/>
  <polygon points="{BRAND},{BRAND},{BRAND},{BRAND},{BRAND},{BRAND}" fill="#ffffff"/>
  <path d="M102 100 L120 86 L138 100" stroke="#ffffff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M108 100 v28 M132 100 v28" stroke="#ffffff" stroke-width="4" stroke-linecap="round"/>
  <text x="160" y="114" class="sans" font-weight="600" font-size="34" fill="#211d1a">vizin.Os</text>
  <text x="80" y="232" class="serif" font-weight="600" font-size="62" fill="#211d1a">Seu bairro existe.</text>
  <text x="80" y="304" class="serif" font-style="italic" font-weight="600" font-size="62" fill="{BRAND}">Só falta um lugar</text>
  <text x="80" y="376" class="serif" font-weight="600" font-size="62" fill="#211d1a">para ele se encontrar.</text>
  <text x="84" y="454" class="sans" font-size="25" fill="#5f5751">Grupos, encontros e conversas privadas</text>
  <text x="84" y="488" class="sans" font-size="25" fill="#5f5751">com quem mora perto de verdade.</text>
  <text x="84" y="562" class="sans" font-weight="600" font-size="22" fill="{BRAND}">vizin-os.page.gd</text>
  <g fill="{BRAND}">
    <rect x="84" y="502" width="115" height="34" rx="17"/>
    <text x="141.5" y="528" class="sans" font-weight="600" font-size="16" fill="#c42e49" text-anchor="middle">Sem algoritmo</text>
  </g>
  <g fill="{BRAND}">
    <rect x="209" y="502" width="110" height="34" rx="17"/>
    <text x="264" y="528" class="sans" font-weight="600" font-size="16" fill="#c42e49" text-anchor="middle">Sem telefone</text>
  </g>
  <g fill="{BRAND}">
    <rect x="329" y="502" width="125" height="34" rx="17"/>
    <text x="391.5" y="528" class="sans" font-weight="600" font-size="16" fill="#c42e49" text-anchor="middle">Offline-first</text>
  </g>
  <rect x="830" y="96" width="290" height="470" rx="46" fill="#211d1a"/>
  <rect x="840" y="106" width="270" height="450" rx="37" fill="#fbf8f5"/>
  <rect x="930" y="116" width="90" height="20" rx="10" fill="#0b0908"/>
  <text x="858" y="140" class="sans" font-weight="600" font-size="12" fill="#211d1a">9:41</text>
  <rect x="1062" y="138" width="3" height="5" fill="#211d1a" rx="1.5"/>
  <rect x="1067" y="136" width="3" height="7" fill="#211d1a" rx="1.5"/>
  <rect x="1072" y="134" width="3" height="9" fill="#211d1a" rx="1.5"/>
  <rect x="844" y="160" width="28" height="28" rx="9" fill="#fdecef"/>
  <text x="882" y="180" class="sans" font-weight="600" font-size="15" fill="#211d1a">Vila Mariana</text>
  <text x="882" y="196" class="sans" font-size="10" fill="#8a8078">São Paulo · sua zona</text>
  <rect x="1172" y="178" width="30" height="30" rx="15" fill="#fdecef"/>
  <text x="1187" y="202" class="sans" font-weight="600" font-size="13" fill="#e63956" text-anchor="middle">M</text>
  <rect x="844" y="208" width="266" height="32" rx="10" fill="#ffffff" stroke="#e7dfd7" stroke-width="1"/>
  <text x="866" y="229" class="sans" font-size="11" fill="#8a8078">Buscar grupo no bairro…</text>
  <rect x="844" y="256" width="266" height="56" rx="12" fill="#ffffff" stroke="#e7dfd7" stroke-width="1"/>
  <rect x="854" y="268" width="32" height="32" rx="9" fill="#fdecef"/>
  <text x="896" y="286" class="sans" font-weight="600" font-size="12" fill="#211d1a">Vila Mariana</text>
  <text x="896" y="304" class="sans" font-size="9" fill="#8a8078">3 novas mensagens</text>
  <rect x="1098" y="280" width="28" height="14" rx="7" fill="#e63956"/>
  <text x="1112" y="292" class="sans" font-weight="600" font-size="9" fill="#ffffff" text-anchor="middle">234</text>
  <rect x="844" y="320" width="266" height="56" rx="12" fill="#ffffff" stroke="#e7dfd7" stroke-width="1"/>
  <rect x="854" y="332" width="32" height="32" rx="9" fill="#fdecef"/>
  <text x="896" y="350" class="sans" font-weight="600" font-size="12" fill="#211d1a">Música no bairro</text>
  <text x="896" y="368" class="sans" font-size="9" fill="#8a8078">1 novo encontro</text>
  <rect x="1098" y="344" width="28" height="14" rx="7" fill="#e63956"/>
  <text x="1112" y="356" class="sans" font-weight="600" font-size="9" fill="#ffffff" text-anchor="middle">45</text>
  <rect x="844" y="386" width="266" height="56" rx="12" fill="#ffffff" stroke="#e7dfd7" stroke-width="1"/>
  <rect x="854" y="398" width="32" height="32" rx="9" fill="#fdecef"/>
  <text x="896" y="416" class="sans" font-weight="600" font-size="12" fill="#211d1a">Horta comunitária</text>
  <text x="896" y="434" class="sans" font-size="9" fill="#8a8078">12 vizinhos</text>
  <rect x="844" y="452" width="266" height="50" rx="12" fill="#fdecef" stroke="#f0d6db" stroke-width="1"/>
  <rect x="854" y="464" width="30" height="20" rx="8" fill="#ffffff"/>
  <text x="869" y="480" class="sans" font-weight="600" font-size="14" fill="#e63956" text-anchor="middle">15</text>
  <text x="869" y="494" class="sans" font-weight="600" font-size="7" fill="#8a8078" text-anchor="middle">NOV</text>
  <text x="906" y="480" class="sans" font-weight="600" font-size="11" fill="#211d1a">Mutirão de limpeza</text>
  <text x="906" y="496" class="sans" font-size="9" fill="#8a8078">Praça Central · 9h</text>
  <rect x="840" y="598" width="270" height="12" fill="#ffffff"/>
  <text x="858" y="610" class="sans" font-size="8" fill="#e63956">⌂ Início</text>
  <text x="948" y="610" class="sans" font-size="8" fill="#8a8078">⌕ Descobrir</text>
  <text x="1078" y="610" class="sans" font-size="8" fill="#8a8078">◎ Perfil</text>
</svg>'''
    (ASSETS / "og-image.svg").write_text(svg.strip())


def svg_to_png(svg_path: Path, png_path: Path, width: int | None = None):
    """Converte um SVG em PNG (mesma imagem usada em redes sociais e ícones)."""
    import cairosvg

    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(png_path),
        output_width=width,
    )


if __name__ == "__main__":
    make_svg_icon(192, ASSETS / "icon-192.svg")
    make_svg_icon(512, ASSETS / "icon-512.svg")
    make_svg_icon(180, ASSETS / "apple-touch-icon.svg")
    make_og_svg()
    print("Imagens SVG geradas em", ASSETS)

    # PNGs derivados dos SVGs (o site e as redes sociais usam os dois formatos).
    svg_to_png(ASSETS / "og-image.svg", ASSETS / "og-image.png", width=1200)
    svg_to_png(ASSETS / "icon-192.svg", ASSETS / "icon-192.png", width=192)
    svg_to_png(ASSETS / "icon-512.svg", ASSETS / "icon-512.png", width=512)
    svg_to_png(ASSETS / "apple-touch-icon.svg", ASSETS / "apple-touch-icon.png", width=180)
    svg_to_png(ASSETS / "icon-192.svg", ASSETS / "favicon.png", width=64)
    print("Imagens PNG geradas em", ASSETS)
