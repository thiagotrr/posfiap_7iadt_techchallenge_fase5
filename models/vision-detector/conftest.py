import sys
from pathlib import Path

# Espelha o que predict.py já faz sozinho quando rodado direto (insere seu
# próprio diretório em sys.path pra achar `extraction/` subindo os pais) --
# aqui garante que `import predict` funcione a partir de tests/ também.
sys.path.insert(0, str(Path(__file__).resolve().parent))
