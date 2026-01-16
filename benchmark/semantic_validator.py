"""
Semantic Validator - Validação de métricas usando análise semântica

Em vez de pattern matching simples, usa embeddings para detectar se uma
resposta menciona semanticamente o conteúdo de uma memória.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import os
from typing import List, Tuple, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()

# Usa o serviço de embeddings existente do Cortex
from cortex.core.processing.embedding import EmbeddingService, cosine_similarity


@dataclass
class SemanticMatch:
    """Resultado de uma comparação semântica."""
    score: float  # 0-1, quanto maior mais similar
    matched: bool  # True se score >= threshold
    query: str
    target: str


class SemanticValidator:
    """
    Valida se respostas do LLM mencionam semanticamente conteúdos esperados.

    Exemplo:
        validator = SemanticValidator()

        # Verifica se resposta menciona preferência de horário
        result = validator.check_mention(
            response="vamos considerar sua preferência de horário",
            expected_content="reuniões entre 9h e 11h"
        )

        if result.matched:
            print(f"✅ Mencionou! Score: {result.score:.2f}")
    """

    def __init__(
        self,
        ollama_url: Optional[str] = None,
        embedding_model: Optional[str] = None,
        threshold: float = 0.5
    ):
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.embedding_model = embedding_model or os.getenv("CORTEX_EMBEDDING_MODEL", "qwen3-embedding:0.6b")
        self.threshold = threshold

        # Usa o serviço de embeddings do Cortex
        self.embedding_service = EmbeddingService(
            ollama_url=self.ollama_url,
            model=self.embedding_model
        )

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Obtém embedding de um texto via serviço do Cortex.

        Args:
            text: Texto para gerar embedding

        Returns:
            Vetor de embedding ou None se falhar
        """
        result = self.embedding_service.embed(text)
        if result is None:
            return None
        return result.vector

    def check_mention(
        self,
        response: str,
        expected_content: str,
        context: str = ""
    ) -> SemanticMatch:
        """
        Verifica se a resposta menciona semanticamente o conteúdo esperado.

        Args:
            response: Resposta do LLM a ser validada
            expected_content: Conteúdo que deveria ser mencionado
            context: Contexto adicional (opcional)

        Returns:
            SemanticMatch com score e resultado
        """
        # Gera embeddings
        response_emb = self.get_embedding(response)
        expected_emb = self.get_embedding(expected_content)

        # Se algum embedding falhou, retorna score baixo
        if response_emb is None or expected_emb is None:
            return SemanticMatch(
                score=0.0,
                matched=False,
                query=response,
                target=expected_content
            )

        # Calcula similaridade usando função do Cortex
        similarity = cosine_similarity(response_emb, expected_emb)

        # Normaliza de [-1, 1] para [0, 1]
        score = (similarity + 1) / 2

        return SemanticMatch(
            score=score,
            matched=score >= self.threshold,
            query=response,
            target=expected_content
        )

    def check_multiple_mentions(
        self,
        response: str,
        expected_contents: List[str]
    ) -> Tuple[float, List[SemanticMatch]]:
        """
        Verifica se resposta menciona múltiplos conteúdos esperados.

        Args:
            response: Resposta do LLM
            expected_contents: Lista de conteúdos esperados

        Returns:
            (score_médio, lista_de_matches)
        """
        matches = []

        for content in expected_contents:
            match = self.check_mention(response, content)
            matches.append(match)

        # Score médio
        avg_score = sum(m.score for m in matches) / len(matches) if matches else 0.0

        return avg_score, matches

    def validate_context_retention(
        self,
        response: str,
        stored_memories: List[str],
        min_mentions: int = 1
    ) -> Tuple[float, int]:
        """
        Valida se resposta retém contexto de memórias armazenadas.

        Args:
            response: Resposta do LLM
            stored_memories: Lista de memórias que deveriam ser usadas
            min_mentions: Mínimo de memórias que devem ser mencionadas

        Returns:
            (retention_score 0-1, número de memórias mencionadas)
        """
        mentions_count = 0
        total_score = 0.0

        for memory in stored_memories:
            match = self.check_mention(response, memory)
            if match.matched:
                mentions_count += 1
            total_score += match.score

        # Score normalizado
        avg_score = total_score / len(stored_memories) if stored_memories else 0.0

        # Retention score: combinação de quantidade e qualidade
        retention_score = (
            0.5 * (mentions_count / len(stored_memories)) +  # 50% quantidade
            0.5 * avg_score  # 50% qualidade semântica
        ) if stored_memories else 0.0

        return retention_score, mentions_count


# =============================================================================
# TESTES RÁPIDOS
# =============================================================================

if __name__ == "__main__":
    print("🧪 Testando SemanticValidator...\n")

    validator = SemanticValidator(threshold=0.6)

    # Debug do serviço de embeddings
    print("Debug: Testando embedding service...")
    test_emb = validator.get_embedding("teste")
    if test_emb:
        print(f"  ✅ Embedding gerado: {len(test_emb)} dimensões\n")
    else:
        print(f"  ❌ Falhou ao gerar embedding\n")
        print(f"  Stats: {validator.embedding_service._stats}\n")

    # Teste 1: Menção direta
    print("Test 1: Menção direta")
    result = validator.check_mention(
        response="Suas reuniões devem ser entre 9h e 11h",
        expected_content="reuniões entre 9h e 11h"
    )
    print(f"  Score: {result.score:.2f} | Matched: {result.matched}\n")

    # Teste 2: Menção indireta (o caso problemático)
    print("Test 2: Menção indireta")
    result = validator.check_mention(
        response="Vamos considerar sua preferência de horário, que já foi anotada",
        expected_content="reuniões entre 9h e 11h pela manhã"
    )
    print(f"  Score: {result.score:.2f} | Matched: {result.matched}\n")

    # Teste 3: Sem menção
    print("Test 3: Sem menção")
    result = validator.check_mention(
        response="Vou verificar a disponibilidade da sala",
        expected_content="reuniões entre 9h e 11h"
    )
    print(f"  Score: {result.score:.2f} | Matched: {result.matched}\n")

    # Teste 4: Context retention
    print("Test 4: Context retention")
    retention, count = validator.validate_context_retention(
        response="Sim, verifiquei os três casos de login que você reportou",
        stored_memories=[
            "problema de login dia 1",
            "problema de senha dia 1",
            "ainda com problema dia 2"
        ]
    )
    print(f"  Retention: {retention:.2f} | Mentions: {count}/3\n")

    print("✅ Testes concluídos!")
