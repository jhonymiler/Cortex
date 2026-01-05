# 🧪 Teste Cortex + Ollama

Agentes de teste usando Ollama + Cortex SDK.

## 📦 Agentes Disponíveis

### 1. Agente Google GenAI (agent.py) ⭐ PRINCIPAL
Agente usando Google Gemini com function calling automático.
- **LLM**: Google Gemini 2.0 Flash
- **Tools**: Cortex integration (recall, store, stats)
- **Memória**: Cortex como tools nativas
- **Function Calling**: Automático (Gemini decide quando chamar tools)

### 2. Agente CrewAI (crew_agent.py)
Agente usando framework CrewAI com Ollama local.
- **LLM**: Ollama (customizado)
- **Framework**: CrewAI profissional
- **Memória**: Cortex via custom tools

## 📋 Pré-requisitos

### 1. Google API Key (para agent.py)

```bash
# Obtenha em: https://aistudio.google.com/apikey
export GOOGLE_API_KEY=sua-api-key-aqui
```

### 2. Cortex API Rodando

```bash
# No diretório raiz do Cortex
cd /home/jhony/Documentos/projetos/IA/memorias/cortex
source venv/bin/activate
uvicorn cortex.api.app:app --reload

# Ou
cortex-api
```

Verifique: http://localhost:8000/docs

### 3. Ollama Instalado e Rodando (para crew_agent.py)

```bash
# Verificar se Ollama está rodando
curl http://localhost:11434/api/tags

# Se não estiver rodando
ollama serve
```

### 4. Modelo Ollama Baixado (para crew_agent.py)

```bash
# Baixar modelo recomendado (3B - rápido)
ollama pull llama3.2:3b

# Ou outro modelo (opcional)
ollama pull mistral
ollama pull gemma2:2b
```

### 5. Dependências Python

```bash
# No diretório teste-llm
cd teste-llm

# Para agent.py (Google GenAI)
pip install -r requirements.txt

# Para crew_agent.py (CrewAI + Ollama)
pip install -r requirements-crew.txt
```

## 🚀 Como Usar

## 🚀 Como Usar

### Agente Google GenAI (agent.py) ⭐ RECOMENDADO

#### Modo Interativo
```bash
# Com API key como argumento
python agent.py --api-key sua-chave --interactive

# Ou com variável de ambiente
export GOOGLE_API_KEY=sua-chave
python agent.py --interactive
```

Comandos disponíveis:
- Digite mensagens normalmente para conversar
- `/stats` - Ver estatísticas da memória
- `/history` - Limpar histórico de conversa
- `/clear` - Limpar memória (com confirmação)
- `/quit` - Sair

#### Mensagem Única
```bash
python agent.py "Qual é a capital da França?"
```

#### Customizar Modelo
```bash
python agent.py --model gemini-2.0-flash-001 --interactive
```

---

### Agente CrewAI (crew_agent.py) ⭐

#### Modo Interativo
```bash
python crew_agent.py --interactive
```

#### Mensagem Única
```bash
python crew_agent.py "Me conte sobre os arquivos que analisamos antes"
```

#### Customizar Modelo
```bash
python crew_agent.py --model llama3.2:3b --interactive
```

#### Opções Completas
```bash
python crew_agent.py --help
```

## 🔄 Fluxo de Funcionamento

```
1. USUÁRIO envia mensagem
        ↓
2. AGENT chama memory.recall(query)
        ↓
3. CORTEX retorna entidades/episódios relevantes
        ↓
4. AGENT envia para Ollama com contexto
        ↓
5. OLLAMA gera resposta informada
        ↓
6. AGENT chama memory.store(episode)
        ↓
7. CORTEX armazena e consolida
```

## 📊 Exemplo de Uso

```bash
$ python agent.py

🧠 Cortex Test Agent - Modo Interativo
============================================================
Comandos especiais:
  /stats  - Ver estatísticas da memória
  /quit   - Sair
  /clear  - Limpar memória (cuidado!)
============================================================

👤 Você: Olá! Meu nome é João.

============================================================
💬 Usuário: Olá! Meu nome é João.
============================================================
🧠 [RECALL] Buscando memórias para: 'Olá! Meu nome é João.'
  ✓ Encontradas: 0 entidades, 0 episódios
🤖 [LLM] Gerando resposta com modelo 'llama3.2:3b'...
  ✓ Resposta gerada (45 caracteres)
💾 [STORE] Armazenando episódio...
  ✓ Episódio armazenado: abc123...

🤖 Assistente: Olá João! Prazer em conhecê-lo.
============================================================

👤 Você: Você lembra meu nome?

============================================================
💬 Usuário: Você lembra meu nome?
============================================================
🧠 [RECALL] Buscando memórias para: 'Você lembra meu nome?'
  ✓ Encontradas: 1 entidades, 1 episódios
🤖 [LLM] Gerando resposta com modelo 'llama3.2:3b'...
  ✓ Resposta gerada (32 caracteres)
💾 [STORE] Armazenando episódio...
  ✓ Episódio armazenado: def456...

🤖 Assistente: Sim! Você é o João.
============================================================

👤 Você: /stats

📊 Estatísticas da Memória Cortex:
  - Entidades: 1
  - Episódios: 2
  - Relações: 0
  - Episódios consolidados: 0
```

## 📊 Persistência de Memórias

As memórias são salvas em:
```
~/.cortex/           # Padrão
```

Ou configure via variável de ambiente:
```bash
export CORTEX_DATA_DIR=/caminho/customizado
```

## 🏗️ Arquitetura

### Agente Simples
- HTTP direto para Cortex e Ollama
- Sem frameworks
- Ideal para testes rápidos

### Agente CrewAI
```
┌─────────────────────────────────────┐
│         CortexCrew                  │
│  ┌───────────────────────────────┐  │
│  │  Agent (OllamaLLM)            │  │
│  │  ┌─────────────────────────┐  │  │
│  │  │ CortexRecallTool        │  │  │
│  │  │ CortexStoreTool         │  │  │
│  │  └─────────────────────────┘  │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         ↓                    ↓
    Cortex API           Ollama API
```

## 🎯 O Que Testar

1. **Memória Funciona?**
   - Converse algumas vezes
   - Pergunte algo relacionado à conversa anterior
   - Veja se o agente usa o contexto

2. **Consolidação Automática?**
   - Repita a mesma pergunta 5+ vezes
   - Execute `/stats`
   - Veja se episódios foram consolidados

3. **Busca Relevante?**
   - Converse sobre tópicos diferentes
   - Pergunte sobre um tópico específico
   - Veja se retorna o contexto certo

## 🐛 Troubleshooting

### Erro: "connection refused"
```bash
# Ollama não está rodando
ollama serve
```

### Erro: "model not found"
```bash
# Baixar o modelo
ollama pull llama3.2:3b
```

### Erro: "No module named 'cortex'"
```bash
# Instalar Cortex em modo dev
cd ..
pip install -e ".[all,dev]"
```

### LLM muito lento
```bash
# UsVia API REST**: Usa `CortexClient` SDK (HTTP) - completamente isolado do código Cortex
- **Memória em RAM**: Não persiste entre reinícios da API (usar `/stats` antes de parar servidor)
- **Single-user**: Sempre usa "test_user" como entidade
- **Prompt simples**: Para produção, melhorar engenharia de prompt
- **Testes isolados**: Pode rodar em máquina diferente do Cortex (basta apontar URL)
## 📝 Notas Técnicas

- **Sem API REST**: Usa `MemoryService` diretamente (mais rápido para testes)
- **Memória em RAM**: Não persiste entre execuções (usar `/stats` antes de sair)
- **Single-user**: Sempre usa "test_user" como entidade
- **Prompt simples**: Para produção, melhorar engenharia de prompt

## 🔧 Próximas Melhorias

- [ ] Persistência em JSON/SQLite
- [ ] Multi-usuário (identificar por nome)
- [ ] Streaming de respostas
- [ ] Interface web simples
- [ ] Logs detalhados
- [ ] Benchmark de recall/store

## 📚 Referências

- [Ollama](https://ollama.ai)
- [Cortex Architecture](../docs/ARCHITECTURE.md)
- [Cortex MCP](../docs/MCP.md)
