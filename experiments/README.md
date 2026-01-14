# Experimentos de Validação do Cortex

Este diretório contém experimentos isolados para validar as teorias fundamentais do Cortex **sem modificar o código do projeto**.

## Objetivo

Responder à pergunta: **"O Cortex funciona como se propõe? Pode se tornar algo grande?"**

## Experimentos

### 1. Decaimento Cognitivo ([01_test_decay.py](01_test_decay.py))

**Teoria testada:** Memórias devem decair exponencialmente seguindo a curva de Ebbinghaus.

**Testes:**
- ✅ Decaimento exponencial básico
- ✅ Proteção por acesso (spaced repetition)
- ✅ Proteção por consolidação
- ✅ Limiar de esquecimento
- ✅ Benefício de revisões espaçadas

**Resultado:** ✅ **PASSOU (100%)**

---

### 2. Economia de Tokens ([02_test_token_efficiency.py](02_test_token_efficiency.py))

**Teoria testada:** Estrutura W5H economiza tokens vs texto livre (promessa: 5x mais compacto).

**Testes:**
- ✅ Economia básica (W5H vs texto)
- ✅ Economia em múltiplos cenários
- ✅ Economia ao construir contexto para LLM
- ✅ Busca estruturada vs embedding

**Resultado:** ⚠️ **PARCIAL (50%)** - Economia real: 1.2-1.7x (não 5x)

---

### 3. Memory Firewall ([03_test_memory_firewall.py](03_test_memory_firewall.py))

**Teoria testada:** Identity Kernel detecta ataques (promessa: 90% detecção, 0% falsos positivos).

**Testes:**
- ✅ Taxa de detecção de ataques conhecidos
- ✅ Taxa de falsos positivos
- ✅ Latência de detecção
- ✅ Integração com armazenamento
- ✅ Casos extremos

**Resultado:** ✅ **PASSOU (100%)**

---

### 4. Consolidação de Memórias ([04_test_consolidation.py](04_test_consolidation.py))

**Teoria testada:** Padrões repetidos devem ser consolidados automaticamente.

**Testes:**
- ✅ Detecção de similaridade
- ✅ Consolidação de padrões
- ✅ Força da memória consolidada
- ✅ Redução de ruído
- ✅ Metadados de consolidação
- ✅ Decaimento acelerado de filhas

**Resultado:** ✅ **PASSOU (100%)**

---

### 5. Qualidade de Conversa ([05_test_conversation_quality.py](05_test_conversation_quality.py))

**Teoria testada:** Memória melhora qualidade das conversas ao longo do tempo.

**Testes:**
- ✅ Persistência de contexto entre sessões
- ❌ Evita perguntas repetitivas (threshold)
- ✅ Personalização baseada em histórico
- ✅ Aprendizado multi-sessão
- ✅ Continuidade conversacional

**Resultado:** ✅ **PASSOU (80%)**

---

### 6. Grafos e Aprendizado ([06_test_graphs_and_learning.py](06_test_graphs_and_learning.py))

**Teoria testada:** Grafos de memória são reais, sistema aprende ao longo do tempo.

**Testes:**
- ✅ Estrutura do grafo (nós + arestas)
- ✅ Detecção de hubs (nós importantes)
- ✅ Aprendizado ao longo do tempo
- ✅ Fortalecimento de relações (+166%)
- ✅ Dados para visualização (D3.js/PyVis)
- ✅ Evolução orgânica do grafo

**Resultado:** ✅ **PASSOU (100%)**

---

## Como Executar

### Executar todos os experimentos

```bash
python experiments/run_all.py
```

Gera relatório consolidado em `experiments/VALIDATION_REPORT.txt`

### Executar experimento individual

```bash
python experiments/01_test_decay.py
python experiments/02_test_token_efficiency.py
python experiments/03_test_memory_firewall.py
python experiments/04_test_consolidation.py
```

## Interpretação dos Resultados

### 100% de sucesso
🎉 **TEORIA TOTALMENTE VALIDADA**

O projeto funciona como prometido. Recomenda-se:
- Implementar testes com usuários reais
- Comparar com soluções existentes
- Medir ROI em casos de uso reais
- Publicar paper científico

### 75-99% de sucesso
✅ **TEORIA PARCIALMENTE VALIDADA**

O conceito central é sólido. Recomenda-se:
- Revisar experimentos que falharam
- Ajustar implementação onde necessário
- Executar testes adicionais

### 50-74% de sucesso
⚠️ **TEORIA PARCIALMENTE VALIDADA COM RESSALVAS**

Potencial existe mas precisa trabalho. Recomenda-se:
- Análise profunda dos pontos de falha
- Refatoração de componentes críticos
- Revisão da proposta de valor

### < 50% de sucesso
❌ **TEORIA NÃO VALIDADA**

Reavaliar fundamentos. Recomenda-se:
- Revisão completa da arquitetura
- Validação de premissas básicas
- Considerar pivots

## Princípios dos Experimentos

1. **Isolamento:** Não modificam o código principal
2. **Reprodutibilidade:** Resultados determinísticos
3. **Transparência:** Todo código visível
4. **Objetividade:** Métricas claras de sucesso/falha

## Estrutura dos Arquivos

```
experiments/
├── README.md                     # Este arquivo
├── run_all.py                    # Script principal
├── 01_test_decay.py              # Experimento 1
├── 02_test_token_efficiency.py   # Experimento 2
├── 03_test_memory_firewall.py    # Experimento 3
├── 04_test_consolidation.py      # Experimento 4
└── VALIDATION_REPORT.txt         # Relatório gerado
```

## Limitações

Estes são **experimentos controlados**, não benchmarks de produção:

- Não testam carga real de produção
- Não comparam com concorrentes diretamente
- Não medem UX de usuários reais
- Não avaliam casos extremos de escala

Para validação completa, recomenda-se:
1. Estes experimentos (validação técnica)
2. Benchmarks comparativos (vs Mem0, RAG, etc)
3. Testes com usuários (UX, ROI)
4. Deployment piloto em produção

## Contribuindo

Para adicionar novos experimentos:

1. Crie `0N_test_<nome>.py`
2. Siga estrutura: setup → testes → sumário
3. Retorne exit code 0 (sucesso) ou 1 (falha)
4. Adicione ao `run_all.py`
5. Documente no README

---

**Data de criação:** 2026-01-13
**Propósito:** Validar viabilidade técnica do Cortex de forma objetiva e transparente
