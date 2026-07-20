"""Copia o corpus mínimo versionado para data/crawled/."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "fixtures" / "sample_corpus"
TARGET = ROOT / "data" / "crawled"


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"Sample corpus not found: {SOURCE}")

    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)
    print(f"Sample corpus copied to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
