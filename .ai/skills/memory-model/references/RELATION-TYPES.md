# Tipos de Relações (Relation)

## Estrutura

```python
Relation(
    from_id: str,           # UUID da entidade origem
    relation_type: str,     # Tipo da relação (veja tabela abaixo)
    to_id: str,             # UUID da entidade destino
    strength: float,        # 0.0-1.0 (força da relação)
    polarity: float,        # -1.0 a +1.0 (negativo/neutro/positivo)
    namespace: str          # Mesmo namespace das entidades
)
```

## Tipos Padrão de Relações

| Tipo | Descrição | Exemplo | Polarity típica |
|------|-----------|---------|-----------------|
| `caused_by` | Causalidade (A causou B) | `erro caused_by bug` | 0.0 (neutro) |
| `fixed_by` | Resolução (A resolveu B) | `bug fixed_by patch` | +1.0 (positivo) |
| `part_of` | Hierarquia (A é parte de B) | `módulo part_of sistema` | 0.0 (neutro) |
| `depends_on` | Dependência (A depende de B) | `feature depends_on API` | 0.0 (neutro) |
| `interacted_with` | Interação genérica | `usuário interacted_with suporte` | 0.0 (neutro) |
| `loves` | Afeto positivo | `personagem loves outro` | +1.0 (positivo) |
| `hates` | Afeto negativo | `personagem hates inimigo` | -1.0 (negativo) |
| `created_by` | Autoria | `arquivo created_by desenvolvedor` | 0.0 (neutro) |
| `modified_by` | Modificação | `documento modified_by editor` | 0.0 (neutro) |
| `similar_to` | Similaridade | `produto_A similar_to produto_B` | 0.0 (neutro) |

## Derivação Automática de Relações

Relações são derivadas automaticamente do W5H:

| W5H | Relação Derivada |
|-----|------------------|
| `who=[A,B]` + `why="erro"` | `erro caused_by A`, `erro caused_by B` |
| `who=[A]` + `what="corrigiu bug"` | `bug fixed_by A` |
| `who=[A]` + `what="interagiu com B"` | `A interacted_with B` |

## Strength (Força) vs Polarity (Polaridade)

- **Strength**: Intensidade da relação (0=fraca, 1=forte)
  - Baseado em frequência de co-ocorrência
  - Incrementado a cada nova memória conectando as mesmas entidades

- **Polarity**: Valência emocional/causal (-1=negativo, 0=neutro, +1=positivo)
  - Baseado no tipo de relação e contexto

## Exemplos

### Causalidade
```python
Relation(
    from_id="bug_123",
    relation_type="caused_by",
    to_id="código_legado",
    strength=0.8,
    polarity=0.0
)
```

### Resolução
```python
Relation(
    from_id="erro_pagamento",
    relation_type="fixed_by",
    to_id="dev_joão",
    strength=1.0,
    polarity=+1.0
)
```

### Hierarquia
```python
Relation(
    from_id="módulo_auth",
    relation_type="part_of",
    to_id="sistema_backend",
    strength=1.0,
    polarity=0.0
)
```

## Boas Práticas

1. **Usar tipos padrão quando possível**: Facilita queries e análise de grafo
2. **Strength baseado em evidências**: Incrementar com cada co-ocorrência
3. **Polarity consistente**: Negativo para problemas, positivo para soluções
4. **Evitar relações redundantes**: Não criar `A→B` se já existe caminho indireto

## Referência de Código

- **Modelo**: `src/cortex/core/primitives/relation.py`
- **Derivação automática**: `src/cortex/services/memory_service.py::_derive_relations()`
- **Queries**: `src/cortex/core/graph/memory_graph.py::get_relations()`
