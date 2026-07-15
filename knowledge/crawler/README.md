# Web Crawler — Épico 2

Coleta documentação pública de segurança para enriquecimento do Knowledge Graph (input do pipeline de ingestão — Épico 3).

## Stack

- `requests` — HTTP client
- `BeautifulSoup4` — extração de texto limpo
- `urllib.robotparser` — respeito a `robots.txt`

> **Nota:** `langchain_community.document_loaders` não foi adotado neste MVP. O crawler precisa de controle fino sobre profundidade, prefixo de path, rate limiting e deduplicação — `requests` + `BeautifulSoup4` já estão no `requirements.txt` e atendem o escopo acadêmico com menor overhead.

## Targets configurados

| Fonte | Provider | URL base | max_depth |
|-------|----------|----------|-----------|
| AWS Well-Architected Security Pillar | `aws` | docs.aws.amazon.com/.../welcome.html | 2 |
| Azure Security Fundamentals | `azure` | learn.microsoft.com/azure/security/fundamentals/ | 2 |
| Microsoft STRIDE Threat Categories | `microsoft` | learn.microsoft.com/azure/security/develop/ | 1 |
| OWASP Threat Modeling Cheat Sheet | `owasp` | cheatsheetseries.owasp.org/cheatsheets/ | 1 |

## Uso

```bash
# Variáveis opcionais (ver .env.example)
python scripts/run_crawler.py
```

Saída:
- Documentos em `data/crawled/{provider}/{content_hash}.json`
- Manifesto em `data/crawled/crawl_manifest.json` (handoff para ingestão)

## Variáveis de ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `KG_CRAWL_OUTPUT_DIR` | `data/crawled/` | Diretório de saída |
| `KG_CRAWL_DELAY_S` | `1.5` | Delay entre requests (segundos) |
| `KG_CRAWL_REQUEST_TIMEOUT_S` | `30` | Timeout por request |
| `KG_CRAWL_SSL_VERIFY` | `true` | Verificação SSL (`false` em dev Windows com proxy/CA corporativa) |

## Estrutura de um documento

```json
{
  "url": "https://...",
  "title": "...",
  "text_content": "...",
  "source_name": "AWS Well-Architected Security Pillar",
  "provider": "aws",
  "stride_hint": ["T", "I", "D", "E"],
  "crawled_at": "2026-07-14T22:00:00Z",
  "content_hash": "sha256...",
  "schema_version": "1"
}
```

## Comportamento

- **robots.txt:** URLs bloqueadas são ignoradas com log `WARNING`
- **Rate limiting:** `POLITENESS_DELAY_S` entre cada request
- **Deduplicação:** por `content_hash` (SHA-256 do texto limpo)
- **User-Agent:** `STRIDE-Analyzer-Academic-Crawler/1.0 (educational project)`

## Testes

```bash
pytest tests/test_crawler.py tests/test_storage.py -v
```

Testes usam mock HTTP — não requerem internet.

## Execução real (US-2.4)

Execução validada em **2026-07-15** contra fontes reais.

| Métrica | Valor |
|---------|-------|
| Data da execução | 2026-07-15T21:57:43Z |
| Total de documentos | **192** |
| Providers cobertos | `aws` (9), `azure` (60), `microsoft` (3), `owasp` (120) |
| Tamanho do corpus | ~2.601.591 caracteres |
| Tempo de execução | ~5,7 min (delay 1,5 s entre requests) |
| Testes unitários | 13/13 passando |

### Amostras verificadas manualmente

| Documento | Conteúdo relevante |
|-----------|-------------------|
| AWS Security Pillar (welcome) | Well-Architected Framework, pilares de segurança, boas práticas AWS |
| Microsoft STRIDE Threats | Modelo STRIDE, spoofing, categorias de ameaça |
| OWASP Threat Modeling | Metodologia STRIDE, DFDs, mitigações |
| Azure Security Overview | Defense-in-depth, RBAC, criptografia, DDoS |

Texto extraído legível, sem lixo HTML significativo. Algumas páginas Microsoft Learn incluem boilerplate de autenticação no topo, mas o conteúdo principal de segurança está presente.

### Páginas com problema

| Fonte | Problema | Impacto |
|-------|----------|---------|
| **AWS Security Pillar** (URL índice) | Página usa redirect JavaScript para `welcome.html`; HTML retornado tem corpo vazio | Resolvido: 9 docs coletados após apontar target para `welcome.html` |
| **SSL (Windows dev)** | `CERTIFICATE_VERIFY_FAILED` com CA padrão do Python | Todas as requests falharam até workaround |
| **OWASP** | `max_depth=1` + prefixo `/cheatsheets/` segue links do índice para ~120 cheat sheets | Corpus maior que o mínimo; conteúdo ainda é segurança válida |

### Workarounds aplicados

1. **AWS:** URL do target alterada para `welcome.html` diretamente em `config.py` (evita redirect JS).
2. **SSL:** `KG_CRAWL_SSL_VERIFY=false` no ambiente de dev + `certifi` como CA padrão em produção.
3. **OWASP:** Mantido como está — volume extra é aceitável para o MVP; filtragem por `stride_hint` na ingestão (Épico 3).

### Como reproduzir

```powershell
# Windows (se SSL falhar)
$env:KG_CRAWL_SSL_VERIFY="false"
python scripts/run_crawler.py
```

```bash
# Linux/macOS (SSL normalmente funciona)
python scripts/run_crawler.py
```
