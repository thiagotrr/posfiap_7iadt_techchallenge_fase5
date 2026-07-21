"""Regera extraction/schemas_v1.json a partir dos modelos Pydantic.

Uso:
    python -m extraction.gen_schema
"""

import json
from pathlib import Path

from extraction.schemas import ArchitectureDiagram

OUT = Path(__file__).parent / "schemas_v1.json"


def main() -> None:
    schema = ArchitectureDiagram.model_json_schema()
    OUT.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK. Schema escrito em {OUT}")


if __name__ == "__main__":
    main()
