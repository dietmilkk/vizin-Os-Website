#!/usr/bin/env python3
"""Cria o commit de publicacao da Vercel sem tocar no working tree.

O site que esta no ar (VPS) e o mesmo que vai para a Vercel, com o snippet
do Analytics. Como o working tree tem trabalho em andamento do dono do
repositorio, este script monta a arvore com um indice temporario do Git
(`GIT_INDEX_FILE`), assim nada do que esta em edicao e sobrescrito.

Uso: commitar-publicacao-vercel.py <pasta-publicada> <mensagem>
"""

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = "HEAD"

# Arquivos do HEAD que nao existem mais no site publicado (pagina /midia
# virou /documento; as imagens de etapa foram trocadas).
REMOVER = [
    "midia/index.html",
    "assets/galeria/etapa-4.svg",
    "assets/galeria/etapa-5.svg",
    "assets/galeria/vizin_screen13.png",
]


def git(*args, **kw):
    return subprocess.run(
        ["git", *args], cwd=REPO, check=True, capture_output=True, text=True, **kw
    ).stdout


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    publica = Path(sys.argv[1])
    mensagem = sys.argv[2]

    indice = Path("/tmp/idx-vercel")
    if indice.exists():
        indice.unlink()

    env = dict(os.environ, GIT_INDEX_FILE=str(indice))
    subprocess.run(["git", "read-tree", BASE], cwd=REPO, check=True, env=env)

    def set_arquivo(caminho: str, dados: bytes):
        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=REPO,
            input=dados,
            check=True,
            capture_output=True,
            env=env,
        ).stdout.decode().strip()
        subprocess.run(
            ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob},{caminho}"],
            cwd=REPO,
            check=True,
            env=env,
        )

    # 1) site publicado (com o snippet) entra no lugar
    for arquivo in sorted(publica.rglob("*")):
        if arquivo.is_dir() or arquivo.name == ".gitignore":
            continue
        set_arquivo(str(arquivo.relative_to(publica)), arquivo.read_bytes())

    # 2) o .gitignore do repo e mais rigoroso (protege .deploy-*.env): mantem o daqui
    set_arquivo(".gitignore", (REPO / ".gitignore").read_bytes())

    # 3) fora os arquivos que nao existem mais no site publicado
    for caminho in REMOVER:
        subprocess.run(
            ["git", "update-index", "--force-remove", caminho],
            cwd=REPO,
            check=False,
            env=env,
        )

    arvore = subprocess.run(
        ["git", "write-tree"], cwd=REPO, check=True, capture_output=True, text=True, env=env
    ).stdout.strip()

    commit = subprocess.run(
        ["git", "commit-tree", arvore, "-p", BASE, "-m", mensagem],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()

    print(f"commit: {commit}")
    print(f"arvore: {arvore}")
    print("--- resumo ---")
    print(git("--no-pager", "show", "--stat", "--oneline", commit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
