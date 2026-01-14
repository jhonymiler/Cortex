"""
SharedMemory - Sistema de memória compartilhada com isolamento de contexto pessoal.

Conceito Central:
- Agentes podem APRENDER com interações de outros usuários
- Mas NÃO podem CONFUNDIR dados pessoais de um usuário com outro

Casos de Uso:
1. Atendimento ao Cliente:
   - Agente aprende padrões: "problema X geralmente se resolve com Y"
   - Mas não diz "você teve esse problema antes" se foi OUTRA pessoa

2. Time de Devs:
   - Agente sabe sobre projetos do workspace
   - Aprendeu com perguntas de outros devs
   - Mas não diz "você perguntou isso ontem" se foi outro dev

Arquitetura:
```
┌─────────────────────────────────────────────────────────────┐
│                    SHARED MEMORY                             │
│     (conhecimento geral, padrões, aprendizados)             │
│     visibility = "shared" ou "learned"                       │
├─────────────────────────────────────────────────────────────┤
│   USER A        │   USER B        │   USER C                │
│   (personal)    │   (personal)    │   (personal)            │
│   visibility    │   visibility    │   visibility            │
│   = "personal"  │   = "personal"  │   = "personal"          │
└─────────────────────────────────────────────────────────────┘
```

Regras de Recall:
- PERSONAL: Só retorna se owner == current_user
- SHARED: Retorna para todos, marcado como "conhecimento geral"
- LEARNED: Retorna para todos, mas anônimo (sem mencionar quem ensinou)

Regras de Store:
- Interações pessoais → visibility = "personal"
- Padrões detectados → visibility = "learned" (extrai conhecimento, remove PII)
- Configurações do workspace → visibility = "shared"
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from cortex.core.graph import MemoryGraph


class MemoryVisibility(str, Enum):
    """Níveis de visibilidade de memória."""
    
    PERSONAL = "personal"   # Apenas o owner pode ver
    SHARED = "shared"       # Todos podem ver, atribuição clara
    LEARNED = "learned"     # Todos podem ver, anônimo (conhecimento extraído)


@dataclass
class NamespaceConfig:
    """Configuração de um namespace."""
    
    # Identificador do namespace
    namespace: str
    
    # Namespace pai (para hierarquia)
    parent_namespace: str | None = None
    
    # Se permite herdar memórias do pai
    inherit_from_parent: bool = True
    
    # Se permite extrair conhecimento para o pai
    contribute_to_parent: bool = True
    
    # Threshold para promover memória pessoal para shared
    promotion_threshold: int = 3  # 3+ usuários com padrão similar = shared
    
    # Se memórias deste namespace são visíveis para filhos
    visible_to_children: bool = True


@dataclass
class SharedMemoryContext:
    """Contexto para recall com memória compartilhada."""
    
    # Identificador do usuário atual
    user_id: str
    
    # Namespace atual (ex: "workspace:projeto_x")
    namespace: str
    
    # Se deve incluir memórias compartilhadas
    include_shared: bool = True
    
    # Se deve incluir memórias aprendidas (anônimas)
    include_learned: bool = True
    
    # Se deve incluir memórias do namespace pai
    include_parent: bool = True
    
    # Limite de memórias compartilhadas vs pessoais
    personal_limit: int = 5
    shared_limit: int = 3
    learned_limit: int = 2


@dataclass
class MemoryWithVisibility:
    """Wrapper para memória com informação de visibilidade."""
    
    # ID original da memória (episode ou entity)
    memory_id: str
    memory_type: str  # "episode" ou "entity"
    
    # Conteúdo
    content: dict[str, Any]
    
    # Visibilidade
    visibility: MemoryVisibility
    
    # Owner (quem criou)
    owner_id: str
    
    # Namespace
    namespace: str
    
    # Timestamp
    created_at: datetime = field(default_factory=datetime.now)
    
    # Se foi promovido de personal para shared
    promoted_from: str | None = None
    
    # Score de relevância (para ordenação)
    relevance_score: float = 0.0
    
    def is_accessible_by(self, user_id: str) -> bool:
        """Verifica se o usuário pode acessar esta memória."""
        if self.visibility == MemoryVisibility.PERSONAL:
            return self.owner_id == user_id
        return True  # SHARED e LEARNED são acessíveis por todos
    
    def to_prompt_context(self, current_user_id: str) -> str:
        """
        Gera contexto para prompt, respeitando visibilidade.
        
        - PERSONAL (own): Mostra normalmente
        - PERSONAL (other): Não mostra (não deveria chegar aqui)
        - SHARED: Mostra com atribuição
        - LEARNED: Mostra como conhecimento geral, sem atribuição
        """
        if self.visibility == MemoryVisibility.PERSONAL:
            if self.owner_id == current_user_id:
                # Memória pessoal do usuário atual
                return self._format_personal()
            else:
                # Não deveria acontecer, mas protege
                return ""
        
        elif self.visibility == MemoryVisibility.SHARED:
            # Memória compartilhada com atribuição
            return self._format_shared()
        
        else:  # LEARNED
            # Conhecimento extraído, anônimo
            return self._format_learned()
    
    def _format_personal(self) -> str:
        """Formata memória pessoal."""
        if self.memory_type == "episode":
            return f"[Você] {self.content.get('action', '')}: {self.content.get('outcome', '')}"
        else:
            return f"[Você] conhece: {self.content.get('name', '')}"
    
    def _format_shared(self) -> str:
        """Formata memória compartilhada."""
        if self.memory_type == "episode":
            return f"[Equipe] {self.content.get('action', '')}: {self.content.get('outcome', '')}"
        else:
            return f"[Projeto] {self.content.get('name', '')}: {self.content.get('type', '')}"
    
    def _format_learned(self) -> str:
        """Formata conhecimento aprendido (anônimo)."""
        if self.memory_type == "episode":
            # Remove referências pessoais
            action = self.content.get('action', '')
            outcome = self.content.get('outcome', '')
            return f"[Aprendido] {action} geralmente resulta em: {outcome}"
        else:
            return f"[Conhecimento] {self.content.get('name', '')} é do tipo {self.content.get('type', '')}"


class SharedMemoryManager:
    """
    Gerencia memória compartilhada com isolamento de contexto pessoal.
    
    Responsabilidades:
    1. Armazenar memórias com visibilidade correta
    2. Recuperar memórias respeitando privacidade
    3. Detectar padrões para promover a shared/learned
    4. Extrair conhecimento genérico de interações pessoais
    """
    
    def __init__(self):
        # Índice de visibilidade: memory_id -> MemoryWithVisibility
        self._visibility_index: dict[str, MemoryWithVisibility] = {}
        
        # Índice por namespace: namespace -> [memory_ids]
        self._namespace_index: dict[str, list[str]] = {}
        
        # Índice por owner: owner_id -> [memory_ids]
        self._owner_index: dict[str, list[str]] = {}
        
        # Configurações de namespace
        self._namespace_configs: dict[str, NamespaceConfig] = {}
        
        # Detector de padrões para promoção
        self._pattern_tracker: dict[str, dict[str, int]] = {}  # pattern_hash -> {user_ids}
    
    def configure_namespace(self, config: NamespaceConfig) -> None:
        """Configura um namespace."""
        self._namespace_configs[config.namespace] = config
        if config.namespace not in self._namespace_index:
            self._namespace_index[config.namespace] = []
    
    def get_namespace_config(self, namespace: str) -> NamespaceConfig:
        """Retorna configuração do namespace (cria padrão se não existir)."""
        if namespace not in self._namespace_configs:
            self._namespace_configs[namespace] = NamespaceConfig(namespace=namespace)
        return self._namespace_configs[namespace]
    
    def register_memory(
        self,
        memory_id: str,
        memory_type: str,
        content: dict[str, Any],
        owner_id: str,
        namespace: str,
        visibility: MemoryVisibility = MemoryVisibility.PERSONAL,
    ) -> MemoryWithVisibility:
        """
        Registra uma memória com visibilidade.
        
        Args:
            memory_id: ID da memória no grafo
            memory_type: "episode" ou "entity"
            content: Conteúdo serializado
            owner_id: Quem criou
            namespace: Namespace da memória
            visibility: Nível de visibilidade
            
        Returns:
            MemoryWithVisibility registrada
        """
        mem_vis = MemoryWithVisibility(
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            visibility=visibility,
            owner_id=owner_id,
            namespace=namespace,
        )
        
        self._visibility_index[memory_id] = mem_vis
        
        # Indexa por namespace
        if namespace not in self._namespace_index:
            self._namespace_index[namespace] = []
        self._namespace_index[namespace].append(memory_id)
        
        # Indexa por owner
        if owner_id not in self._owner_index:
            self._owner_index[owner_id] = []
        self._owner_index[owner_id].append(memory_id)
        
        # Tracker de padrões para promoção automática
        if visibility == MemoryVisibility.PERSONAL:
            self._track_pattern(mem_vis)
        
        return mem_vis
    
    def recall_with_context(
        self,
        graph: "MemoryGraph",
        query: str,
        context: SharedMemoryContext,
    ) -> list[MemoryWithVisibility]:
        """
        Recall respeitando visibilidade e contexto.
        
        Retorna memórias ordenadas por relevância:
        1. Memórias pessoais do usuário
        2. Memórias compartilhadas do namespace
        3. Conhecimento aprendido
        4. Memórias do namespace pai (se configurado)
        
        Args:
            graph: MemoryGraph para busca
            query: Query do usuário
            context: Contexto com user_id, namespace, etc.
            
        Returns:
            Lista de memórias com visibilidade
        """
        results: list[MemoryWithVisibility] = []
        
        # 1. Memórias PESSOAIS do usuário atual
        personal_memories = self._get_personal_memories(
            context.user_id,
            context.namespace,
            query,
            limit=context.personal_limit,
        )
        results.extend(personal_memories)
        
        # 2. Memórias COMPARTILHADAS do namespace
        if context.include_shared:
            shared_memories = self._get_shared_memories(
                context.namespace,
                query,
                limit=context.shared_limit,
            )
            results.extend(shared_memories)
        
        # 3. Conhecimento APRENDIDO
        if context.include_learned:
            learned_memories = self._get_learned_memories(
                context.namespace,
                query,
                limit=context.learned_limit,
            )
            results.extend(learned_memories)
        
        # 4. Memórias do namespace PAI
        if context.include_parent:
            ns_config = self.get_namespace_config(context.namespace)
            if ns_config.parent_namespace and ns_config.inherit_from_parent:
                parent_memories = self._get_inherited_memories(
                    ns_config.parent_namespace,
                    query,
                    limit=2,
                )
                results.extend(parent_memories)
        
        # Ordena por relevância
        results.sort(key=lambda m: m.relevance_score, reverse=True)
        
        return results
    
    def _get_personal_memories(
        self,
        user_id: str,
        namespace: str,
        query: str,
        limit: int,
    ) -> list[MemoryWithVisibility]:
        """Retorna memórias pessoais do usuário."""
        if user_id not in self._owner_index:
            return []
        
        personal = []
        for mid in self._owner_index[user_id]:
            mem = self._visibility_index.get(mid)
            if mem and mem.visibility == MemoryVisibility.PERSONAL:
                if mem.namespace == namespace:
                    # TODO: Calcular relevância real baseado na query
                    mem.relevance_score = 1.0  # Prioridade máxima para pessoal
                    personal.append(mem)
        
        return personal[:limit]
    
    def _get_shared_memories(
        self,
        namespace: str,
        query: str,
        limit: int,
    ) -> list[MemoryWithVisibility]:
        """Retorna memórias compartilhadas do namespace."""
        if namespace not in self._namespace_index:
            return []
        
        shared = []
        for mid in self._namespace_index[namespace]:
            mem = self._visibility_index.get(mid)
            if mem and mem.visibility == MemoryVisibility.SHARED:
                mem.relevance_score = 0.8  # Prioridade alta
                shared.append(mem)
        
        return shared[:limit]
    
    def _get_learned_memories(
        self,
        namespace: str,
        query: str,
        limit: int,
    ) -> list[MemoryWithVisibility]:
        """Retorna conhecimento aprendido do namespace."""
        if namespace not in self._namespace_index:
            return []
        
        learned = []
        for mid in self._namespace_index[namespace]:
            mem = self._visibility_index.get(mid)
            if mem and mem.visibility == MemoryVisibility.LEARNED:
                mem.relevance_score = 0.6  # Prioridade média
                learned.append(mem)
        
        return learned[:limit]
    
    def _get_inherited_memories(
        self,
        parent_namespace: str,
        query: str,
        limit: int,
    ) -> list[MemoryWithVisibility]:
        """Retorna memórias herdadas do namespace pai."""
        parent_config = self.get_namespace_config(parent_namespace)
        if not parent_config.visible_to_children:
            return []
        
        inherited = []
        if parent_namespace in self._namespace_index:
            for mid in self._namespace_index[parent_namespace]:
                mem = self._visibility_index.get(mid)
                if mem and mem.visibility in [MemoryVisibility.SHARED, MemoryVisibility.LEARNED]:
                    mem.relevance_score = 0.4  # Prioridade mais baixa
                    inherited.append(mem)
        
        return inherited[:limit]
    
    def _track_pattern(self, memory: MemoryWithVisibility) -> None:
        """
        Rastreia padrões para promoção automática.
        
        Quando 3+ usuários diferentes têm memórias similares,
        extrai conhecimento genérico e promove para LEARNED.
        """
        # Cria hash do padrão (simplificado)
        if memory.memory_type == "episode":
            pattern_key = f"{memory.content.get('action', '')}:{memory.namespace}"
        else:
            pattern_key = f"{memory.content.get('type', '')}:{memory.namespace}"
        
        if pattern_key not in self._pattern_tracker:
            self._pattern_tracker[pattern_key] = {}
        
        self._pattern_tracker[pattern_key][memory.owner_id] = self._pattern_tracker[pattern_key].get(memory.owner_id, 0) + 1
        
        # Verifica se deve promover
        unique_users = len(self._pattern_tracker[pattern_key])
        ns_config = self.get_namespace_config(memory.namespace)
        
        if unique_users >= ns_config.promotion_threshold:
            self._promote_pattern_to_learned(pattern_key, memory.namespace)
    
    def _promote_pattern_to_learned(self, pattern_key: str, namespace: str) -> None:
        """
        Promove um padrão para conhecimento aprendido.
        
        Extrai conhecimento genérico, remove PII, e cria memória LEARNED.
        """
        # TODO: Implementar extração de conhecimento
        # Por enquanto, apenas marca como promoted
        pass
    
    def promote_to_shared(
        self,
        memory_id: str,
        promoted_by: str = "system",
    ) -> bool:
        """
        Promove uma memória pessoal para compartilhada.
        
        Usado quando um admin ou o sistema decide compartilhar algo.
        """
        mem = self._visibility_index.get(memory_id)
        if not mem or mem.visibility != MemoryVisibility.PERSONAL:
            return False
        
        mem.visibility = MemoryVisibility.SHARED
        mem.promoted_from = mem.owner_id
        
        return True
    
    def extract_knowledge(
        self,
        memory_id: str,
        anonymize: bool = True,
    ) -> MemoryWithVisibility | None:
        """
        Extrai conhecimento de uma memória pessoal, criando versão LEARNED.
        
        Remove informações pessoais e cria conhecimento genérico.
        """
        original = self._visibility_index.get(memory_id)
        if not original:
            return None
        
        # Copia e anonimiza
        learned_content = original.content.copy()
        
        if anonymize:
            # Remove referências pessoais
            learned_content.pop("user_name", None)
            learned_content.pop("user_email", None)
            learned_content.pop("user_id", None)
            
            # Generaliza ação
            if "participants" in learned_content:
                learned_content["participants"] = ["usuário"]
        
        # Cria nova memória LEARNED
        learned_id = f"learned_{str(uuid4())[:8]}"
        learned_mem = MemoryWithVisibility(
            memory_id=learned_id,
            memory_type=original.memory_type,
            content=learned_content,
            visibility=MemoryVisibility.LEARNED,
            owner_id="system",
            namespace=original.namespace,
            promoted_from=memory_id,
        )
        
        self._visibility_index[learned_id] = learned_mem
        
        if original.namespace not in self._namespace_index:
            self._namespace_index[original.namespace] = []
        self._namespace_index[original.namespace].append(learned_id)
        
        return learned_mem
    
    def format_recall_for_prompt(
        self,
        memories: list[MemoryWithVisibility],
        current_user_id: str,
    ) -> str:
        """
        Formata memórias para injeção no prompt.
        
        Separa claramente:
        - "Você mencionou anteriormente..."
        - "A equipe sabe que..."
        - "Geralmente, ..."
        """
        if not memories:
            return ""
        
        personal_lines = []
        shared_lines = []
        learned_lines = []
        
        for mem in memories:
            formatted = mem.to_prompt_context(current_user_id)
            if not formatted:
                continue
            
            if mem.visibility == MemoryVisibility.PERSONAL:
                personal_lines.append(formatted)
            elif mem.visibility == MemoryVisibility.SHARED:
                shared_lines.append(formatted)
            else:
                learned_lines.append(formatted)
        
        parts = []
        
        if personal_lines:
            parts.append("📝 Seu histórico:")
            parts.extend(f"  - {line}" for line in personal_lines[:3])
        
        if shared_lines:
            parts.append("👥 Conhecimento da equipe:")
            parts.extend(f"  - {line}" for line in shared_lines[:2])
        
        if learned_lines:
            parts.append("💡 Aprendizados gerais:")
            parts.extend(f"  - {line}" for line in learned_lines[:2])
        
        return "\n".join(parts)
    
    def stats(self) -> dict[str, Any]:
        """Retorna estatísticas do sistema de memória compartilhada."""
        personal_count = sum(
            1 for m in self._visibility_index.values()
            if m.visibility == MemoryVisibility.PERSONAL
        )
        shared_count = sum(
            1 for m in self._visibility_index.values()
            if m.visibility == MemoryVisibility.SHARED
        )
        learned_count = sum(
            1 for m in self._visibility_index.values()
            if m.visibility == MemoryVisibility.LEARNED
        )
        
        return {
            "total_memories": len(self._visibility_index),
            "personal": personal_count,
            "shared": shared_count,
            "learned": learned_count,
            "namespaces": len(self._namespace_index),
            "unique_owners": len(self._owner_index),
            "tracked_patterns": len(self._pattern_tracker),
        }


# Factory
def create_shared_memory_manager() -> SharedMemoryManager:
    """Cria um SharedMemoryManager."""
    return SharedMemoryManager()

