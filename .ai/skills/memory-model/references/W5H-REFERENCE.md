# Especificação Completa do Modelo W5H

## Estrutura Detalhada

### WHO (Participantes)

**Tipo**: `list[str]`
**Obrigatório**: Sim
**Constraints**:
- Mínimo 1 elemento
- Cada string é um `entity_id` ou nome de entidade
- Pode incluir múltiplos tipos: pessoas, sistemas, arquivos, produtos

**Como extrair**:
- Sujeitos da frase
- Objetos diretos quando participantes ativos
- Sistemas/arquivos mencionados explicitamente

**Edge cases**:
- Eventos sem agente humano: usar nome do sistema (ex: `["cron_job", "banco_de_dados"]`)
- Usuário anônimo: usar `["usuário_anônimo"]` ou identificador técnico (`["user_id_12345"]`)

---

### WHAT (Ação/Fato)

**Tipo**: `str`
**Obrigatório**: Sim
**Constraints**:
- String não-vazia
- Descrever ação ou fato principal em 1-2 frases
- Preferir verbos no passado para eventos, presente para fatos contínuos

**Como extrair**:
- Verbo principal da frase + objeto
- Fato central do relato

**Edge cases**:
- Múltiplas ações: escolher a mais importante ou criar memórias separadas
- Fatos sem ação: usar estado ("estava online", "sistema em manutenção")

---

### WHY (Causa/Motivação)

**Tipo**: `str`
**Obrigatório**: Não (mas **altamente recomendado**)
**Constraints**:
- String livre ou null
- Descrever causa, razão, motivação

**Importância**:
- 87% das queries se beneficiam de causalidade
- Essencial para recall de troubleshooting
- Habilita raciocínio causal (ex: "Por que X falhou?")

**Como extrair**:
- Cláusulas com "porque", "devido a", "pois"
- Contexto inferido da situação

**Edge cases**:
- Causa desconhecida: deixar null ou "causa desconhecida (investigar)"
- Múltiplas causas: priorizar causa raiz

---

### WHEN (Timestamp)

**Tipo**: `datetime`
**Obrigatório**: Sim
**Constraints**:
- Timestamp válido ISO 8601
- Timezone-aware quando possível
- Contexto temporal opcional (ex: "durante deploy", "após migração")

**Como extrair**:
- Timestamp atual se evento real-time
- Timestamp mencionado explicitamente
- Inferir de contexto (ex: "ontem" → datetime.now() - timedelta(days=1))

**Edge cases**:
- Evento futuro: usar timestamp futuro (útil para planejamento)
- Duração/intervalo: criar memória para início e fim, ou usar `how` para descrever duração

---

### WHERE (Namespace/Contexto Espacial)

**Tipo**: `str`
**Obrigatório**: Sim
**Constraints**:
- Formato: `namespace:tenant/contexto/sub_contexto`
- Tenant obrigatório (isolamento de segurança)
- Sub-níveis flexíveis

**Como extrair**:
- Tenant do usuário atual
- Contexto de projeto/módulo/feature
- Localização física/lógica se relevante

**Edge cases**:
- Memória compartilhada entre contextos: usar namespace comum mais amplo
- Migração de namespace: manter `where` original + criar alias

---

### HOW (Resultado/Método)

**Tipo**: `str`
**Obrigatório**: Não (mas **recomendado** para troubleshooting)
**Constraints**:
- String livre ou null
- Descrever resultado, consequência, método

**Importância**:
- 72% dos recalls técnicos usam `how`
- Essencial para aprender soluções
- Permite replay de estratégias bem-sucedidas

**Como extrair**:
- Resultado final mencionado
- Método/processo usado
- Consequência do evento

**Edge cases**:
- Evento sem resolução: "sem resolução" ou "em andamento"
- Múltiplos resultados: priorizar outcome principal

---

## Metadados Adicionais (Não W5H)

Além de W5H, toda Memory tem:

| Campo | Tipo | Padrão | Descrição |
|-------|------|--------|-----------|
| `importance` | `float` | 0.5 | Score 0.0-1.0 (inferido automaticamente) |
| `stability` | `float` | 7.0 | Base de decaimento (Ebbinghaus) |
| `retrievability` | `float` | 1.0 | Score atual de recuperabilidade |
| `access_count` | `int` | 0 | Vezes acessada (incrementa em recall) |
| `consolidated` | `bool` | False | Se passou por DreamAgent |
| `embedding` | `list[float]` | null | Vector semântico (1024 dims) |

---

## Validação e Normalização

### Pipeline de Validação

1. **Campos obrigatórios**: `who` não-vazio, `what` não-vazio, `when` válido, `where` válido
2. **Tipos**: Validar tipos Pydantic
3. **Namespace**: Verificar formato e permissões de tenant
4. **IdentityKernel**: Scan para jailbreak patterns
5. **Normalização**: Limpar strings, padronizar nomes de entidades

### Erros Comuns

| Erro | Causa | Solução |
|------|-------|---------|
| `ValidationError: who is empty` | Lista `who` vazia | Adicionar pelo menos 1 entidade |
| `ValidationError: invalid namespace` | Formato errado | Usar `tenant/contexto` |
| `JailbreakDetected` | Padrão suspeito | Revisar conteúdo, sanitizar |
| `EntityNotFound` | Entidade não existe | Criar entidade antes de memória |

---

## Referências de Código

- **Modelo**: `src/cortex/core/primitives/memory.py`
- **Validação**: `src/cortex/core/processing/memory_normalizer.py`
- **Extração**: `src/cortex/services/memory_service.py::remember()`
