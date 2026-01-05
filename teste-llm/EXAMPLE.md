# 🤖 Exemplo de Uso - Google GenAI Agent

## Quick Start

```bash
# 1. Configure API Key
export GOOGLE_API_KEY="sua-api-key-aqui"

# 2. Certifique-se que Cortex API está rodando
# (em outro terminal)
cd /home/jhony/Documentos/projetos/IA/memorias/cortex
source venv/bin/activate
uvicorn cortex.api.app:app --reload

# 3. Execute o agente
python agent.py --interactive
```

## Exemplo de Conversa

```
🚀 Iniciando Gemini Agent...
✅ Conexões validadas (Cortex + Gemini)
🤖 Modelo: gemini-2.0-flash-exp
📝 Histórico: Ativado

💬 Modo interativo (Ctrl+C para sair)
Comandos: /stats, /clear, /history, /quit

Você: Oi, meu nome é João e trabalho com Python

🤖 Gemini:
Olá João! Prazer em conhecê-lo. É ótimo saber que você trabalha com Python! 

Em que tipo de projetos você costuma usar Python?

Você: Desenvolvo APIs REST e sistemas de machine learning

🤖 Gemini:
Interessante! APIs REST e machine learning são áreas muito importantes hoje em dia.

Você usa algum framework específico para suas APIs? FastAPI, Flask, Django?

E em ML, trabalha mais com qual tipo de problema? Classificação, regressão, NLP?

Você: /stats

📊 Estatísticas Cortex:
  • Entidades: 2
  • Episódios: 2
  • Relações: 0
  • Consolidados: 0

Você: Qual é o meu nome mesmo?

🤖 Gemini:
Seu nome é João, conforme você me disse no início da nossa conversa.

Você: /quit
👋 Até logo!
```

## Como Funciona

### 1. **Function Calling Automático**

O Gemini decide automaticamente quando chamar as tools:

```python
# Tools disponíveis:
- cortex_recall(query, context)     # Busca memórias
- cortex_store(action, outcome, ...) # Armazena episódio
- cortex_stats()                     # Estatísticas
```

### 2. **Workflow Típico**

```
Mensagem do Usuário
       ↓
Gemini: cortex_recall("meu nome mesmo")
       ↓
Cortex: Retorna episódios anteriores
       ↓
Gemini: Processa contexto + gera resposta
       ↓
Gemini: cortex_store("responded_to_user", "...")
       ↓
Resposta ao Usuário
```

### 3. **Vantagens vs Ollama**

| Aspecto | Google GenAI | Ollama |
|---------|--------------|--------|
| Function Calling | Nativo | Manual |
| Qualidade | Superior | Depende do modelo |
| Custo | Pago (API) | Grátis (local) |
| Velocidade | Rápido | Depende do hardware |
| Memória | Automática via tools | Manual |

## Comandos Disponíveis

```bash
# Modo interativo padrão
python agent.py --interactive

# Mensagem única
python agent.py "Qual é a capital da França?"

# Customizar modelo
python agent.py --model gemini-2.0-flash-001 --interactive

# Desabilitar histórico de conversa
python agent.py --no-history --interactive

# Custom API Key
python agent.py --api-key SUA_CHAVE --interactive
```

## Notas Importantes

1. **API Key**: Obtenha em https://aistudio.google.com/apikey
2. **Cortex API**: Deve estar rodando em http://localhost:8000
3. **Histórico**: Mantido na sessão (use /history para limpar)
4. **Memória**: Persistente em `~/.cortex/`
5. **Custos**: Google Gemini API tem custos por uso

## Troubleshooting

### "API Key não encontrada"
```bash
export GOOGLE_API_KEY=sua-chave
# ou
python agent.py --api-key sua-chave --interactive
```

### "Cortex API não está saudável"
```bash
# Inicie o Cortex API
uvicorn cortex.api.app:app --reload
```

### "Model not found"
```bash
# Use modelo disponível
python agent.py --model gemini-2.0-flash-exp --interactive
```
