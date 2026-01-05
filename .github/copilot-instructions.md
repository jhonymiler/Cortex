# Cortex Development Guide for AI Agents

> **Core Principle:** Cortex is NOT RAG/VectorDB — it's semantic memory using Entity-Episode-Relation graphs with O(1) indexed lookup, zero tokens per search.

## Architecture Overview

**Three-layer structure:**
```
MCP/API Layer (entry points) → Services (business logic) → Core (domain models + MemoryGraph)
```

- **Core** (`src/cortex/core/`): Pure domain models (Entity, Episode, Relation, MemoryGraph) — NO I/O operations
- **Services** (`src/cortex/services/`): `MemoryService` orchestrates all logic — single source of truth for both MCP and API
- **Interfaces**: FastMCP (`src/cortex/mcp/server.py`) + FastAPI (`src/cortex/api/app.py`) — both delegate to `MemoryService`

**Critical rule:** NEVER mix layers. Models don't do I/O, services don't handle HTTP/MCP directly.

## Domain Models (Core Abstractions)

### Entity, Episode, Relation — Domain Agnostic

```python
# ✅ CORRECT - Generic types
Entity(type="file", name="auth.py")        # Dev domain
Entity(type="character", name="Gandalf")   # Roleplay
Entity(type="customer", name="Maria")      # Chatbot

# ❌ WRONG - Domain-specific classes
class ProjectFile(Entity): ...
class Character(Entity): ...
```

**Key pattern:** Use free-form `type`, `action`, `relation_type` fields — never create domain-specific subclasses.

### MemoryGraph — Index-Based Recall

```python
# Indexes for O(1) lookup (NOT vector similarity):
_entity_by_name: dict[str, list[str]]
_entity_by_type: dict[str, list[str]]
_relations_by_from: dict[str, list[str]]
```

## Development Workflow

### Environment Setup (ALWAYS FIRST)
```bash
source venv/bin/activate  # Mandatory before any command
pip install -e ".[all,dev]"
```

### Running Services
```bash
# MCP Server (for Claude Desktop)
cortex-mcp

# REST API
cortex-api
# or
uvicorn cortex.api.app:app --reload
```

### Testing Strategy
```bash
pytest tests/ -v  # Unit + integration tests
pytest tests/test_memory_service.py::TestConsolidation -v  # Specific test class
```

**Test structure:**
- `tests/test_core.py` — Entity, Episode, Relation models
- `tests/test_memory_service.py` — Service layer with 6 test classes (validation, recall, consolidation, Pydantic, edge cases, integration)
- `conftest.py` — Shared fixtures

### Code Quality
```bash
ruff check src/    # Lint
ruff format src/   # Auto-format
mypy src/         # Type checking
```

## Critical Patterns

### 1. Consolidation (Auto-Merge Similar Episodes)

```python
# 5+ similar episodes → consolidated pattern
Episode(action="password_reset", occurrence_count=1)  # 5 times
# Becomes:
Episode(action="password_reset_pattern", occurrence_count=5, is_consolidated=True)
```

**Implementation:** `MemoryService._detect_consolidation()` checks for 5+ similar episodes before storing.

### 2. Entity Resolution (Dedupe via Identifiers)

```python
# Prevents duplicates:
entity = graph.resolve_entity(name="João", identifiers=["joao@email.com"])
# Returns existing if identifier matches, creates new otherwise
```

**Always use `resolve_entity()` in `MemoryService.store()` — NEVER create entities directly.**

### 3. Shared Service Pattern

```python
# services/memory_service.py — Single orchestrator
class MemoryService:
    def store(self, request: StoreRequest) -> StoreResponse: ...
    def recall(self, request: RecallRequest) -> RecallResponse: ...

# api/app.py
@app.post("/memory/store")
def store_endpoint(request: StoreRequest, service=Depends(get_service)):
    return service.store(request)  # Delegates to service

# mcp/server.py
@mcp.tool()
def cortex_store(...) -> dict:
    return service.store(StoreRequest(...)).model_dump()  # Same service
```

**Never duplicate logic** — both interfaces call `MemoryService`.

### 4. Pydantic for I/O, Dataclasses for Domain

```python
# API/MCP boundary:
class StoreRequest(BaseModel): ...  # Pydantic for validation

# Internal domain:
@dataclass
class Episode: ...  # Dataclass for core models
```

### 5. FastMCP (Decorator-Based MCP)

```python
# ✅ CORRECT - Modern FastMCP
from fastmcp import FastMCP
mcp = FastMCP("cortex")

@mcp.tool()
def cortex_recall(...) -> dict: ...

# ❌ WRONG - Old MCP (verbose)
from mcp import Server
server = Server("cortex")
server.add_tool(...)
```

## What NOT to Do

### ❌ Store Raw Text
```python
# WRONG - Defeats semantic memory
Episode(context="Here are 10,000 lines of log...")

# RIGHT - Extract meaning
Episode(action="analyzed_log", outcome="found 3 errors: missing route, timeout, auth fail")
```

### ❌ Use Embeddings/Vectors
```python
# Cortex is NOT RAG
results = vector_db.similarity_search(embedding)  # FORBIDDEN
```

### ❌ Mix Layers
```python
# WRONG - Model doing I/O
class Entity:
    def save_to_database(self): ...

# RIGHT - Service handles persistence
class MemoryService:
    def store(self, request): 
        graph.add_entity(entity)
        graph.save()
```

### ❌ Create Duplicate Entities
```python
# WRONG
entity1 = Entity(name="João")
entity2 = Entity(name="João Silva")  # Duplicate!

# RIGHT
entity = graph.resolve_entity(name="João Silva", identifiers=["joao@email.com"])
```

## File Organization Rules

### SDK Location
- `sdk/python/cortex_sdk.py` — REST client for external use (NOT for internal code)
- `teste-llm/` — Integration tests using SDK (Ollama examples)

### Documentation Reference
- `docs/VISION.md` — Philosophy, core concepts
- `docs/ARCHITECTURE.md` — Layer structure, data flows
- `docs/API.md` — REST endpoint specs
- `docs/MCP.md` — MCP tool specs + Claude Desktop config
- `.github/instructions/cortex.instructions.md` — Detailed development rules (this supersedes on conflicts)

## Git Workflow

```bash
# Commit pattern (conventional commits):
feat: add consolidation detection
fix: resolve duplicate entity bug
docs: update MCP configuration
test: add consolidation edge cases
```

**Rule:** Commit after confirming feature works, delete old/duplicate files, maintain organized structure.

## Type Hints & Documentation

**Mandatory:** All functions need type hints + docstrings:

```python
def recall(self, query: str, context: dict) -> RecallResult:
    """
    Busca memórias relevantes para uma query.
    
    Args:
        query: Texto para buscar
        context: Contexto adicional para filtrar
    
    Returns:
        RecallResult com entidades, episódios e relações
    """
```

## Current Status (Jan 2026)

✅ **Complete:** Core models, MemoryService, test suite, documentation, pyproject.toml  
⏳ **Pending:** Full MCP/API implementation, Claude Desktop integration, persistence layer, benchmarks

---

**Key Insight:** When in doubt, check existing patterns in `tests/test_memory_service.py` — it demonstrates correct service usage comprehensively.
