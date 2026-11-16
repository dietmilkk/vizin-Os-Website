"""Deixa o aviso de primeira visita fora do caminho dos testes.

O aviso aparece uma vez por navegador (marcado em localStorage). Num
contexto novo de teste ele sempre aparece e a cortina dele bloqueia os
cliques, entao os contextos e as paginas sao semeados como se a pessoa
ja tivesse lido o aviso.

Uso:
    from lib.primeiro_acesso import ja_visitou

    contexto = navegador.new_context()
    ja_visitou(contexto)
"""

SCRIPT = """
try {
  localStorage.setItem('vizin.os.first-visit', '1');
  localStorage.removeItem('vizin-os-first-visit');
} catch (error) {}
"""


def ja_visitou(alvo):
    """Marca o aviso de primeira visita como ja visto (contexto ou pagina)."""
    alvo.add_init_script(SCRIPT)
    return alvo
