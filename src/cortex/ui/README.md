# 🧠 Cortex Control Panel - Interface Streamlit

Painel de controle moderno para visualização e gerenciamento de grafos de memória do Cortex.

## 🚀 Como Executar

### Instalação das Dependências

```bash
# Instale as dependências da UI
pip install -e ".[ui]"

# Ou instale tudo
pip install -e ".[all]"
```

### Iniciando o Painel

```bash
# Via Streamlit
streamlit run src/cortex/ui/app.py

# Ou via comando do projeto (se configurado)
cortex-ui
```

A interface será aberta automaticamente no navegador em `http://localhost:8501`

## 📋 Funcionalidades

### 🏠 Dashboard
- **Métricas em tempo real**: Entidades, episódios, relações e consolidados
- **Saúde da memória**: Score de saúde com alertas inteligentes
- **Gráficos de distribuição**: Visualização por tipo de entidade
- **Timeline de atividades**: Últimos episódios registrados
- **Top 10 nós**: Ranking por peso e importância

### 🕸️ Grafo Interativo
- **Visualização dinâmica**: Grafo interativo com networkx + agraph
- **5 algoritmos de layout**:
  - Spring (força-direcionado)
  - Kamada-Kawai (minimiza energia)
  - Shell (anéis concêntricos)
  - Radial (a partir do hub)
  - Circular
- **Controles avançados**:
  - Filtrar por tipo (entidades/episódios)
  - Ajustar peso mínimo
  - Controlar tamanho dos nós
  - Configurar espaçamento e escala
- **Interação**: Clique em nós para ver detalhes completos
- **Legenda de cores**: Cores distintas para cada tipo

### 🎯 Gerenciamento de Entidades
- **Lista completa** com filtros avançados:
  - Filtrar por tipo
  - Buscar por nome
  - Ordenar por: Peso, Nome, Data, Acessos
- **Edição inline**: Edite entidades diretamente na lista
- **Criar novas entidades**: Formulário completo com validação
- **Análise estatística**:
  - Top 10 por peso
  - Distribuição por tipo
  - Métricas de uso

### 📝 Gerenciamento de Episódios
- **Lista completa** com filtros:
  - Mostrar apenas consolidados
  - Buscar por ação/resultado
  - Ordenar por: Data, Importância, Peso
- **Criação com modelo W5H**:
  - Who (Quem): Seletor de participantes
  - What (O quê): Ação principal
  - Why (Por quê): Causa/motivação
  - When (Quando): Data/hora
  - Where (Onde): Namespace/localização
  - How (Como): Resultado/método
- **Visualização detalhada**: Todos os campos W5H + metadata
- **Deleção segura**: Confirmação obrigatória

### 🔗 Gerenciamento de Relações
- **Lista completa** com filtro por tipo
- **Visualização de triplas**: De → Tipo → Para
- **Barra de força visual**: Indicador gráfico da força da relação
- **Ações**:
  - Reforçar relação (+0.1)
  - Deletar com confirmação
- **Criação de novas relações**:
  - Seletor de origem e destino
  - Tipo customizável
  - Força inicial ajustável
  - Detecção automática de contradições

### 🔍 Busca Avançada
- **Busca textual simples**:
  - Entidades por nome
  - Episódios por ação/resultado
- **Busca contextual (Recall)**:
  - Usa embeddings semânticos
  - Algoritmos de relevância
  - Contexto compactado em YAML
  - Métricas de performance

## 🎨 Design Moderno

- **Tema dark**: Interface escura otimizada para uso prolongado
- **Cards com gradiente**: Efeitos visuais modernos
- **Animações suaves**: Transições em botões e hover
- **Layout responsivo**: Adapta-se a diferentes tamanhos de tela
- **Progress bars estilizadas**: Gradientes visuais atraentes
- **Tabs organizadas**: Navegação intuitiva

## 🗂️ Namespaces (Workspaces)

O painel suporta **múltiplos namespaces**:

- Selecione um namespace específico para trabalhar isoladamente
- Opção "Todas" para visualizar todos os namespaces mesclados
- Path do diretório de dados exibido na sidebar
- Cache inteligente para performance

## ⚡ Ações Rápidas (Sidebar)

### Estatísticas em Tempo Real
- Entidades, episódios, relações e consolidados
- Atualização automática a cada navegação

### Ferramentas Avançadas
- **Aplicar Decay**: Simula esquecimento natural
  - Fator de decay ajustável (0.8 - 0.99)
  - Mostra quantos episódios e relações foram esquecidos
- **Limpar Tudo**: Remove todas as memórias do namespace
  - Requer confirmação dupla
  - Desabilitado no modo "Todas"

## 🔧 Configurações

### Cache
- **TTL da cache de recursos**: 30 segundos
- **TTL da cache de dados**: 15 segundos
- Cache é limpo automaticamente ao recarregar

### Layout do Grafo
- **Algoritmos disponíveis**: spring, kamada_kawai, shell, radial, circular
- **Escala**: 5-50 (padrão: 20)
- **Espaçamento (k)**: 1.0-15.0 (padrão: 5.0)
- **Seed**: Controla aleatoriedade do layout

## 📊 Métricas e Estatísticas

### Dashboard
- **Total de entidades, episódios, relações**
- **Score de saúde** (0-100%):
  - 🟢 80%+: Excelente
  - 🟡 50-79%: Bom
  - 🔴 <50%: Necessita atenção
- **Importância média dos episódios**
- **Força média das relações**
- **Entidades órfãs** (sem conexões)
- **Relações fracas** (força < 0.2)

### Sistema de Alertas
- ⚠️ Entidades órfãs > 5
- ⚠️ Relações fracas > 10
- 🔴 Saúde < 50%
- 💡 Nenhum episódio registrado

## 🎯 Peso dos Nós

O **peso** de um nó é calculado baseado em:
- Número de conexões de entrada (60%)
- Número de conexões de saída (40%)
- Força média das conexões (50%)

Usado para:
- Ordenação nas listas
- Tamanho visual no grafo
- Ranking de importância

## 🔐 Segurança

- **Confirmação dupla** para ações destrutivas
- **Validação de formulários** antes de salvar
- **Proteção contra edição acidental** (modo de edição explícito)
- **Bloqueio de ferramentas** no modo "Todas"

## 🚀 Performance

- **Cache inteligente**: Reduz consultas ao grafo
- **Paginação automática**: Limita itens exibidos
- **Lazy loading**: Dados carregados sob demanda
- **Otimização de layout**: Cálculo pré-processado de posições

## 🐛 Troubleshooting

### Interface não atualiza
```bash
# Clique no botão "🔄 Atualizar" na sidebar
# Ou recarregue a página no navegador (F5)
```

### Grafo muito lento
```bash
# Aumente o peso mínimo (slider "Peso mínimo")
# Desmarque "Episódios" para mostrar só entidades
# Use layout "circular" (mais rápido que "spring")
```

### Erro ao editar
```bash
# Certifique-se que não está no modo "Todas"
# Selecione um namespace específico
```

### Memórias não aparecem
```bash
# Verifique o namespace selecionado
# Clique em "🔄 Atualizar" para limpar cache
# Verifique o path na sidebar
```

## 📝 Exemplos de Uso

### 1. Criar uma Entidade
1. Vá para "🎯 Entidades"
2. Clique na aba "➕ Criar Nova"
3. Preencha:
   - Tipo: `person`
   - Nome: `João Silva`
   - Identificadores: `joao@email.com, joao123`
4. Clique em "➕ Criar Entidade"

### 2. Criar um Episódio (W5H)
1. Vá para "📝 Episódios"
2. Clique na aba "➕ Criar Novo"
3. Preencha os campos W5H:
   - **What**: `reportou erro de login`
   - **Why**: `senha incorreta`
   - **How**: `senha redefinida com sucesso`
   - **Who**: Selecione João Silva
   - **Where**: `suporte_cliente`
4. Clique em "➕ Criar Episódio"

### 3. Visualizar o Grafo
1. Vá para "🕸️ Grafo Interativo"
2. Ajuste os controles:
   - Marque "🎯 Entidades" e "📝 Episódios"
   - Ajuste "Peso mínimo" para filtrar nós
3. Experimente diferentes layouts
4. Clique em um nó para ver detalhes

### 4. Buscar Memórias
1. Vá para "🔍 Busca Avançada"
2. Digite: `login João`
3. Clique em "🔍 Buscar com Recall"
4. Veja:
   - Entidades relacionadas
   - Episódios relevantes
   - Contexto YAML compactado
   - Métricas de busca

## 🎨 Personalização

### Cores
As cores são definidas no CSS customizado no topo do arquivo `app.py`:
- Entidades person/user: `#FF6B6B` (vermelho)
- Entidades file: `#4ECDC4` (turquesa)
- Entidades concept: `#45B7D1` (azul)
- Episódios consolidados: `#FFD700` (dourado)
- Episódios normais: `#90EE90` (verde claro)

### Tema
Para alterar o tema, edite o bloco CSS em `app.py`:
```python
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;  # Cor de fundo
    }
    /* ... mais estilos ... */
</style>
""", unsafe_allow_html=True)
```

## 🔗 Links Úteis

- [Documentação Streamlit](https://docs.streamlit.io/)
- [NetworkX Graph Layouts](https://networkx.org/documentation/stable/reference/drawing.html)
- [Streamlit-agraph](https://github.com/ChrisDelClea/streamlit-agraph)

---

**🧠 Cortex Control Panel v3.0** - Painel moderno para gerenciamento de memórias cognitivas
