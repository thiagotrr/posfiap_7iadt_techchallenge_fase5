"""streamlit_app/validation.py

Validação client-side do upload de diagrama (US-2.2). Função pura -- sem
`streamlit`, sem I/O -- porque o `AppTest` do Streamlit não suporta
interação programática com `st.file_uploader` (limitação documentada de
`streamlit.testing`), então essa lógica precisa ser testável isoladamente.
"""
from __future__ import annotations


def validate_upload(size_bytes: int, mime_type: str, max_size_mb: int, allowed_types: list[str]) -> str | None:
    """Retorna uma mensagem de erro em português, ou `None` se o arquivo é
    válido. `mime_type` é o `uploaded_file.type` do Streamlit (ex.
    `"image/png"`); a extensão é derivada dele."""
    if size_bytes == 0:
        return "O arquivo enviado está vazio."

    extension = mime_type.split("/")[-1].lower() if "/" in mime_type else mime_type.lower()
    if extension == "jpg":
        extension = "jpeg"
    normalized_allowed = {"jpeg" if t.lower() == "jpg" else t.lower() for t in allowed_types}
    if extension not in normalized_allowed:
        return f"Tipo de arquivo '{mime_type}' não suportado. Tipos aceitos: {', '.join(allowed_types)}."

    max_size_bytes = max_size_mb * 1024 * 1024
    if size_bytes > max_size_bytes:
        size_mb = size_bytes / (1024 * 1024)
        return f"Arquivo de {size_mb:.1f}MB excede o limite de {max_size_mb}MB."

    return None
