"""
Conversation Generator - Gerador de conversas simuladas para benchmark.

Gera conversas realistas para múltiplos setores:
- Suporte ao cliente
- Assistente de código
- Roleplay/RPG
- Educação/tutoria
- Assistente pessoal
- Vendas/CRM
- Saúde
- Financeiro

Cada conversa tem múltiplas sessões para testar memória de longo prazo.
"""

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class Message:
    """Uma mensagem em uma conversa."""
    role: str  # "user" ou "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Session:
    """Uma sessão de conversa (um dia/interação)."""
    id: str = field(default_factory=lambda: str(uuid4()))
    messages: list[Message] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Metadados para avaliação
    expected_recalls: list[str] = field(default_factory=list)  # O que deveria lembrar
    key_facts: list[str] = field(default_factory=list)  # Fatos importantes mencionados
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "messages": [m.to_dict() for m in self.messages],
            "timestamp": self.timestamp.isoformat(),
            "expected_recalls": self.expected_recalls,
            "key_facts": self.key_facts,
        }


@dataclass
class Conversation:
    """Uma conversa completa com múltiplas sessões."""
    id: str = field(default_factory=lambda: str(uuid4()))
    domain: str = ""
    user_profile: dict = field(default_factory=dict)
    sessions: list[Session] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "user_profile": self.user_profile,
            "sessions": [s.to_dict() for s in self.sessions],
        }


# ==================== DOMAIN GENERATORS ====================


class CustomerSupportGenerator:
    """Gerador de conversas de suporte ao cliente."""
    
    PRODUCTS = ["Plano Premium", "Plano Básico", "Addon Storage", "Addon Security", "API Access"]
    ISSUES = [
        "não consigo fazer login",
        "minha fatura veio errada",
        "quero cancelar minha assinatura",
        "como faço upgrade do plano",
        "o sistema está lento",
        "não recebi o email de confirmação",
        "preciso de nota fiscal",
        "esqueci minha senha",
    ]
    NAMES = ["Maria Silva", "João Santos", "Ana Oliveira", "Pedro Costa", "Carla Souza"]
    
    def generate(self, num_sessions: int = 5) -> Conversation:
        user_name = random.choice(self.NAMES)
        user_product = random.choice(self.PRODUCTS)
        user_email = f"{user_name.lower().replace(' ', '.')}@email.com"
        
        conv = Conversation(
            domain="customer_support",
            user_profile={
                "name": user_name,
                "email": user_email,
                "product": user_product,
                "customer_since": "2024-03-15",
            }
        )
        
        base_time = datetime.now() - timedelta(days=num_sessions * 2)
        
        for i in range(num_sessions):
            session_time = base_time + timedelta(days=i * 2)
            session = self._generate_session(i, user_name, user_product, session_time)
            conv.sessions.append(session)
        
        return conv
    
    def _generate_session(self, session_num: int, name: str, product: str, timestamp: datetime) -> Session:
        session = Session(timestamp=timestamp)
        
        if session_num == 0:
            # Primeira sessão: apresentação + problema
            issue = random.choice(self.ISSUES)
            session.messages = [
                Message("user", f"Olá, meu nome é {name} e {issue}", timestamp),
                Message("assistant", f"Olá {name}! Sou o assistente virtual e vou te ajudar com isso. "
                        f"Vejo que você é cliente do {product}. Pode me dar mais detalhes sobre o problema?", timestamp),
                Message("user", "Já tentei várias vezes mas não funciona", timestamp),
                Message("assistant", f"Entendo sua frustração, {name}. Vou verificar sua conta e resolver isso. "
                        "Pode confirmar seu email cadastrado?", timestamp),
            ]
            session.key_facts = [f"nome: {name}", f"produto: {product}", f"problema: {issue}"]
            
        elif session_num == 1:
            # Segunda sessão: follow-up
            session.messages = [
                Message("user", "Oi, voltei. Aquele problema que relatei continua.", timestamp),
                Message("assistant", f"Olá {name}! Vejo seu histórico aqui. O problema anterior foi resolvido?", timestamp),
                Message("user", "Não, ainda estou com dificuldades.", timestamp),
                Message("assistant", "Vou escalar para o time técnico. Eles entrarão em contato em até 24h.", timestamp),
            ]
            session.expected_recalls = ["nome do usuário", "problema anterior", "produto"]
            
        elif session_num == 2:
            # Terceira sessão: nova informação
            session.messages = [
                Message("user", "O técnico me ligou e resolveu! Muito obrigado.", timestamp),
                Message("assistant", f"Que ótimo, {name}! Fico feliz que resolvemos. "
                        "Posso ajudar com mais alguma coisa?", timestamp),
                Message("user", f"Sim, estou pensando em fazer upgrade para um plano maior.", timestamp),
                Message("assistant", "Excelente! Com seu histórico, posso oferecer 20% de desconto no upgrade.", timestamp),
            ]
            session.key_facts = ["problema resolvido", "interesse em upgrade"]
            session.expected_recalls = ["nome", "produto atual", "histórico de problemas"]
            
        elif session_num == 3:
            # Quarta sessão: teste de memória longa
            session.messages = [
                Message("user", "Oi, lembra de mim? Decidi fazer o upgrade.", timestamp),
                Message("assistant", f"Claro, {name}! Você tinha o {product} e estava interessado no upgrade. "
                        "Posso processar agora com o desconto de 20% que ofereci.", timestamp),
                Message("user", "Perfeito! Vamos fazer.", timestamp),
            ]
            session.expected_recalls = ["nome", "produto", "oferta de desconto", "interesse em upgrade"]
            session.key_facts = ["upgrade realizado"]
            
        else:
            # Sessões adicionais: testes variados
            topics = [
                ("preciso de ajuda com a fatura", "fatura"),
                ("como funciona o novo recurso?", "dúvida técnica"),
                ("quero indicar um amigo", "indicação"),
            ]
            topic, key = random.choice(topics)
            session.messages = [
                Message("user", f"Olá novamente! {topic}", timestamp),
                Message("assistant", f"Olá {name}! Como cliente desde março de 2024, você tem acesso a isso. "
                        "Vou te explicar...", timestamp),
            ]
            session.expected_recalls = ["nome", "tempo como cliente", "histórico"]
            session.key_facts = [key]
        
        return session


class CodeAssistantGenerator:
    """Gerador de conversas de assistente de código."""
    
    LANGUAGES = ["Python", "TypeScript", "Rust", "Go", "Java"]
    FRAMEWORKS = ["FastAPI", "React", "Django", "Next.js", "Spring"]
    PROJECT_TYPES = ["API REST", "CLI tool", "web app", "microservice", "library"]
    NAMES = ["Lucas", "Fernanda", "Ricardo", "Juliana", "Gabriel"]
    
    def generate(self, num_sessions: int = 5) -> Conversation:
        name = random.choice(self.NAMES)
        language = random.choice(self.LANGUAGES)
        framework = random.choice(self.FRAMEWORKS)
        project = random.choice(self.PROJECT_TYPES)
        
        conv = Conversation(
            domain="code_assistant",
            user_profile={
                "name": name,
                "preferred_language": language,
                "current_project": project,
                "framework": framework,
                "experience_level": random.choice(["junior", "pleno", "senior"]),
            }
        )
        
        base_time = datetime.now() - timedelta(days=num_sessions)
        
        for i in range(num_sessions):
            session_time = base_time + timedelta(days=i)
            session = self._generate_session(i, name, language, framework, project, session_time)
            conv.sessions.append(session)
        
        return conv
    
    def _generate_session(self, session_num: int, name: str, lang: str, fw: str, proj: str, timestamp: datetime) -> Session:
        session = Session(timestamp=timestamp)
        
        if session_num == 0:
            # Setup do projeto
            session.messages = [
                Message("user", f"Oi! Sou {name}, estou começando um projeto de {proj} em {lang} com {fw}.", timestamp),
                Message("assistant", f"Olá {name}! Que legal, {proj} em {lang} com {fw} é uma ótima escolha. "
                        "Posso ajudar com a estrutura inicial?", timestamp),
                Message("user", "Sim, quero seguir boas práticas desde o início.", timestamp),
                Message("assistant", f"Perfeito! Para {lang} com {fw}, recomendo a seguinte estrutura...", timestamp),
            ]
            session.key_facts = [f"dev: {name}", f"lang: {lang}", f"framework: {fw}", f"projeto: {proj}"]
            
        elif session_num == 1:
            # Bug específico
            session.messages = [
                Message("user", "Estou com um erro estranho: 'TypeError: undefined is not a function'", timestamp),
                Message("assistant", f"Esse erro em {lang}/{fw} geralmente acontece quando...", timestamp),
                Message("user", "Achei! Era um import errado.", timestamp),
                Message("assistant", "Ótimo! Dica: sempre use imports absolutos no seu projeto.", timestamp),
            ]
            session.expected_recalls = ["linguagem", "framework", "tipo de projeto"]
            session.key_facts = ["bug de import resolvido", "usar imports absolutos"]
            
        elif session_num == 2:
            # Padrão recorrente
            session.messages = [
                Message("user", "Como faço autenticação JWT nesse projeto?", timestamp),
                Message("assistant", f"Para {fw}, a melhor abordagem é usar middleware. "
                        f"Como você está fazendo {proj}, recomendo...", timestamp),
                Message("user", "E para refresh token?", timestamp),
                Message("assistant", "Use rotation com blacklist. Guardo isso para referência futura.", timestamp),
            ]
            session.expected_recalls = ["projeto", "framework", "estrutura anterior"]
            session.key_facts = ["implementou JWT", "usa refresh token rotation"]
            
        elif session_num == 3:
            # Referência a decisões anteriores
            session.messages = [
                Message("user", "Lembra daquela estrutura que definimos? Preciso adicionar testes.", timestamp),
                Message("assistant", f"Sim! Para o {proj} em {lang}, seguindo a estrutura que definimos, "
                        "os testes devem ficar em tests/ espelhando src/.", timestamp),
                Message("user", "E qual framework de teste usar?", timestamp),
                Message("assistant", f"Para {lang}, recomendo pytest. Combina bem com o {fw}.", timestamp),
            ]
            session.expected_recalls = ["estrutura definida", "linguagem", "framework", "decisões anteriores"]
            session.key_facts = ["usa pytest", "estrutura de testes definida"]
            
        else:
            # Deploy e finalização
            session.messages = [
                Message("user", "Projeto quase pronto! Como faço deploy?", timestamp),
                Message("assistant", f"Para {proj} em {fw}, recomendo Docker + Kubernetes ou Railway/Fly.io "
                        "dependendo da escala. Como está a autenticação JWT que configuramos?", timestamp),
                Message("user", "Funcionando perfeitamente com refresh token!", timestamp),
            ]
            session.expected_recalls = ["todo histórico do projeto", "decisões técnicas", "padrões definidos"]
            session.key_facts = ["projeto em fase de deploy"]
        
        return session


class RoleplayGenerator:
    """Gerador de conversas de roleplay/RPG."""
    
    SETTINGS = ["fantasia medieval", "cyberpunk", "steampunk", "horror gótico", "sci-fi espacial"]
    CHARACTERS = [
        {"name": "Elena", "class": "maga", "trait": "curiosa"},
        {"name": "Marcus", "class": "guerreiro", "trait": "honrado"},
        {"name": "Lyra", "class": "ladina", "trait": "astuta"},
        {"name": "Theron", "class": "druida", "trait": "sábio"},
    ]
    PLAYER_NAMES = ["Alex", "Sam", "Jordan", "Casey", "Morgan"]
    
    def generate(self, num_sessions: int = 5) -> Conversation:
        player = random.choice(self.PLAYER_NAMES)
        setting = random.choice(self.SETTINGS)
        char = random.choice(self.CHARACTERS)
        
        conv = Conversation(
            domain="roleplay",
            user_profile={
                "player_name": player,
                "setting": setting,
                "character": char,
                "campaign_name": f"A Saga de {char['name']}",
            }
        )
        
        base_time = datetime.now() - timedelta(days=num_sessions * 7)
        
        for i in range(num_sessions):
            session_time = base_time + timedelta(days=i * 7)
            session = self._generate_session(i, player, setting, char, session_time)
            conv.sessions.append(session)
        
        return conv
    
    def _generate_session(self, session_num: int, player: str, setting: str, char: dict, timestamp: datetime) -> Session:
        session = Session(timestamp=timestamp)
        char_name = char["name"]
        char_class = char["class"]
        
        if session_num == 0:
            # Introdução da campanha
            session.messages = [
                Message("user", f"Olá! Sou {player} e quero jogar como {char_name}, uma {char_class}.", timestamp),
                Message("assistant", f"Bem-vindo, {player}! {char_name} acorda em uma taverna decadente. "
                        f"O cenário de {setting} se desenrola à sua volta...", timestamp),
                Message("user", f"{char_name} olha ao redor procurando pistas.", timestamp),
                Message("assistant", "Você nota um homem misterioso no canto, ele segura um medalhão antigo.", timestamp),
            ]
            session.key_facts = [f"jogador: {player}", f"personagem: {char_name}", 
                               f"classe: {char_class}", f"cenário: {setting}", "medalhão misterioso"]
            
        elif session_num == 1:
            # Desenvolvimento
            session.messages = [
                Message("user", f"{char_name} se aproxima do homem misterioso.", timestamp),
                Message("assistant", f"Ele te reconhece. 'Então você é {char_name}, a {char_class} que todos falam. "
                        "Tenho uma missão para você. Este medalhão pertence à Rainha das Sombras.'", timestamp),
                Message("user", "Aceito a missão. O que preciso fazer?", timestamp),
                Message("assistant", "Ele te entrega o medalhão e um mapa. 'Leve ao Templo Esquecido ao norte.'", timestamp),
            ]
            session.expected_recalls = ["nome do personagem", "classe", "cenário", "medalhão"]
            session.key_facts = ["missão: levar medalhão ao Templo Esquecido", "Rainha das Sombras", "mapa recebido"]
            
        elif session_num == 2:
            # Conflito
            session.messages = [
                Message("user", f"{char_name} segue o mapa rumo ao norte.", timestamp),
                Message("assistant", f"Após dois dias de viagem, {char_name} encontra um grupo de bandidos. "
                        "Eles parecem estar procurando algo... ou alguém.", timestamp),
                Message("user", f"Uso minha habilidade de {char_class} para me esconder.", timestamp),
                Message("assistant", "Você ouve: 'A portadora do medalhão deve estar por perto. A Rainha quer de volta.'", timestamp),
            ]
            session.expected_recalls = ["missão", "medalhão", "destino", "personagem"]
            session.key_facts = ["bandidos procuram medalhão", "Rainha quer medalhão de volta"]
            
        elif session_num == 3:
            # Revelação
            session.messages = [
                Message("user", "Consigo passar pelos bandidos?", timestamp),
                Message("assistant", f"Sim! {char_name} usa sua astúcia e escapa. Mais adiante, "
                        "você encontra o Templo Esquecido. Uma figura etérea aparece.", timestamp),
                Message("user", "Quem é você?", timestamp),
                Message("assistant", "'Sou a verdadeira Rainha das Sombras. Aquela que enviou os bandidos é uma impostora. "
                        "O medalhão é a chave para derrotá-la.'", timestamp),
            ]
            session.expected_recalls = ["toda a jornada", "missão", "medalhão", "bandidos"]
            session.key_facts = ["duas Rainhas", "impostora", "medalhão é arma", "aliança com Rainha verdadeira"]
            
        else:
            # Clímax
            session.messages = [
                Message("user", f"{char_name} aceita ajudar a Rainha verdadeira.", timestamp),
                Message("assistant", f"A Rainha te abençoa. 'Lembre-se de tudo que aprendeu nesta jornada, {char_name}. "
                        f"Você começou como uma simples {char_class} em uma taverna, e agora é a campeã do reino.'", timestamp),
                Message("user", "Vamos derrotar a impostora!", timestamp),
            ]
            session.expected_recalls = ["toda a narrativa", "todos os personagens", "todas as decisões"]
            session.key_facts = ["momento do clímax", "arco completo do personagem"]
        
        return session


class EducationGenerator:
    """Gerador de conversas educacionais/tutoria."""
    
    SUBJECTS = ["Matemática", "Física", "Programação", "História", "Química"]
    LEVELS = ["ensino médio", "graduação", "pós-graduação"]
    TOPICS = {
        "Matemática": ["derivadas", "integrais", "matrizes", "probabilidade"],
        "Física": ["mecânica", "termodinâmica", "eletromagnetismo", "óptica"],
        "Programação": ["algoritmos", "estruturas de dados", "POO", "banco de dados"],
        "História": ["revolução francesa", "guerra fria", "Brasil colonial", "renascimento"],
        "Química": ["ligações químicas", "reações orgânicas", "equilíbrio", "eletroquímica"],
    }
    NAMES = ["Beatriz", "Henrique", "Camila", "Rafael", "Letícia"]
    
    def generate(self, num_sessions: int = 5) -> Conversation:
        name = random.choice(self.NAMES)
        subject = random.choice(self.SUBJECTS)
        level = random.choice(self.LEVELS)
        
        conv = Conversation(
            domain="education",
            user_profile={
                "student_name": name,
                "subject": subject,
                "level": level,
                "learning_style": random.choice(["visual", "prático", "teórico"]),
                "goal": "passar na prova",
            }
        )
        
        base_time = datetime.now() - timedelta(days=num_sessions * 3)
        topics = self.TOPICS.get(subject, ["tópico geral"])
        
        for i in range(num_sessions):
            session_time = base_time + timedelta(days=i * 3)
            topic = topics[i % len(topics)]
            session = self._generate_session(i, name, subject, level, topic, session_time)
            conv.sessions.append(session)
        
        return conv
    
    def _generate_session(self, session_num: int, name: str, subject: str, level: str, topic: str, timestamp: datetime) -> Session:
        session = Session(timestamp=timestamp)
        
        if session_num == 0:
            # Primeira aula - diagnóstico
            session.messages = [
                Message("user", f"Oi! Sou {name}, estou no {level} e preciso de ajuda com {subject}.", timestamp),
                Message("assistant", f"Olá {name}! Vou te ajudar com {subject}. Qual parte está mais difícil?", timestamp),
                Message("user", f"Estou tendo dificuldade com {topic}.", timestamp),
                Message("assistant", f"Entendi! Vamos começar pelo básico de {topic}. "
                        f"Como você aprende melhor: com exemplos práticos ou explicação teórica primeiro?", timestamp),
                Message("user", "Prefiro exemplos práticos!", timestamp),
            ]
            session.key_facts = [f"aluno: {name}", f"matéria: {subject}", f"nível: {level}",
                               f"dificuldade: {topic}", "aprende melhor: exemplos práticos"]
            
        elif session_num == 1:
            # Aula de aprofundamento
            session.messages = [
                Message("user", f"Voltei! Pratiquei o que você ensinou sobre {topic}.", timestamp),
                Message("assistant", f"Ótimo, {name}! Como foi? Conseguiu resolver os exercícios que sugeri?", timestamp),
                Message("user", "Alguns sim, mas ainda tenho dúvidas em um ponto.", timestamp),
                Message("assistant", f"Me mostra onde travou. Lembro que você prefere exemplos práticos, "
                        "então vou usar um caso concreto.", timestamp),
            ]
            session.expected_recalls = ["nome do aluno", "estilo de aprendizado", "tópico anterior"]
            session.key_facts = [f"progresso em {topic}", "ainda tem dúvidas"]
            
        elif session_num == 2:
            # Novo tópico relacionado
            session.messages = [
                Message("user", "Agora entendi! Podemos avançar?", timestamp),
                Message("assistant", f"Perfeito, {name}! Você dominou {topic}. "
                        f"O próximo passo em {subject} seria...", timestamp),
                Message("user", "Isso vai cair na prova?", timestamp),
                Message("assistant", f"Sim! E como você gosta de exemplos práticos, vou mostrar questões de provas anteriores.", timestamp),
            ]
            session.expected_recalls = ["progresso anterior", "estilo de aprendizado", "objetivo (prova)"]
            session.key_facts = ["tópico dominado", "preparando para prova"]
            
        elif session_num == 3:
            # Revisão pré-prova
            session.messages = [
                Message("user", "A prova é semana que vem! Estou nervoso.", timestamp),
                Message("assistant", f"{name}, você evoluiu muito desde nossa primeira aula. "
                        f"Lembra quando tinha dificuldade com {topic}? Agora você domina!", timestamp),
                Message("user", "É verdade... mas ainda preciso revisar.", timestamp),
                Message("assistant", "Vamos fazer um simulado cobrindo tudo que estudamos juntos.", timestamp),
            ]
            session.expected_recalls = ["toda evolução", "tópicos estudados", "dificuldades superadas"]
            session.key_facts = ["prova próxima", "revisão geral"]
            
        else:
            # Pós-prova
            session.messages = [
                Message("user", "PASSEI NA PROVA! Tirei 8.5!", timestamp),
                Message("assistant", f"Parabéns, {name}! Você merece! Lembro quando você começou com dificuldade "
                        f"em {topic} e agora olha só!", timestamp),
                Message("user", "Muito obrigado por toda ajuda!", timestamp),
            ]
            session.expected_recalls = ["toda jornada de aprendizado", "evolução completa"]
            session.key_facts = ["aprovado", "nota 8.5"]
        
        return session


class PersonalAssistantGenerator:
    """Gerador de conversas de assistente pessoal."""
    
    NAMES = ["Carolina", "Thiago", "Marina", "Felipe", "Amanda"]
    OCCUPATIONS = ["médica", "advogado", "empreendedor", "designer", "professor"]
    
    def generate(self, num_sessions: int = 5) -> Conversation:
        name = random.choice(self.NAMES)
        occupation = random.choice(self.OCCUPATIONS)
        
        conv = Conversation(
            domain="personal_assistant",
            user_profile={
                "name": name,
                "occupation": occupation,
                "preferences": {
                    "coffee": "expresso sem açúcar",
                    "meeting_time": "manhã",
                    "communication": "direto ao ponto",
                },
                "family": {
                    "spouse": "parceiro(a)",
                    "kids": random.randint(0, 2),
                },
            }
        )
        
        base_time = datetime.now() - timedelta(days=num_sessions)
        
        for i in range(num_sessions):
            session_time = base_time + timedelta(days=i)
            session = self._generate_session(i, name, occupation, conv.user_profile, session_time)
            conv.sessions.append(session)
        
        return conv
    
    def _generate_session(self, session_num: int, name: str, occupation: str, profile: dict, timestamp: datetime) -> Session:
        session = Session(timestamp=timestamp)
        
        if session_num == 0:
            # Primeira interação - conhecendo
            session.messages = [
                Message("user", f"Olá! Sou {name}, trabalho como {occupation}. Preciso de ajuda para me organizar.", timestamp),
                Message("assistant", f"Olá {name}! Prazer em conhecê-lo. Como {occupation}, imagino que tenha uma agenda cheia. "
                        "Quais são suas maiores dificuldades de organização?", timestamp),
                Message("user", "Esqueço compromissos e não consigo priorizar tarefas.", timestamp),
                Message("assistant", "Entendi! Vou te ajudar com lembretes e priorização. "
                        "Prefere receber lembretes pela manhã ou noite anterior?", timestamp),
                Message("user", "Pela manhã, sou mais produtivo de manhã.", timestamp),
            ]
            session.key_facts = [f"nome: {name}", f"profissão: {occupation}", 
                               "problema: esquece compromissos", "prefere manhã"]
            
        elif session_num == 1:
            # Rotina diária
            session.messages = [
                Message("user", "Bom dia! O que tenho para hoje?", timestamp),
                Message("assistant", f"Bom dia, {name}! Hoje você tem: reunião às 10h, almoço com cliente às 12h, "
                        "e relatório para entregar às 17h.", timestamp),
                Message("user", "O almoço é em qual restaurante mesmo?", timestamp),
                Message("assistant", "No Restaurante Italiano que você gosta, na Av. Paulista. "
                        "Reserva confirmada para 2 pessoas.", timestamp),
            ]
            session.expected_recalls = ["preferência por manhã", "profissão"]
            session.key_facts = ["restaurante favorito: Italiano na Paulista"]
            
        elif session_num == 2:
            # Preferências pessoais
            session.messages = [
                Message("user", "Preciso marcar médico, qual dia é melhor?", timestamp),
                Message("assistant", f"Baseado na sua agenda, {name}, sugiro terça ou quinta de manhã. "
                        "Você prefere manhãs, certo?", timestamp),
                Message("user", "Terça fica bom. Ah, marca no Dr. Santos, meu médico de sempre.", timestamp),
                Message("assistant", "Anotado! Dr. Santos, terça de manhã. Vou te lembrar segunda à noite.", timestamp),
            ]
            session.expected_recalls = ["preferência por manhã", "nome"]
            session.key_facts = ["médico: Dr. Santos", "consulta terça"]
            
        elif session_num == 3:
            # Evento especial
            kids = profile.get("family", {}).get("kids", 0)
            session.messages = [
                Message("user", "Mês que vem é aniversário do meu filho. Preciso planejar a festa.", timestamp),
                Message("assistant", f"Que legal, {name}! Vou anotar. Qual a data e quantos anos ele faz?", timestamp),
                Message("user", "Dia 15, ele faz 7 anos. Quer tema de dinossauros.", timestamp),
                Message("assistant", "Perfeito! Festa de 7 anos, tema dinossauros, dia 15. "
                        "Vou te lembrar de encomendar bolo uma semana antes.", timestamp),
            ]
            session.expected_recalls = ["informações familiares"]
            session.key_facts = ["filho faz 7 anos dia 15", "tema: dinossauros"]
            
        else:
            # Uso de memória completa
            session.messages = [
                Message("user", "Como está minha semana?", timestamp),
                Message("assistant", f"{name}, sua semana está assim: segunda reunião importante (lembra de preparar?), "
                        "terça médico com Dr. Santos, e você precisa começar a planejar a festa do seu filho!", timestamp),
                Message("user", "Você lembra de tudo!", timestamp),
                Message("assistant", "Claro! Sei que como {occupation} você tem muito na cabeça. "
                        "Estou aqui para não esquecer nada importante.", timestamp),
            ]
            session.expected_recalls = ["todos os compromissos", "preferências", "informações familiares"]
        
        return session


class SalesCRMGenerator:
    """Gerador de conversas de vendas/CRM."""
    
    COMPANIES = ["TechCorp", "InnovaLab", "DataFlow", "CloudSys", "SmartBiz"]
    CONTACTS = ["Diretor de TI", "CEO", "Gerente de Compras", "CTO", "CFO"]
    PRODUCTS = ["Enterprise Suite", "API Platform", "Analytics Pro", "Security Shield"]
    SALES_NAMES = ["Roberto", "Patrícia", "André", "Vanessa", "Marcos"]
    
    def generate(self, num_sessions: int = 5) -> Conversation:
        sales_name = random.choice(self.SALES_NAMES)
        company = random.choice(self.COMPANIES)
        contact = random.choice(self.CONTACTS)
        product = random.choice(self.PRODUCTS)
        
        conv = Conversation(
            domain="sales_crm",
            user_profile={
                "sales_person": sales_name,
                "company": company,
                "contact_role": contact,
                "contact_name": f"Dr. Silva ({contact})",
                "product_interest": product,
                "deal_value": random.randint(50, 500) * 1000,
            }
        )
        
        base_time = datetime.now() - timedelta(days=num_sessions * 5)
        
        for i in range(num_sessions):
            session_time = base_time + timedelta(days=i * 5)
            session = self._generate_session(i, sales_name, company, contact, product, session_time)
            conv.sessions.append(session)
        
        return conv
    
    def _generate_session(self, session_num: int, sales: str, company: str, contact: str, product: str, timestamp: datetime) -> Session:
        session = Session(timestamp=timestamp)
        
        if session_num == 0:
            # Primeiro contato
            session.messages = [
                Message("user", f"Tive uma call com a {company}. O {contact}, Dr. Silva, mostrou interesse no {product}.", timestamp),
                Message("assistant", f"Ótimo, {sales}! A {company} é uma boa oportunidade. "
                        f"Qual foi a principal dor que o {contact} mencionou?", timestamp),
                Message("user", "Eles estão tendo problemas de escalabilidade. O sistema atual não aguenta.", timestamp),
                Message("assistant", f"Perfeito para o {product}! Anoto: {company}, Dr. Silva ({contact}), "
                        "problema de escalabilidade. Qual o próximo passo?", timestamp),
                Message("user", "Vou mandar proposta semana que vem.", timestamp),
            ]
            session.key_facts = [f"empresa: {company}", f"contato: Dr. Silva ({contact})",
                               f"produto: {product}", "dor: escalabilidade", "próximo: proposta"]
            
        elif session_num == 1:
            # Follow-up proposta
            session.messages = [
                Message("user", f"Mandei a proposta para {company}. Aguardando retorno.", timestamp),
                Message("assistant", f"Boa! Lembro que o Dr. Silva tem dor de escalabilidade. "
                        "Destacou isso na proposta?", timestamp),
                Message("user", "Sim! Mostrei como o {product} resolve isso.", timestamp),
                Message("assistant", "Perfeito. Sugiro follow-up em 3 dias se não responderem.", timestamp),
            ]
            session.expected_recalls = ["empresa", "contato", "dor principal", "produto"]
            session.key_facts = ["proposta enviada", "aguardando retorno"]
            
        elif session_num == 2:
            # Objeção
            session.messages = [
                Message("user", f"Dr. Silva respondeu. Gostou mas achou caro.", timestamp),
                Message("assistant", f"Objeção de preço é comum. Lembra que a {company} tem problema de escalabilidade? "
                        "Quanto estão perdendo por mês com o sistema atual travando?", timestamp),
                Message("user", "Boa pergunta! Vou levantar isso com ele.", timestamp),
                Message("assistant", f"Isso! Mostre ROI. Se perdem R$50k/mês, o {product} se paga rapidinho.", timestamp),
            ]
            session.expected_recalls = ["histórico completo da negociação", "dor do cliente"]
            session.key_facts = ["objeção: preço", "estratégia: ROI"]
            
        elif session_num == 3:
            # Negociação
            session.messages = [
                Message("user", f"Consegui! A {company} perde R$80k/mês com downtime. Dr. Silva ficou impressionado.", timestamp),
                Message("assistant", f"Excelente, {sales}! Com R$80k/mês de prejuízo, o {product} tem ROI em 2 meses! "
                        "Como está a negociação?", timestamp),
                Message("user", "Eles querem 15% de desconto.", timestamp),
                Message("assistant", "Podemos oferecer 10% + suporte premium grátis por 6 meses. Valor percebido maior.", timestamp),
            ]
            session.expected_recalls = ["todo o histórico", "valores", "objeções anteriores"]
            session.key_facts = ["prejuízo: R$80k/mês", "pedido: 15% desconto", "contraproposta: 10% + suporte"]
            
        else:
            # Fechamento
            session.messages = [
                Message("user", f"FECHAMOS! {company} assinou contrato do {product}!", timestamp),
                Message("assistant", f"Parabéns, {sales}! Que jornada! Desde o primeiro contato quando identificamos "
                        "a dor de escalabilidade até agora. Dr. Silva vai adorar o ROI!", timestamp),
                Message("user", "Valeu! Você lembrou de tudo!", timestamp),
            ]
            session.expected_recalls = ["toda a jornada de venda", "todas as interações"]
            session.key_facts = ["DEAL FECHADO"]
        
        return session


class HealthcareGenerator:
    """Gerador de conversas de saúde (assistente de paciente)."""
    
    NAMES = ["Dona Maria", "Sr. José", "Ana Paula", "Carlos Alberto", "Helena"]
    CONDITIONS = ["diabetes", "hipertensão", "acompanhamento geral", "pós-cirúrgico", "gestante"]
    
    def generate(self, num_sessions: int = 5) -> Conversation:
        name = random.choice(self.NAMES)
        condition = random.choice(self.CONDITIONS)
        
        conv = Conversation(
            domain="healthcare",
            user_profile={
                "patient_name": name,
                "condition": condition,
                "medications": ["Medicamento A", "Medicamento B"],
                "doctor": "Dr. Fernandes",
                "next_appointment": "próxima segunda",
            }
        )
        
        base_time = datetime.now() - timedelta(days=num_sessions * 7)
        
        for i in range(num_sessions):
            session_time = base_time + timedelta(days=i * 7)
            session = self._generate_session(i, name, condition, session_time)
            conv.sessions.append(session)
        
        return conv
    
    def _generate_session(self, session_num: int, name: str, condition: str, timestamp: datetime) -> Session:
        session = Session(timestamp=timestamp)
        
        if session_num == 0:
            # Primeira consulta
            session.messages = [
                Message("user", f"Olá, sou {name}. Preciso de ajuda para lembrar meus remédios.", timestamp),
                Message("assistant", f"Olá {name}! Claro, vou te ajudar. Qual sua condição de saúde?", timestamp),
                Message("user", f"Tenho {condition}. Tomo Medicamento A de manhã e B à noite.", timestamp),
                Message("assistant", f"Anotado! {condition}, Medicamento A manhã, B noite. "
                        "Quer que eu te lembre nos horários?", timestamp),
                Message("user", "Sim, por favor! Às vezes esqueço.", timestamp),
            ]
            session.key_facts = [f"paciente: {name}", f"condição: {condition}", 
                               "medicamentos: A manhã, B noite", "precisa de lembretes"]
            
        elif session_num == 1:
            # Rotina de medicação
            session.messages = [
                Message("user", "Bom dia! Já tomei o remédio.", timestamp),
                Message("assistant", f"Bom dia, {name}! Ótimo que tomou o Medicamento A. "
                        "Como está se sentindo hoje?", timestamp),
                Message("user", "Um pouco cansada, mas bem.", timestamp),
                Message("assistant", f"Cansaço pode ser efeito do {condition}. Está se hidratando bem?", timestamp),
            ]
            session.expected_recalls = ["nome", "condição", "medicamentos"]
            session.key_facts = ["sintoma: cansaço"]
            
        elif session_num == 2:
            # Dúvida sobre efeitos
            session.messages = [
                Message("user", "Posso tomar o Medicamento A junto com café?", timestamp),
                Message("assistant", f"{name}, é melhor evitar café 30 minutos antes e depois do Medicamento A. "
                        "A cafeína pode reduzir a absorção.", timestamp),
                Message("user", "Não sabia! Obrigada.", timestamp),
                Message("assistant", f"Por nada! Qualquer dúvida sobre seu tratamento para {condition}, me pergunte.", timestamp),
            ]
            session.expected_recalls = ["medicamentos", "condição"]
            session.key_facts = ["evitar café com Medicamento A"]
            
        elif session_num == 3:
            # Lembrete de consulta
            session.messages = [
                Message("user", "Quando é minha consulta mesmo?", timestamp),
                Message("assistant", f"{name}, sua consulta com Dr. Fernandes é próxima segunda às 14h. "
                        "Precisa levar os exames de sangue.", timestamp),
                Message("user", "Ah sim! Quase esqueci dos exames.", timestamp),
                Message("assistant", "Vou te lembrar no domingo para separar os exames!", timestamp),
            ]
            session.expected_recalls = ["médico", "consulta", "exames"]
            session.key_facts = ["consulta segunda 14h", "levar exames"]
            
        else:
            # Acompanhamento geral
            session.messages = [
                Message("user", "A consulta foi ótima! Dr. Fernandes disse que estou melhorando.", timestamp),
                Message("assistant", f"Que maravilha, {name}! Lembro quando você começou a acompanhar seu {condition} "
                        "e às vezes esquecia os remédios. Agora está super organizada!", timestamp),
                Message("user", "Verdade! Muito obrigada pela ajuda.", timestamp),
            ]
            session.expected_recalls = ["toda evolução", "histórico de medicação", "consultas"]
            session.key_facts = ["melhora no quadro"]
        
        return session


class FinancialGenerator:
    """Gerador de conversas de assistente financeiro."""
    
    NAMES = ["Eduardo", "Priscila", "Rodrigo", "Isabela", "Gustavo"]
    GOALS = ["aposentadoria", "casa própria", "viagem", "emergência", "educação dos filhos"]
    
    def generate(self, num_sessions: int = 5) -> Conversation:
        name = random.choice(self.NAMES)
        goal = random.choice(self.GOALS)
        monthly_income = random.randint(5, 30) * 1000
        
        conv = Conversation(
            domain="financial",
            user_profile={
                "name": name,
                "goal": goal,
                "monthly_income": monthly_income,
                "risk_profile": random.choice(["conservador", "moderado", "arrojado"]),
                "current_savings": random.randint(10, 100) * 1000,
            }
        )
        
        base_time = datetime.now() - timedelta(days=num_sessions * 30)
        
        for i in range(num_sessions):
            session_time = base_time + timedelta(days=i * 30)
            session = self._generate_session(i, name, goal, monthly_income, conv.user_profile, session_time)
            conv.sessions.append(session)
        
        return conv
    
    def _generate_session(self, session_num: int, name: str, goal: str, income: int, profile: dict, timestamp: datetime) -> Session:
        session = Session(timestamp=timestamp)
        risk = profile.get("risk_profile", "moderado")
        
        if session_num == 0:
            # Primeiro planejamento
            session.messages = [
                Message("user", f"Olá! Sou {name}, ganho R${income:,}/mês e quero juntar para {goal}.", timestamp),
                Message("assistant", f"Olá {name}! Meta de {goal} é muito importante. "
                        "Qual seu perfil de risco: conservador, moderado ou arrojado?", timestamp),
                Message("user", f"Sou {risk}.", timestamp),
                Message("assistant", f"Perfeito! Para {goal} com perfil {risk}, recomendo: "
                        f"30% renda fixa, 50% multimercado, 20% ações. Quanto pode investir por mês?", timestamp),
                Message("user", "Consigo R$2.000 por mês.", timestamp),
            ]
            session.key_facts = [f"investidor: {name}", f"meta: {goal}", f"renda: R${income:,}",
                               f"perfil: {risk}", "aporte: R$2.000/mês"]
            
        elif session_num == 1:
            # Primeiro mês de investimento
            session.messages = [
                Message("user", "Fiz meu primeiro aporte! R$2.000 como combinamos.", timestamp),
                Message("assistant", f"Parabéns, {name}! Primeiro passo para {goal} dado! "
                        f"Com aporte mensal de R$2.000 e perfil {risk}, em 5 anos você terá aproximadamente R$150.000.", timestamp),
                Message("user", "Será que dá pra acelerar?", timestamp),
                Message("assistant", "Se aumentar para R$3.000/mês, alcança em 3.5 anos!", timestamp),
            ]
            session.expected_recalls = ["meta", "perfil de risco", "aporte"]
            session.key_facts = ["primeiro aporte feito", "projeção: R$150k em 5 anos"]
            
        elif session_num == 2:
            # Ajuste de carteira
            session.messages = [
                Message("user", "O mercado caiu essa semana. Devo me preocupar?", timestamp),
                Message("assistant", f"{name}, com seu perfil {risk}, oscilações são esperadas. "
                        f"Sua meta é {goal} - pense no longo prazo.", timestamp),
                Message("user", "Verdade, não devo entrar em pânico.", timestamp),
                Message("assistant", "Exato! Na verdade, quedas são oportunidade de comprar mais barato.", timestamp),
            ]
            session.expected_recalls = ["perfil de risco", "meta de longo prazo"]
            session.key_facts = ["orientação sobre volatilidade", "manter estratégia"]
            
        elif session_num == 3:
            # Revisão trimestral
            session.messages = [
                Message("user", "Como está minha carteira?", timestamp),
                Message("assistant", f"{name}, em 3 meses você acumulou R$6.500 (aportes + rendimento). "
                        f"Está no caminho certo para {goal}!", timestamp),
                Message("user", "Boa! Alguma sugestão de ajuste?", timestamp),
                Message("assistant", f"Para perfil {risk}, sugiro rebalancear: ações subiram muito, venda um pouco e compre renda fixa.", timestamp),
            ]
            session.expected_recalls = ["todo histórico financeiro", "aportes", "meta", "perfil"]
            session.key_facts = ["patrimônio: R$6.500", "sugestão: rebalanceamento"]
            
        else:
            # Progresso de longo prazo
            session.messages = [
                Message("user", "6 meses de investimento! Como estamos?", timestamp),
                Message("assistant", f"Parabéns, {name}! Você já tem R$13.200! "
                        f"Está 8% à frente do planejado para {goal}. Seu perfil {risk} está funcionando!", timestamp),
                Message("user", "Incrível ver a evolução!", timestamp),
                Message("assistant", f"Lembro quando você começou com a meta de {goal}. Continue assim!", timestamp),
            ]
            session.expected_recalls = ["toda evolução", "aportes", "rendimentos", "meta original"]
            session.key_facts = ["patrimônio: R$13.200", "8% acima do planejado"]
        
        return session


# ==================== COLLECTIVE SCENARIOS ====================


class CollectiveScenarioGenerator:
    """
    Gerador de cenários coletivos para testar memória compartilhada.
    
    Cria múltiplos usuários com problemas similares no mesmo domínio,
    permitindo testar:
    1. Isolamento de memórias pessoais
    2. Compartilhamento de conhecimento LEARNED
    3. Extração de padrões procedurais
    """
    
    def generate_support_collective(self, num_users: int = 3) -> list[Conversation]:
        """
        Gera conversas de suporte com problema similar para testar memória coletiva.
        
        Usuário 1: Reporta problema e resolve (cria conhecimento)
        Usuário 2: Reporta mesmo problema (deve receber conhecimento LEARNED)
        Usuário 3: Problema diferente (isolamento)
        """
        conversations = []
        
        # Problema comum: timeout de API
        common_problem = "timeout na API"
        common_solution = "aumentar timeout para 30s e verificar connection pooling"
        
        users = [
            {"name": "Pedro Costa", "id": "pedro_costa", "role": "first_reporter"},
            {"name": "Maria Silva", "id": "maria_silva", "role": "second_reporter"},
            {"name": "João Santos", "id": "joao_santos", "role": "different_problem"},
        ]
        
        for i, user in enumerate(users[:num_users]):
            conv = Conversation(
                domain="customer_support",
                user_profile={
                    "name": user["name"],
                    "id": user["id"],
                    "product": "Plano Enterprise",
                    "role_in_test": user["role"],
                }
            )
            
            if user["role"] == "first_reporter":
                # Primeiro a reportar e resolver
                session1 = Session()
                session1.messages = [
                    Message("user", f"Olá, sou {user['name']}. Estou tendo {common_problem}!"),
                    Message("assistant", f"Olá {user['name']}! Vou verificar. Pode descrever melhor o erro?"),
                    Message("user", "A integração dá timeout depois de 10 segundos, mas as vezes demora mais."),
                    Message("assistant", "Entendi. O timeout padrão é 10s. Sugiro aumentar para 30s nas configurações."),
                ]
                session1.key_facts = [f"usuário: {user['name']}", f"problema: {common_problem}"]
                
                session2 = Session()
                session2.messages = [
                    Message("user", f"Funcionou! Aumentei o timeout e também verifiquei o connection pooling."),
                    Message("assistant", f"Ótimo, {user['name']}! Fico feliz que resolveu. Essa é uma dica importante."),
                ]
                session2.key_facts = [f"solução: {common_solution}"]
                
                conv.sessions = [session1, session2]
                
            elif user["role"] == "second_reporter":
                # Segundo usuário - deve receber conhecimento do primeiro
                session = Session()
                session.messages = [
                    Message("user", f"Olá, sou {user['name']}. Também estou com {common_problem}."),
                    Message("assistant", f"Olá {user['name']}! Esse é um problema comum. Já tentou aumentar o timeout?"),
                ]
                session.expected_recalls = ["solução anterior", "timeout", "connection pooling"]
                conv.sessions = [session]
                
            else:
                # Problema diferente - isolamento
                session = Session()
                session.messages = [
                    Message("user", f"Olá, sou {user['name']}. Quero fazer upgrade do meu plano."),
                    Message("assistant", f"Olá {user['name']}! Claro, posso ajudar com o upgrade."),
                ]
                session.expected_recalls = []  # Não deve ver memórias de timeout
                conv.sessions = [session]
            
            conversations.append(conv)
        
        return conversations
    
    def generate_education_collective(self, num_users: int = 3) -> list[Conversation]:
        """
        Gera conversas educacionais com dúvidas similares.
        """
        conversations = []
        
        common_topic = "derivadas"
        common_approach = "pensar como velocidade instantânea, usar exemplos práticos"
        
        users = [
            {"name": "Letícia", "id": "leticia", "role": "first_learner"},
            {"name": "Rafael", "id": "rafael", "role": "second_learner"},
            {"name": "Camila", "id": "camila", "role": "different_subject"},
        ]
        
        for user in users[:num_users]:
            conv = Conversation(
                domain="education",
                user_profile={
                    "student_name": user["name"],
                    "id": user["id"],
                    "subject": "Cálculo" if user["role"] != "different_subject" else "História",
                    "role_in_test": user["role"],
                }
            )
            
            if user["role"] == "first_learner":
                session1 = Session()
                session1.messages = [
                    Message("user", f"Oi, sou {user['name']}. Não entendo {common_topic}!"),
                    Message("assistant", f"Olá {user['name']}! Derivadas podem ser difíceis. Como você aprende melhor?"),
                    Message("user", "Prefiro exemplos práticos."),
                    Message("assistant", "Ótimo! Pense em velocidade: a derivada é a velocidade instantânea."),
                ]
                
                session2 = Session()
                session2.messages = [
                    Message("user", "Entendi! Pensar como velocidade ajudou muito!"),
                    Message("assistant", f"Que bom, {user['name']}! Essa analogia funciona muito bem."),
                ]
                session2.key_facts = [common_approach]
                
                conv.sessions = [session1, session2]
                
            elif user["role"] == "second_learner":
                session = Session()
                session.messages = [
                    Message("user", f"Sou {user['name']}, também preciso de ajuda com {common_topic}."),
                    Message("assistant", f"Olá {user['name']}! Uma dica que funciona: pense como velocidade."),
                ]
                session.expected_recalls = ["velocidade instantânea", "exemplos práticos"]
                conv.sessions = [session]
                
            else:
                session = Session()
                session.messages = [
                    Message("user", f"Sou {user['name']}, preciso estudar Revolução Francesa."),
                    Message("assistant", f"Olá {user['name']}! Vamos estudar a Revolução Francesa."),
                ]
                conv.sessions = [session]
            
            conversations.append(conv)
        
        return conversations


# ==================== MAIN GENERATOR ====================


class ConversationGenerator:
    """Gerador principal que cria conversas para todos os domínios."""
    
    GENERATORS = {
        "customer_support": CustomerSupportGenerator,
        "code_assistant": CodeAssistantGenerator,
        "roleplay": RoleplayGenerator,
        "education": EducationGenerator,
        "personal_assistant": PersonalAssistantGenerator,
        "sales_crm": SalesCRMGenerator,
        "healthcare": HealthcareGenerator,
        "financial": FinancialGenerator,
    }
    
    # Gerador de cenários coletivos
    COLLECTIVE_GENERATOR = CollectiveScenarioGenerator
    
    def generate_all(self, conversations_per_domain: int = 3, sessions_per_conversation: int = 5) -> list[Conversation]:
        """
        Gera conversas para todos os domínios.
        
        Args:
            conversations_per_domain: Quantas conversas por domínio
            sessions_per_conversation: Quantas sessões por conversa
            
        Returns:
            Lista de todas as conversas
        """
        all_conversations = []
        
        for domain, generator_class in self.GENERATORS.items():
            generator = generator_class()
            
            for _ in range(conversations_per_domain):
                conv = generator.generate(num_sessions=sessions_per_conversation)
                all_conversations.append(conv)
        
        return all_conversations
    
    def generate_domain(self, domain: str, count: int = 3, sessions: int = 5) -> list[Conversation]:
        """Gera conversas para um domínio específico."""
        if domain not in self.GENERATORS:
            raise ValueError(f"Domínio desconhecido: {domain}. Opções: {list(self.GENERATORS.keys())}")
        
        generator = self.GENERATORS[domain]()
        return [generator.generate(num_sessions=sessions) for _ in range(count)]
    
    def generate_collective(self, scenario_type: str = "support", num_users: int = 3) -> list[Conversation]:
        """
        Gera cenário coletivo para testar memória compartilhada.
        
        Args:
            scenario_type: "support" ou "education"
            num_users: Número de usuários no cenário
            
        Returns:
            Lista de conversas no mesmo domínio com problemas similares
        """
        collective_gen = self.COLLECTIVE_GENERATOR()
        
        if scenario_type == "support":
            return collective_gen.generate_support_collective(num_users)
        elif scenario_type == "education":
            return collective_gen.generate_education_collective(num_users)
        else:
            raise ValueError(f"Tipo desconhecido: {scenario_type}. Opções: support, education")
    
    def generate_with_collective(
        self, 
        conversations_per_domain: int = 2, 
        sessions_per_conversation: int = 3,
        include_collective: bool = True,
    ) -> list[Conversation]:
        """
        Gera conversas incluindo cenários coletivos para testar memória compartilhada.
        
        Args:
            conversations_per_domain: Conversas por domínio
            sessions_per_conversation: Sessões por conversa
            include_collective: Se True, adiciona cenários coletivos
            
        Returns:
            Lista de todas as conversas incluindo cenários coletivos
        """
        conversations = self.generate_all(
            conversations_per_domain=conversations_per_domain,
            sessions_per_conversation=sessions_per_conversation,
        )
        
        if include_collective:
            # Adiciona cenários coletivos
            collective_support = self.generate_collective("support", num_users=3)
            collective_education = self.generate_collective("education", num_users=3)
            
            conversations.extend(collective_support)
            conversations.extend(collective_education)
        
        return conversations
    
    def save_to_file(self, conversations: list[Conversation], filepath: Path | str) -> None:
        """Salva conversas em arquivo JSON."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "generated_at": datetime.now().isoformat(),
            "total_conversations": len(conversations),
            "total_sessions": sum(len(c.sessions) for c in conversations),
            "total_messages": sum(
                sum(len(s.messages) for s in c.sessions)
                for c in conversations
            ),
            "domains": list(set(c.domain for c in conversations)),
            "conversations": [c.to_dict() for c in conversations],
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Salvo {len(conversations)} conversas em {filepath}")
    
    def load_from_file(self, filepath: Path | str) -> list[Conversation]:
        """Carrega conversas de arquivo JSON."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Reconstrói objetos (simplificado - mantém como dict)
        return data["conversations"]


def main():
    """Função principal para teste."""
    generator = ConversationGenerator()
    
    # Gera 3 conversas por domínio, 5 sessões cada
    print("🔄 Gerando conversas para benchmark...")
    conversations = generator.generate_all(
        conversations_per_domain=3,
        sessions_per_conversation=5
    )
    
    print(f"\n📊 Estatísticas:")
    print(f"  - Domínios: {len(generator.GENERATORS)}")
    print(f"  - Conversas: {len(conversations)}")
    print(f"  - Sessões: {sum(len(c.sessions) for c in conversations)}")
    print(f"  - Mensagens: {sum(sum(len(s.messages) for s in c.sessions) for c in conversations)}")
    
    # Salva
    output_path = Path(__file__).parent / "data" / "benchmark_conversations.json"
    generator.save_to_file(conversations, output_path)
    
    print(f"\n✅ Benchmark dataset pronto em: {output_path}")


if __name__ == "__main__":
    main()
