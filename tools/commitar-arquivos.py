#!/usr/bin/env python3
"""Cria um commit so com os arquivos indicados, sem tocar no working tree.

O repositorio costuma ter trabalho em andamento no stage (paginas, docs,
scripts). Este script monta uma arvore nova a partir do `HEAD` usando um
indice temporario do Git (`GIT_INDEX_FILE`) e sobrescreve **apenas** os
arquivos pedidos com o que esta no disco. O stage do dono do repositorio
nao e mexido em nada.

Uso:
    python3 tools/commitar-arquivos.py <arquivo> [<arquivo> ...] -m "mensagem"

Exemplo:
    python3 tools/commitar-arquivos.py .gitignore tools/checar-segredos.py \\
        -m "seg: protege o repositorio contra segredo vazado"
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = "HEAD"


def git(*args: str, env: dict | None = None) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


def main() -> int:
    argv = sys.argv[1:]
    if "-m" not in argv:
        print(__doc__)
        return 2

    corte = argv.index("-m")
    caminhos = argv[:corte]
    mensagem = argv[corte + 1]
    if not caminhos:
        print(__doc__)
        return 2

    indice = Path("/tmp/idx-commitar-arquivos")
    if indice.exists():
        indice.unlink()

    env = dict(os.environ, GIT_INDEX_FILE=str(indice))
    subprocess.run(["git", "read-tree", BASE], cwd=REPO, check=True, env=env)

    for caminho in caminhos:
        arquivo = REPO / caminho
        if not arquivo.is_file():
            print(f"ERRO: {caminho} nao existe no disco.", file=sys.stderr)
            return 1

        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=REPO,
            input=arquivo.read_bytes(),
            check=True,
            capture_output=True,
            env=env,
        ).stdout.decode().strip()

        # 100755 quando o arquivo e executavel no disco, 100644 caso contrario.
        modo = "100755" if os.access(arquivo, os.X_OK) else "100644"
        subprocess.run(
            ["git", "update-index", "--add", "--cacheinfo", f"{modo},{blob},{caminho}"],
            cwd=REPO,
            check=True,
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
    print("--- resumo ---")
    print(git("--no-pager", "show", "--stat", "--oneline", commit))
    print("Para publicar: git push origin <commit>:main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
