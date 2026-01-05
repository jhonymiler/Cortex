# 🔍 CME2 Feature Analysis - O que podemos adaptar para Cortex Python

> **Análise realizada em 5 de Janeiro de 2026**
> **Fonte:** `/home/jhony/Documentos/projetos/IA/memorias/CME2/`

## 📋 Sumário dos Componentes Encontrados

### 1. ✅ **ConceptExtractor** - Zero-Token Concept Extraction
**Arquivo:** `server/src/Memory/ConceptExtractor.php`

**O que faz:**
- Extrai conceitos de texto SEM usar LLM
- Remove stopwords (PT/EN)
- Detecta padrões técnicos (linguagens, frameworks, conceitos)
- Extrai n-grams compostos ("código limpo" → "codigo_limpo")
- Detecta conceitos implícitos (quando fala "eu", "meu", "prefiro")
- Detecta polaridade (positivo/negativo/neutro)

**Valor para Cortex:**
- **ALTO** - Melhoraria muito a busca sem custo de tokens
- Substitui/complementa o `similarity_score` atual

**Exemplo:**
```python
# Query: "eu prefiro Python para projetos grandes"
# Conceitos extraídos:
# - "python" (técnico)
# - "projetos_grandes" (n-gram)
# - "user" (implícito - "eu")
# - "prefers" (implícito - "prefiro")
# Polaridade: +1 (positivo)
```

---

### 2. ✅ **SemanticTriple** - Triplas Semânticas
**Arquivo:** `server/src/Memory/SemanticTriple.php`

**O que faz:**
- Estrutura: `(subject, predicate, object, polarity)`
- Exemplo: `(user, prefers, python, +1)`
- Suporte a polaridade (-1, 0, +1)
- Detecção de contradições
- Decay baseado em acesso (não tempo!)
- Consolidação por uso repetido

**Valor para Cortex:**
- **MÉDIO** - Cortex já tem Entity+Episode+Relation
- Polaridade e contradição são úteis
- Formato compacto para contexto: `+user.prefers=python`

**Possível adaptação:**
```python
# Adicionar polaridade às Relations
Relation(
    from_id="user",
    relation_type="prefers",
    to_id="python",
    polarity=1,  # +1 positivo, -1 negativo, 0 neutro
)
```

---

### 3. ✅ **MemoryCompressor** - Extração de Triplas via LLM
**Arquivo:** `server/src/Memory/MemoryCompressor.php`

**O que faz:**
- Converte conversas em triplas semânticas
- Modo offline/batch (NUNCA durante request)
- Fallback sem LLM (ConceptExtractor)
- Prompt estruturado para extração

**Valor para Cortex:**
- **BAIXO** - Cortex já faz store() via agente
- Poderia ser job de background para consolidação
- Útil para importar histórico de conversas

---

### 4. ⭐ **ProceduralMemory** - Skills e Policies
**Arquivo:** `server/src/Memory/Procedural/ProceduralMemory.php`

**O que faz:**
- **Skills**: COMO fazer tarefas (passos, contextos aplicáveis)
  - Proficiência (0-1)
  - Taxa de sucesso
  - Confiabilidade
- **Policies**: QUANDO e O QUE fazer/não fazer
  - Tipos: MUST, MUST_NOT, PREFER, SHOULD, AVOID
  - Prioridade
  - Detecção de violações

**Valor para Cortex:**
- **ALTO** - Não existe no Cortex atual
- Permitiria ensinar "como fazer" ao agente
- Policies protegem contra comportamentos indesejados

**Exemplo de uso:**
```python
# Skill aprendida
Skill(
    name="deploy_to_prod",
    steps=["run tests", "build", "push", "verify"],
    applicable_contexts=["git_repo", "ci_config"],
    proficiency=0.85,
)

# Policy de segurança
Policy(
    name="confirm_destructive",
    type="MUST",
    description="Confirmar antes de deletar",
    priority=9,
)
```

---

### 5. ⭐ **IdentityKernel** - Anti-Jailbreak + Personalidade
**Arquivo:** `server/src/Identity/IdentityKernel.php`

**O que faz:**
- Detecta padrões de jailbreak (DAN, prompt injection, etc.)
- Define persona do agente
- Valores fundamentais
- Fronteiras absolutas
- Modos: pattern (sem LLM), semantic (com LLM), hybrid

**Padrões detectados:**
- DAN attacks
- Role-play exploitation
- Prompt injection
- Encoding attacks
- Authority impersonation
- Emotional manipulation

**Valor para Cortex:**
- **ALTO** - Proteção importante para produção
- Pode ser um componente separado ou integrado

---

### 6. ✅ **WorkingMemory** - Memória de Curto Prazo
**Arquivo:** `server/src/Memory/Working/WorkingMemory.php`

**O que faz:**
- Contexto ativo da sessão (max 7±2 itens - Lei de Miller)
- GoalStack: pilha de objetivos com progresso
- ThoughtBuffer: observações, raciocínios, decisões
- Auto-limpeza de itens menos acessados

**Valor para Cortex:**
- **MÉDIO** - Cortex foca em memória de longo prazo
- Poderia complementar para sessões longas
- GoalStack útil para tarefas complexas

---

## 🎯 Recomendações de Prioridade

### Prioridade 1 (Implementar agora)
1. **ConceptExtractor** → Melhorar busca zero-token
2. **Polaridade em Relations** → Detectar contradições

### Prioridade 2 (Próxima fase)
3. **ProceduralMemory (Skills)** → Ensinar "como fazer"
4. **IdentityKernel** → Proteção anti-jailbreak

### Prioridade 3 (Futuro)
5. **ProceduralMemory (Policies)** → Regras de comportamento
6. **WorkingMemory** → Sessões longas

---

## 📊 Comparativo CME2 vs Cortex Python

| Feature | CME2 (PHP) | Cortex (Python) | Status |
|---------|------------|-----------------|--------|
| Entity/Episodic | ✅ | ✅ | Equivalente |
| Relations | ✅ | ✅ | Equivalente |
| Consolidação | ✅ | ✅ | Equivalente |
| Namespace Isolation | ✅ | ✅ | **Implementado hoje** |
| ConceptExtractor | ✅ | ❌ | **Adaptar** |
| Polaridade | ✅ | ❌ | **Adaptar** |
| SemanticTriple | ✅ | ~Episode | Similar |
| ProceduralMemory | ✅ | ❌ | **Criar** |
| IdentityKernel | ✅ | ❌ | **Criar** |
| WorkingMemory | ✅ | ❌ | Futuro |
| MCP Integration | ❌ | ✅ | Cortex melhor |
| REST API | ✅ | ✅ | Equivalente |

---

## 🚀 Próximos Passos Sugeridos

1. **Portar ConceptExtractor para Python**
   - Adaptar stopwords PT/EN
   - Adaptar patterns técnicos
   - Integrar no `recall()` para melhor busca

2. **Adicionar Polaridade às Relations**
   - Campo `polarity: int` (-1, 0, +1)
   - Método `contradicts()` para detectar conflitos
   - Atualizar formato YAML de contexto

3. **Criar módulo IdentityKernel básico**
   - Patterns de jailbreak (regex)
   - Configurável via arquivos

4. **Avaliar ProceduralMemory**
   - Decidir se Skills/Policies fazem sentido no MVP
   - Pode ser módulo separado
