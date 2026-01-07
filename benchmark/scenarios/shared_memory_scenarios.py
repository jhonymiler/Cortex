"""
Cenários de Teste para Shared Memory (Memória Compartilhada).

Estes cenários testam:
1. Isolamento de dados pessoais entre usuários
2. Compartilhamento de conhecimento aprendido
3. Distinção entre "você disse" vs "aprendi que"

Casos de Uso:
- Atendimento ao Cliente: múltiplos clientes, conhecimento compartilhado
- Time de Devs: múltiplos devs, conhecimento do projeto compartilhado
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SharedMemoryScenario:
    """Cenário de teste para shared memory."""
    
    name: str
    description: str
    namespace: str  # Namespace compartilhado
    users: list[dict]  # Usuários que vão interagir
    interactions: list[dict]  # Sequência de interações
    expected_behaviors: list[dict]  # Comportamentos esperados
    
    def __post_init__(self):
        # Valida estrutura
        for user in self.users:
            assert "id" in user, "User must have 'id'"
            assert "name" in user, "User must have 'name'"
        
        for interaction in self.interactions:
            assert "user_id" in interaction, "Interaction must have 'user_id'"
            assert "message" in interaction, "Interaction must have 'message'"


# ============================================================
# CENÁRIO 1: ATENDIMENTO AO CLIENTE
# ============================================================

CUSTOMER_SUPPORT_SCENARIO = SharedMemoryScenario(
    name="customer_support_shared",
    description="Múltiplos clientes com problemas similares. Agente deve aprender padrões mas não confundir dados pessoais.",
    namespace="support_team",
    users=[
        {"id": "client_maria", "name": "Maria Silva", "email": "maria@email.com"},
        {"id": "client_joao", "name": "João Santos", "email": "joao@email.com"},
        {"id": "client_ana", "name": "Ana Costa", "email": "ana@email.com"},
    ],
    interactions=[
        # Maria tem problema de pagamento
        {
            "user_id": "client_maria",
            "session": 1,
            "message": "Olá, meu nome é Maria Silva. Estou com problema no pagamento.",
            "expected_store": {"personal": True, "contains": ["Maria Silva", "pagamento"]},
        },
        {
            "user_id": "client_maria",
            "session": 1,
            "message": "O erro diz que meu cartão foi recusado.",
            "expected_store": {"personal": True, "contains": ["cartão", "recusado"]},
        },
        {
            "user_id": "client_maria",
            "session": 1,
            "message": "Meu cartão termina em 4532.",
            "expected_store": {"personal": True, "pii": True, "contains": ["4532"]},
        },
        
        # João tem problema SIMILAR de pagamento
        {
            "user_id": "client_joao",
            "session": 1,
            "message": "Oi, sou João Santos. Não consigo pagar minha fatura.",
            "expected_store": {"personal": True, "contains": ["João Santos", "fatura"]},
        },
        {
            "user_id": "client_joao",
            "session": 1,
            "message": "Também diz que o cartão foi recusado.",
            "expected_store": {"personal": True, "pattern_detected": "payment_rejected"},
        },
        
        # Ana tem problema DIFERENTE
        {
            "user_id": "client_ana",
            "session": 1,
            "message": "Olá! Sou Ana Costa e preciso alterar meu endereço.",
            "expected_store": {"personal": True, "contains": ["Ana Costa", "endereço"]},
        },
        
        # TESTE CRÍTICO: João em nova sessão
        {
            "user_id": "client_joao",
            "session": 2,
            "message": "Oi, ainda estou com problema no pagamento.",
            "expected_recall": {
                "should_have": ["João", "cartão recusado"],  # Pessoal dele
                "should_not_have": ["Maria", "4532", "Ana"],  # Dados de outros
                "may_have": ["problema de pagamento comum"],  # Conhecimento aprendido
            },
        },
        
        # TESTE CRÍTICO: Maria em nova sessão
        {
            "user_id": "client_maria",
            "session": 2,
            "message": "Voltei, ainda com problema.",
            "expected_recall": {
                "should_have": ["Maria", "4532", "cartão recusado"],  # Pessoal dela
                "should_not_have": ["João", "Ana", "endereço"],  # Dados de outros
            },
        },
    ],
    expected_behaviors=[
        {
            "name": "personal_isolation",
            "description": "Dados pessoais não vazam entre usuários",
            "test": "client_joao não vê dados de client_maria",
        },
        {
            "name": "pattern_learning",
            "description": "Agente aprende que 'cartão recusado' é problema comum",
            "test": "Após 2+ usuários com mesmo problema, conhecimento é compartilhado",
        },
        {
            "name": "pii_protection",
            "description": "PII (número do cartão) nunca é compartilhado",
            "test": "4532 só aparece para client_maria",
        },
        {
            "name": "context_distinction",
            "description": "Agente distingue 'você disse' de 'aprendi que'",
            "test": "Usa 'você mencionou' para pessoal, 'geralmente' para aprendido",
        },
    ],
)


# ============================================================
# CENÁRIO 2: TIME DE DESENVOLVEDORES
# ============================================================

DEV_TEAM_SCENARIO = SharedMemoryScenario(
    name="dev_team_shared",
    description="Time de devs trabalhando no mesmo projeto. Conhecimento do projeto é compartilhado, mas preferências pessoais não.",
    namespace="projeto_ecommerce",
    users=[
        {"id": "dev_carlos", "name": "Carlos", "role": "backend"},
        {"id": "dev_julia", "name": "Julia", "role": "frontend"},
        {"id": "dev_pedro", "name": "Pedro", "role": "devops"},
    ],
    interactions=[
        # Carlos configura o projeto
        {
            "user_id": "dev_carlos",
            "session": 1,
            "message": "O projeto usa FastAPI no backend com PostgreSQL.",
            "expected_store": {"shared": True, "project_knowledge": True},
        },
        {
            "user_id": "dev_carlos",
            "session": 1,
            "message": "Eu prefiro usar VSCode com a extensão Python.",
            "expected_store": {"personal": True, "preference": True},
        },
        
        # Julia faz pergunta sobre arquitetura
        {
            "user_id": "dev_julia",
            "session": 1,
            "message": "Qual framework o backend usa?",
            "expected_recall": {
                "should_have": ["FastAPI", "PostgreSQL"],  # Conhecimento do projeto
                "should_not_have": ["VSCode", "extensão"],  # Preferência do Carlos
            },
        },
        {
            "user_id": "dev_julia",
            "session": 1,
            "message": "Estou implementando o componente de checkout em React.",
            "expected_store": {"shared": True, "project_knowledge": True},
        },
        
        # Pedro pergunta sobre infraestrutura
        {
            "user_id": "dev_pedro",
            "session": 1,
            "message": "Qual banco de dados estamos usando?",
            "expected_recall": {
                "should_have": ["PostgreSQL"],
                "may_have": ["FastAPI", "React", "checkout"],  # Conhecimento acumulado
            },
        },
        {
            "user_id": "dev_pedro",
            "session": 1,
            "message": "Vou configurar o deploy com Docker e Kubernetes.",
            "expected_store": {"shared": True, "project_knowledge": True},
        },
        
        # TESTE CRÍTICO: Carlos em nova sessão
        {
            "user_id": "dev_carlos",
            "session": 2,
            "message": "Qual a stack completa do projeto?",
            "expected_recall": {
                "should_have": ["FastAPI", "PostgreSQL", "React", "Docker", "Kubernetes"],
                "learned_from": ["dev_julia", "dev_pedro"],  # Conhecimento de outros
            },
        },
        
        # TESTE CRÍTICO: Julia pergunta sobre preferências
        {
            "user_id": "dev_julia",
            "session": 2,
            "message": "Qual IDE você usa?",
            "expected_recall": {
                "should_not_have": ["VSCode", "extensão Python"],  # Preferência pessoal do Carlos
            },
        },
    ],
    expected_behaviors=[
        {
            "name": "project_knowledge_sharing",
            "description": "Conhecimento técnico do projeto é compartilhado",
            "test": "Todos os devs sabem sobre FastAPI, PostgreSQL, etc.",
        },
        {
            "name": "preference_isolation",
            "description": "Preferências pessoais não são compartilhadas",
            "test": "Preferência de IDE do Carlos não aparece para Julia",
        },
        {
            "name": "accumulated_knowledge",
            "description": "Conhecimento acumula de todos os devs",
            "test": "Carlos vê conhecimento que Julia e Pedro adicionaram",
        },
        {
            "name": "attribution",
            "description": "Conhecimento compartilhado não é atribuído errado",
            "test": "Não diz 'você configurou Docker' para Carlos (foi Pedro)",
        },
    ],
)


# ============================================================
# CENÁRIO 3: EQUIPE MÉDICA (PII CRÍTICO)
# ============================================================

HEALTHCARE_TEAM_SCENARIO = SharedMemoryScenario(
    name="healthcare_team",
    description="Equipe médica atendendo pacientes. Protocolos são compartilhados, dados de pacientes são isolados.",
    namespace="clinica_saude",
    users=[
        {"id": "dr_silva", "name": "Dr. Silva", "role": "cardiologista"},
        {"id": "dr_santos", "name": "Dra. Santos", "role": "clínica geral"},
    ],
    interactions=[
        # Dr. Silva atende paciente
        {
            "user_id": "dr_silva",
            "session": 1,
            "message": "Paciente José, 65 anos, histórico de hipertensão.",
            "expected_store": {"personal": True, "pii": True, "patient_data": True},
        },
        {
            "user_id": "dr_silva",
            "session": 1,
            "message": "Prescrevi Losartana 50mg para controle da pressão.",
            "expected_store": {"personal": True, "pii": True},
        },
        
        # Dra. Santos atende outro paciente
        {
            "user_id": "dr_santos",
            "session": 1,
            "message": "Atendendo Maria, 45 anos, queixa de dores de cabeça.",
            "expected_store": {"personal": True, "pii": True, "patient_data": True},
        },
        
        # TESTE CRÍTICO: Dra. Santos NÃO deve ver dados do paciente do Dr. Silva
        {
            "user_id": "dr_santos",
            "session": 2,
            "message": "Tenho um paciente com hipertensão, qual medicação recomenda?",
            "expected_recall": {
                "should_not_have": ["José", "65 anos", "Losartana"],  # Dados do paciente do Dr. Silva
                "may_have": ["hipertensão comum", "tratamentos usuais"],  # Conhecimento médico geral
            },
        },
    ],
    expected_behaviors=[
        {
            "name": "patient_data_isolation",
            "description": "Dados de pacientes são estritamente isolados",
            "test": "Dra. Santos não vê dados dos pacientes do Dr. Silva",
        },
        {
            "name": "medical_knowledge_sharing",
            "description": "Conhecimento médico geral pode ser compartilhado",
            "test": "Protocolos e recomendações gerais são acessíveis",
        },
    ],
)


# ============================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================

def get_all_scenarios() -> list[SharedMemoryScenario]:
    """Retorna todos os cenários de shared memory."""
    return [
        CUSTOMER_SUPPORT_SCENARIO,
        DEV_TEAM_SCENARIO,
        HEALTHCARE_TEAM_SCENARIO,
    ]


def get_scenario_by_name(name: str) -> SharedMemoryScenario | None:
    """Busca cenário por nome."""
    for scenario in get_all_scenarios():
        if scenario.name == name:
            return scenario
    return None


def validate_recall_result(
    recall_result: str,
    expected: dict,
) -> dict[str, bool]:
    """
    Valida se o resultado do recall atende às expectativas.
    
    Args:
        recall_result: Texto retornado pelo recall
        expected: Dicionário com should_have, should_not_have, may_have
        
    Returns:
        Dicionário com resultados da validação
    """
    results = {}
    recall_lower = recall_result.lower()
    
    # Verifica should_have
    if "should_have" in expected:
        for item in expected["should_have"]:
            results[f"has_{item}"] = item.lower() in recall_lower
    
    # Verifica should_not_have
    if "should_not_have" in expected:
        for item in expected["should_not_have"]:
            results[f"not_has_{item}"] = item.lower() not in recall_lower
    
    return results


def calculate_scenario_score(validation_results: list[dict]) -> float:
    """
    Calcula score do cenário baseado nos resultados de validação.
    
    Returns:
        Score entre 0.0 e 1.0
    """
    total = 0
    passed = 0
    
    for result in validation_results:
        for key, value in result.items():
            total += 1
            if value:
                passed += 1
    
    return passed / total if total > 0 else 0.0


# ============================================================
# TEMPLATE PARA TESTES
# ============================================================

SHARED_MEMORY_TEST_TEMPLATE = """
## Teste de Shared Memory: {scenario_name}

### Descrição
{description}

### Usuários
{users}

### Resultados

#### Isolamento de Dados Pessoais
{isolation_results}

#### Compartilhamento de Conhecimento
{sharing_results}

#### Score Final: {score:.1%}

### Falhas Detectadas
{failures}
"""


if __name__ == "__main__":
    # Lista cenários
    print("📋 Cenários de Shared Memory disponíveis:\n")
    
    for scenario in get_all_scenarios():
        print(f"  📁 {scenario.name}")
        print(f"     {scenario.description}")
        print(f"     Usuários: {len(scenario.users)}")
        print(f"     Interações: {len(scenario.interactions)}")
        print(f"     Comportamentos esperados: {len(scenario.expected_behaviors)}")
        print()

