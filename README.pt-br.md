# Cortex

*Read this in [English](README.md).*

> **Um sistema de memória cognitiva para agentes de IA — estruturado, internacionalizado, ciente de contradições e econômico em tokens.**

O Cortex dá a um agente LLM uma memória de longo prazo *estruturada*, em vez de
um vector store plano. Cada memória é decomposta em um registro **W5H** (quem, o
quê, por quê, quando, onde, como), validada contra o que já se sabe — para que o
agente não armazene contradições silenciosamente — e recuperada por um parser
estrutural determinístico que retorna um contexto **compacto** em vez de um
amontoado de chunks crus.

É uma biblioteca Python pura com **zero dependências obrigatórias**, local-first,
projetada para entrar no loop de um agente como uma camada de memória
transparente (recall antes do turno, store depois dele).

```python
from cortext import CortexV5

cortex = CortexV5(namespace="myapp")

# Armazena uma memória estruturada (W5H)
cortex.remember(
    who=["Maria"],
    what="reportou erro de pagamento",
    why="cartão expirado",
    where="suporte",
    how="orientada a atualizar dados",
    lang="pt",
)

# Recall — retorna (contexto_compacto, RecallResult)
context, result = cortex.recall("O que Maria pediu?")
print(context)
# Maria | reportou erro de pagamento
```

## Por que memória estruturada

A maioria das memórias de agente é "embeda o turno, recupera top-k chunks". Isso
funciona até não funcionar: chunks são volumosos, o retrieval mistura fatos não
relacionados, e nada impede o store de guardar `X` e `não X` ao mesmo tempo.

O Cortex adota outra postura — memória é **informação codificada**, não mera
correlação. É construído em torno de cinco propriedades estruturais (esquema
discreto, sintaxe, mapeamento arbitrário-mas-estável para referentes externos,
intérprete independente e semântica funcional guiada pelo uso). Na prática, isso
entrega quatro coisas concretas:

| Propriedade | O que significa na prática |
|---|---|
| **Estruturado (W5H)** | O recall retorna `Maria \| reportou erro → orientada a atualizar dados`, não um chunk de 90 tokens. |
| **Normativo** | Um `CanonicalValidator` detecta contradições *na escrita* (3 níveis: heurístico → embedding → LLM-as-judge) e pode avisar ou bloquear. |
| **Internacionalizado** | O esquema W5H é neutro de idioma; só a extração é específica de idioma, e ela é plugável (regex PT/EN/ES + fallback LLM opcional). |
| **Auto-poda** | Decaimento de Ebbinghaus + forget gate + um `DreamAgent` opcional em background que faz replay, consolida duplicatas e poda o que não é mais usado. |

## Benchmarks

Reproduzível neste repositório (`python bench/run_benchmark_v5.py`), comparando o
Cortex com um baseline top-k não estruturado ("v3") em 2 cenários:

| Cenário | Tokens (baseline → Cortex) | Economia | P@5 (baseline → Cortex) | Detecção de contradição |
|---|---|---|---|---|
| customer_support | 540 → 123 | **77.2%** | 0.367 → 0.778 | 100% |
| personal_assistant | 380 → 111 | **70.8%** | 0.840 → 0.860 | 67% |
| **Média** | — | **74.0%** | **0.603 → 0.819** | 83.5% |

- **~74% menos tokens de contexto** para a mesma informação recuperada.
- **Precision@5 sobe de 0.60 para 0.82** — o recall retorna as memórias *certas*.
- **Zero falsos positivos** na detecção de contradições nos dois cenários.
- **~0.1 ms** de latência média de recall (Python puro, grafo em memória).

## Instalação

```bash
pip install cortext
```

Extras opcionais:

```bash
pip install "cortext[embeddings]"   # sentence-transformers para checagem de contradição por embedding
pip install "cortext[dev]"          # pytest, ruff
```

O Cortex roda **sem dependências extras** por padrão. Os níveis de contradição
por embedding e LLM-as-judge são opt-in.

## Documentação

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — desenho componente a componente.
- [docs/INTEGRATION.md](docs/INTEGRATION.md) — como plugar o Cortex num agente.

## Desenvolvimento

```bash
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

pytest                                  # 190+ testes
python bench/run_benchmark_v5.py        # reproduz os benchmarks
```

## Licença

MIT — veja [LICENSE](LICENSE).
