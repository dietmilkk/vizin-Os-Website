#!/usr/bin/env python3
"""Vasculha o repositorio em busca de segredo vazado.

O `.gitignore` resolve metade do problema: impede que arquivo de credencial
entre no repositorio. A outra metade e o segredo colado *dentro* de um arquivo
que ja e versionado (um `.js`, um `.py`, um `.html`). Isso esse script pega.

Ele le apenas o que o Git versiona (ou o que seria versionado, com
`--staged`), nunca o que esta ignorado, e sai com codigo 1 quando acha
alguma coisa.

Uso:
    python3 tools/checar-segredos.py             # arquivo por arquivo versionado
    python3 tools/checar-segredos.py --staged    # so o que entraria no commit
    python3 tools/checar-segredos.py --arquivo X # um arquivo especifico
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# (nome do grupo, regex, mensagem)
REGRAS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "chave privada",
        re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"),
        "chave privada embutida no arquivo",
    ),
    (
        "senha de app do Gmail",
        re.compile(r"\b([a-z]{4})\s([a-z]{4})\s([a-z]{4})\s([a-z]{4})\b"),
        "senha de app do Gmail (16 letras em 4 blocos) no arquivo",
    ),
    (
        "token do GitHub",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
        "token do GitHub no arquivo",
    ),
    (
        "token do Slack",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "token do Slack no arquivo",
    ),
    (
        "chave da AWS",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "chave de acesso da AWS no arquivo",
    ),
    (
        "chave da OpenAI",
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
        "chave da OpenAI no arquivo",
    ),
    (
        "token do Vercel",
        re.compile(r"\b[a-zA-Z0-9]{24}\.[a-zA-Z0-9_-]{6}\.[a-zA-Z0-9_-]{27}\b"),
        "token da Vercel no arquivo",
    ),
    (
        "senha em arquivo de configuracao",
        re.compile(
            r"(?im)^\s*(?:export\s+)?[A-Za-z0-9_]*"
            r"(?:PASS|SENHA|PASSWORD|SECRET|TOKEN|API_?KEY|PRIVATE_KEY)"
            r"[A-Za-z0-9_]*\s*[:=]\s*([\"'])([^\"'\n]{12,})\1"
        ),
        "senha/token literal em um arquivo de configuracao",
    ),
    (
        "senha em arquivo .env",
        re.compile(
            r"(?im)^\s*(?:export\s+)?[A-Za-z0-9_]*"
            r"(?:PASS|SENHA|PASSWORD|SECRET|TOKEN|API_?KEY|PRIVATE_KEY)"
            r"[A-Za-z0-9_]*\s*=\s*(?<![\"'])([^\s#\"']{12,})\s*$"
        ),
        "senha/token sem aspas em um arquivo de configuracao",
    ),
    (
        "Authorization com token",
        re.compile(r"(?i)authorization\s*[:=]\s*[\"']?(?:bearer\s+)?[A-Za-z0-9_\-.]{24,}"),
        "cabecalho Authorization com token fixo",
    ),
]

# Valores que sao placeholder, nao segredo de verdade.
FALSOS_POSITIVOS = re.compile(
    r"(?i)^(?:x{4,}|\*{4,}|\.{3,}|<[^>]+>|changeme|example|placeholder|"
    r"seu_?token|seu_?senha|meu_?token|todo|fixme|teste|test|dummy|sample|"
    r"redacted|undefined|null|none|true|false|\d+)$"
)

# Palavras que denunciam um valor de teste/placeholder dentro de um literal.
PALAVRAS_FALSAS = re.compile(
    r"(?i)(privado|privada|exemplo|example|fake|dummy|sample|placeholder|"
    r"teste|test|fixture|redacted|changeme|senha_de_app|xxxx|your|meu|meua|"
    r"aqui|vazio|empty)"
)

# Um literal que parece e-mail, IP, caminho, URL ou chamada de funcao nao e senha.
NAO_E_SENHA = re.compile(
    r"(?i)([@/\\]|[\(\)]|^https?:|^[a-z]:\\|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
    r"^\.{0,2}/|^\w+\.(js|ts|py|sh|html|css|json|md|txt|env)$)"
)

# Constante de codigo (ALLCAPS_COM_UNDERSCORE) nao e senha.
CONSTANTE_CODIGO = re.compile(r"^[A-Z][A-Z0-9]*_[A-Z0-9_]*$")

# Arquivos onde palavra "senha"/"token" aparece o tempo todo (falsos positivos).
ARQUIVOS_PERMITIDOS = re.compile(
    r"(?i)(README\.md$|\.md$|\.lock$|package-lock\.json$|yarn\.lock$)"
)

# Testes usam tokens de mentira (a API e mockada), entao a regra generica de
# "literal com cara de senha" nao se aplica ali. As regras de alta confianca
# (chave privada, token do GitHub, senha de app do Gmail) continuam valendo
# em qualquer arquivo, inclusive nos testes.
ARQUIVO_DE_TESTE = re.compile(r"(?i)(^|/)(tests?|spec)/|test[-_]|(^|/)test_")


def arquivos_versionados() -> list[str]:
    saida = subprocess.run(
        ["git", "ls-files"],
        cwd=RAIZ,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [linha for linha in saida.splitlines() if linha.strip()]


def arquivos_staged() -> list[str]:
    saida = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=RAIZ,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [linha for linha in saida.splitlines() if linha.strip()]


def checar(caminho: str) -> list[tuple[int, str, str]]:
    """Devolve [(linha, grupo, trecho)] para um arquivo."""
    arquivo = RAIZ / caminho
    if not arquivo.is_file():
        return []
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    achados: list[tuple[int, str, str]] = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if len(linha) > 4000:
            continue
        for grupo, padrao, mensagem in REGRAS:
            achado = padrao.search(linha)
            if not achado:
                continue

            valor = achado.group(0)

            if grupo == "senha de app do Gmail":
                # A senha do Gmail tem 16 letras; "xxxx xxxx xxxx xxxx" e o
                # placeholder dos docs, entao uma letra so nao conta.
                letras = {c for c in valor.lower() if c.isalpha()}
                if len(letras) <= 2:
                    continue
                if PALAVRAS_FALSAS.search(valor):
                    continue

            if grupo in ("senha em arquivo de configuracao", "senha em arquivo .env"):
                literal = achado.group(achado.lastindex)
                if ARQUIVO_DE_TESTE.search(caminho):
                    continue
                if literal.startswith(("$", "${", "`")):
                    continue
                if " " in literal or "\t" in literal:
                    continue
                if FALSOS_POSITIVOS.match(literal):
                    continue
                if PALAVRAS_FALSAS.search(literal):
                    continue
                if NAO_E_SENHA.search(literal):
                    continue
                if CONSTANTE_CODIGO.match(literal):
                    continue
                tem_classe = sum(
                    [
                        any(c.islower() for c in literal),
                        any(c.isupper() for c in literal),
                        any(c.isdigit() for c in literal),
                        any(not c.isalnum() for c in literal),
                    ]
                )
                # Uma senha de verdade costuma misturar classes de caractere;
                # uma string so com letras minúsculas so conta se for longa.
                if tem_classe < 2 and len(literal) < 16:
                    continue

            if FALSOS_POSITIVOS.match(valor.strip().strip("\"'")):
                continue
            achados.append((numero, grupo, mensagem))
    return achados


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--staged", action="store_true", help="checa so o que entraria no commit")
    analisador.add_argument("--arquivo", action="append", help="checa um arquivo especifico")
    opcoes = analisador.parse_args()

    if opcoes.arquivo:
        alvos = opcoes.arquivo
    elif opcoes.staged:
        alvos = arquivos_staged()
    else:
        alvos = arquivos_versionados()

    problemas: list[str] = []
    for caminho in alvos:
        if ARQUIVOS_PERMITIDOS.search(caminho):
            continue
        for numero, grupo, mensagem in checar(caminho):
            problemas.append(f"{caminho}:{numero}: [{grupo}] {mensagem}")

    if problemas:
        print("Segredos encontrados — o commit foi BLOQUEADO:\n")
        for problema in problemas:
            print("  " + problema)
        print(
            "\nSe isso for um falso positivo, use um valor de exemplo "
            "(exemplo/xxx/seu_token) ou ajuste a regra em tools/checar-segredos.py."
        )
        return 1

    print(f"Sem segredos nos arquivos versionados ({len(alvos)} verificados).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
