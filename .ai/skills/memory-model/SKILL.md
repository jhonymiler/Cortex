---
name: memory-model
description: Complete reference for the W5H memory model (Who/What/Why/When/Where/How).
  Use when implementing memory creation, parsing user input into structured memories,
  validating W5H fields, or understanding entity/relation modeling. Mention when working
  with Entity, Memory, Relation classes or parsing natural language into memories.
---

# Modelo W5H de Memória

Sistema de estruturação de memórias baseado no framework jornalístico W5H estendido para decomposição de eventos em dimensões buscáveis.

## Quando Usar

- Implementar criação de memórias (parsing de texto para W5H)
- Validar campos obrigatórios/opcionais de memórias
- Entender relacionamento entre Entity, Memory, Relation
- Debugar problemas de extração de entidades ou relações
- Trabalhar com diferentes domínios (suporte técnico, dev, roleplay)

## Estrutura do Modelo W5H

| Dimensão | Tipo | Obrigatório | Descrição |
|----------|------|-------------|-----------|
| **WHO** | `list[str]` | Sim | Participantes (entidades envolvidas) — pessoas, sistemas, arquivos |
| **WHAT** | `str` | Sim | Ação principal ou fato (o que aconteceu) |
| **WHY** | `str` | Não | Causa, motivação, razão do evento |
| **WHEN** | `datetime` | Sim | Timestamp + contexto temporal opcional |
| **WHERE** | `str` | Sim | Namespace + contexto espacial opcional |
| **HOW** | `str` | Não | Resultado, método, consequência |

## Conceitos-Chave

- **Entity**: Representa agentes (pessoas, sistemas, arquivos). Tem `type`, `name`, `identifiers` (emails, paths, apelidos)
- **Memory**: Evento estruturado em W5H com metadados (`importance`, `stability`, `retrievability`, `access_count`)
- **Relation**: Conexão entre entidades (`from_id → relation_type → to_id`) com `strength` (0-1) e `polarity` (-1 a +1)
- **Namespace**: Isolamento de memórias (tenant obrigatório, sub-namespaces flexíveis)

## Fluxo de Criação de Memória

1. **Input**: Texto natural do usuário
2. **Parse W5H**: Extrair Who/What/Why/When/Where/How
3. **Entity Extraction**: Identificar participantes → criar/atualizar Entities
4. **Memory Creation**: Instanciar Memory com W5H preenchido
5. **Relation Creation**: Derivar relações causais/temporais entre entidades
6. **Validation**: IdentityKernel check (jailbreak detection)
7. **Storage**: Salvar no MemoryGraph (O(1))

## Validação de Campos

**Obrigatórios**:
- `who`: Pelo menos 1 entidade (lista não-vazia)
- `what`: String não-vazia (ação/fato)
- `when`: Timestamp válido
- `where`: Namespace válido

**Opcionais mas recomendados**:
- `why`: Essencial para causalidade (87% das queries beneficiam)
- `how`: Importante para troubleshooting (72% dos recalls técnicos)

## Exemplos por Domínio

**Suporte Técnico**:
```python
Memory(
    who=["Maria", "sistema_pagamento"],
    what="reportou erro de pagamento",
    why="cartão expirado",
    when=datetime.now(),
    where="namespace:empresa_x/suporte",
    how="foi orientada a atualizar cartão"
)
```

**Desenvolvimento**:
```python
Memory(
    who=["Dev João", "API pagamentos"],
    what="debugou timeout de requisição",
    why="conexão não fechava após erro",
    when=datetime.now(),
    where="namespace:projeto_y/backend",
    how="adicionou connection pooling e retry"
)
```

**Roleplay**:
```python
Memory(
    who=["Personagem Elena", "Templo Sagrado"],
    what="roubou amuleto mágico",
    why="precisa para ritual de proteção",
    when=datetime(2024, 3, 15, 22, 30),
    where="namespace:campanha_rpg/ato2",
    how="conseguiu escapar pela passagem secreta"
)
```

## Referências

- [W5H-REFERENCE.md](references/W5H-REFERENCE.md) — Especificação completa com tipos, constraints, edge cases
- [ENTITY-GUIDE.md](references/ENTITY-GUIDE.md) — Criar e gerenciar entidades, identifiers, tipos
- [RELATION-TYPES.md](references/RELATION-TYPES.md) — Tipos de relações (caused_by, part_of, loves, etc)
