"""Mata servidores de teste que ficaram presos na porta.

Uso:
    python3 tools/limpar-servidores.py
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys

PORTAS = ["8080", "8099", "8791", "8792"]


def pids_na_porta(porta: str) -> list[str]:
    try:
        saida = subprocess.run(
            ["ss", "-ltnp"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    pids: list[str] = []
    for linha in saida.splitlines():
        if f":{porta} " not in linha:
            continue
        for pedaco in linha.split("pid=")[1:]:
            pids.append(pedaco.split(",")[0].strip())
    return pids


def main() -> int:
    for porta in PORTAS:
        for pid in pids_na_porta(porta):
            try:
                os.kill(int(pid), signal.SIGKILL)
                print(f"porta {porta}: encerrado o processo {pid}")
            except (ProcessLookupError, PermissionError, ValueError):
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
