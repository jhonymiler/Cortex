# Cortex Benchmark

Benchmark comparativo entre agente **baseline** (sem memória) e agente **Cortex** (com memória semântica), usando **LLM real via Ollama**.

## 🎯 Objetivo

Medir quantitativamente a diferença entre:
- **Baseline**: Agente LLM padrão, cada sessão é isolada
- **Cortex**: Agente LLM com memória persistente via Cortex

## 📊 Métricas Coletadas

### Métricas Tangíveis
- **Tokens**: Total de tokens usados (prompt + completion)
- **Tempo**: Tempo de resposta, overhead de memória
- **Taxa de Hit**: % de mensagens que recuperaram memórias

### Métricas Qualitativas
- **Contexto Recuperado**: Quais memórias foram usadas
- **Consistência**: Se informações de sessões anteriores foram lembradas
- **Personalização**: Se o agente usou informações do usuário

## 🏗️ Estrutura

```
benchmark/
├── __init__.py
├── agents.py              # BaselineAgent e CortexAgent (LLM real)
├── benchmark.py           # BenchmarkRunner e MetricsEvaluator
├── conversation_generator.py  # Gerador de conversas por domínio
├── run_benchmark.py       # Script principal
├── data/                  # Dados gerados
│   └── benchmark_conversations.json
└── results/               # Resultados dos benchmarks
    └── benchmark_YYYYMMDD_HHMMSS.json
```

## 🚀 Uso

### Pré-requisitos

1. **Ollama rodando**:
```bash
ollama serve
ollama pull llama3.2:3b  # ou outro modelo
```

2. **Cortex API rodando**:
```bash
cd /path/to/cortex
source venv/bin/activate
cortex-api
```

### Executar Benchmark

```bash
# Ativar ambiente
source venv/bin/activate

# Benchmark rápido (teste)
python benchmark/run_benchmark.py --quick

# Benchmark padrão (1 conv/domínio, 3 sessões)
python benchmark/run_benchmark.py

# Benchmark completo (3 conv/domínio, 5 sessões)
python benchmark/run_benchmark.py --full

# Apenas um domínio
python benchmark/run_benchmark.py --domain education

# Configuração customizada
python benchmark/run_benchmark.py --conversations 5 --sessions 7

# Modelo diferente
python benchmark/run_benchmark.py --model llama3.1:8b
```

### Opções

```
--full              Benchmark completo (3 conv/domínio, 5 sessões)
--quick             Benchmark rápido (1 conv/domínio, 2 sessões)
--conversations N   N conversas por domínio
--sessions N        N sessões por conversa
--domain DOMAIN     Apenas um domínio específico
--model MODEL       Modelo Ollama a usar
--ollama-url URL    URL do Ollama
--cortex-url URL    URL da API Cortex
--output FILE       Arquivo de saída
--no-clear          Não limpar memória antes
--quiet             Menos output
```

## 🏛️ Domínios de Teste

8 domínios cobrindo diferentes casos de uso:

| Domínio | Descrição | Foco de Memória |
|---------|-----------|-----------------|
| customer_support | Suporte ao cliente | Nome, histórico de tickets |
| code_assistant | Assistente de código | Projeto, linguagem, decisões técnicas |
| roleplay | RPG/narrativa | Personagem, história, mundo |
| education | Tutoria/educação | Aluno, progresso, dificuldades |
| personal_assistant | Assistente pessoal | Agenda, preferências, família |
| sales_crm | Vendas/CRM | Cliente, negociação, histórico |
| healthcare | Saúde/medicação | Paciente, medicamentos, consultas |
| financial | Finanças pessoais | Investimentos, metas, perfil |

## 📈 Exemplo de Resultado

```
📊 RESUMO DO BENCHMARK
======================================================================

🔧 Configuração:
   Modelo: llama3.2:3b
   Duração: 342.5s
   Conversas: 8
   Sessões: 24
   Mensagens: 48

📝 Tokens:
   Baseline: 12,450 total (259.4 avg)
   Cortex:   14,230 total (296.5 avg)
   Overhead: +1,780 tokens (+14.3%)

⏱️ Tempo:
   Baseline: 120.3s total (2506ms avg)
   Cortex:   145.8s total (3037ms avg)
   Overhead memória: 2,340ms (recall: 1,890ms, store: 450ms)

🧠 Memória Cortex:
   Entidades recuperadas: 42
   Episódios recuperados: 67
   Taxa de hit: 78.5%
```

## 🔬 Como Funciona

### Fluxo de uma Conversa

```
1. Gera conversas simuladas por domínio
   ↓
2. Para cada conversa:
   ↓
3. Para cada sessão:
   ├─ Baseline: nova sessão (limpa histórico)
   └─ Cortex: nova sessão (mantém memória)
   ↓
4. Para cada mensagem do usuário:
   ├─ Baseline: processa com contexto da sessão
   └─ Cortex: RECALL → processa → STORE
   ↓
5. Coleta métricas de ambos
   ↓
6. Gera relatório comparativo
```

### O que o Benchmark Testa

1. **Reconhecimento de Usuário**: O Cortex lembra do nome?
2. **Continuidade**: O Cortex lembra do contexto de sessões anteriores?
3. **Preferências**: O Cortex lembra de preferências do usuário?
4. **Histórico**: O Cortex lembra de eventos passados?
5. **Consistência**: O Cortex mantém consistência entre sessões?

## 📝 Notas

- Todas as métricas são **reais** (LLM real, não simulado)
- Tokens são contados pelo Ollama via LiteLLM
- Tempos incluem latência de rede (localhost)
- O overhead do Cortex é esperado (recall + store)
- O valor está na **qualidade** das respostas, não só nos números

## 🔮 Próximos Passos

- [ ] Adicionar avaliação qualitativa automática (LLM-as-judge)
- [ ] Métricas de consistência (comparar informações entre sessões)
- [ ] Gráficos e visualizações
- [ ] Benchmark com múltiplos modelos
- [ ] Teste de carga (muitos usuários simultâneos)
