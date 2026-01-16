"""
Cortex Logging Infrastructure - Sistema de Auditoria e Debug

Fornece logging estruturado para todo o sistema Cortex com:
- Audit trail para rastreabilidade de operações
- Logs rotativos por tamanho e data
- Níveis configuráveis (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Formatação JSON para análise automatizada
- Separação de logs por módulo/categoria
"""

import logging
import logging.handlers
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager


class CortexLogger:
    """
    Sistema centralizado de logging para Cortex.

    Cria logs estruturados em diferentes categorias:
    - audit: Operações de memória (CRUD de episodes, entities, relations)
    - api: Chamadas HTTP (entrada/saída)
    - performance: Métricas de tempo e recursos
    - error: Erros e exceções
    - debug: Informações detalhadas de desenvolvimento

    Exemplo:
        logger = CortexLogger.get_logger("memory_graph")
        logger.info("Episode created", extra={
            "episode_id": episode.id,
            "user_id": user.id,
            "content_preview": content[:50]
        })
    """

    _loggers: Dict[str, logging.Logger] = {}
    _initialized = False

    # Configurações padrão
    DEFAULT_LOG_DIR = Path("logs")
    DEFAULT_AUDIT_DIR = Path("logs/audit")
    DEFAULT_LOG_LEVEL = logging.INFO
    DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    DEFAULT_BACKUP_COUNT = 5

    @classmethod
    def initialize(
        cls,
        log_dir: Optional[Path] = None,
        audit_dir: Optional[Path] = None,
        level: Optional[int] = None,
        enable_console: bool = True,
        enable_file: bool = True,
        enable_json: bool = False,
        force: bool = False
    ):
        """
        Inicializa o sistema de logging.

        Args:
            log_dir: Diretório para logs gerais
            audit_dir: Diretório para logs de auditoria
            level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            enable_console: Se True, envia logs para console
            enable_file: Se True, envia logs para arquivos
            enable_json: Se True, usa formato JSON para logs
            force: Se True, permite re-inicialização mesmo se já inicializado
        """
        if cls._initialized and not force:
            return

        # Se force=True, limpa loggers existentes
        if force and cls._initialized:
            cls.shutdown()

        cls.log_dir = log_dir or cls.DEFAULT_LOG_DIR
        cls.audit_dir = audit_dir or cls.DEFAULT_AUDIT_DIR
        cls.log_level = level or cls.DEFAULT_LOG_LEVEL
        cls.enable_console = enable_console
        cls.enable_file = enable_file
        cls.enable_json = enable_json

        # Cria diretórios se não existirem
        cls.log_dir.mkdir(parents=True, exist_ok=True)
        cls.audit_dir.mkdir(parents=True, exist_ok=True)

        cls._initialized = True

    @classmethod
    def get_logger(cls, name: str, category: str = "general") -> logging.Logger:
        """
        Obtém um logger configurado.

        Args:
            name: Nome do módulo/componente (ex: "memory_graph", "embedding_service")
            category: Categoria do log ("audit", "api", "performance", "error", "debug", "general")

        Returns:
            Logger configurado
        """
        if not cls._initialized:
            cls.initialize()

        logger_key = f"{category}.{name}"

        if logger_key in cls._loggers:
            return cls._loggers[logger_key]

        logger = logging.getLogger(logger_key)
        logger.setLevel(cls.log_level)
        logger.handlers = []  # Limpa handlers existentes

        # Handler para console
        if cls.enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(cls.log_level)
            console_handler.setFormatter(cls._get_formatter(use_json=False))
            logger.addHandler(console_handler)

        # Handler para arquivo
        if cls.enable_file:
            # Log geral rotativo
            log_file = cls.log_dir / f"{category}.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=cls.DEFAULT_MAX_BYTES,
                backupCount=cls.DEFAULT_BACKUP_COUNT
            )
            file_handler.setLevel(cls.log_level)
            file_handler.setFormatter(cls._get_formatter(use_json=cls.enable_json))
            logger.addHandler(file_handler)

            # Log de auditoria (apenas para categoria audit)
            if category == "audit":
                audit_file = cls.audit_dir / f"{name}_{datetime.now():%Y%m%d}.log"
                audit_handler = logging.handlers.RotatingFileHandler(
                    audit_file,
                    maxBytes=cls.DEFAULT_MAX_BYTES,
                    backupCount=cls.DEFAULT_BACKUP_COUNT
                )
                audit_handler.setLevel(logging.INFO)  # Audit sempre INFO ou superior
                audit_handler.setFormatter(cls._get_formatter(use_json=True))  # Audit sempre JSON
                logger.addHandler(audit_handler)

        cls._loggers[logger_key] = logger
        return logger

    @classmethod
    def _get_formatter(cls, use_json: bool = False) -> logging.Formatter:
        """
        Cria um formatter para os logs.

        Args:
            use_json: Se True, retorna JSONFormatter; caso contrário, formato texto
        """
        if use_json:
            return JSONFormatter()
        else:
            return logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

    @classmethod
    def shutdown(cls):
        """Fecha todos os handlers e limpa recursos."""
        for logger in cls._loggers.values():
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
        cls._loggers.clear()
        cls._initialized = False


class JSONFormatter(logging.Formatter):
    """
    Formatter que converte logs em JSON estruturado.

    Exemplo de saída:
    {
        "timestamp": "2026-01-15T03:22:45.123456",
        "level": "INFO",
        "logger": "audit.memory_graph",
        "message": "Episode created",
        "episode_id": "ep_123",
        "user_id": "user_456",
        "content_preview": "Cliente reportou problema..."
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Adiciona campos extras se houver
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # Adiciona informações de exceção se houver
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


class AuditLogger:
    """
    Logger especializado para audit trail.

    Registra todas as operações críticas do sistema:
    - Criação/modificação/exclusão de memórias
    - Acessos a dados sensíveis
    - Alterações de configuração
    - Operações de usuários

    Exemplo:
        audit = AuditLogger("memory_graph")
        audit.log_create("episode", episode_id="ep_123", user_id="user_456", content="...")
        audit.log_access("memory", memory_id="mem_789", user_id="user_456", query="...")
    """

    def __init__(self, component: str):
        self.component = component
        self.logger = CortexLogger.get_logger(component, category="audit")

    def log_create(self, entity_type: str, **kwargs):
        """Registra criação de entidade."""
        self._log("CREATE", entity_type, **kwargs)

    def log_update(self, entity_type: str, **kwargs):
        """Registra atualização de entidade."""
        self._log("UPDATE", entity_type, **kwargs)

    def log_delete(self, entity_type: str, **kwargs):
        """Registra exclusão de entidade."""
        self._log("DELETE", entity_type, **kwargs)

    def log_access(self, entity_type: str, **kwargs):
        """Registra acesso a entidade."""
        self._log("ACCESS", entity_type, **kwargs)

    def log_query(self, query_type: str, **kwargs):
        """Registra query/busca."""
        self._log("QUERY", query_type, **kwargs)

    def _log(self, operation: str, entity_type: str, **kwargs):
        """Método interno para logging estruturado."""
        extra_data = {
            "operation": operation,
            "entity_type": entity_type,
            "component": self.component,
            **kwargs
        }

        # Cria LogRecord com extra_data
        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "(audit)",
            0,
            f"{operation} {entity_type}",
            (),
            None
        )
        record.extra_data = extra_data
        self.logger.handle(record)


class PerformanceLogger:
    """
    Logger especializado para métricas de performance.

    Rastreia tempo de execução, uso de recursos, latência de operações.

    Exemplo:
        perf = PerformanceLogger("embedding_service")

        with perf.measure("embed_text"):
            embedding = service.embed(text)

        # Ou manualmente:
        perf.start("recall_memories")
        memories = graph.recall(query)
        perf.end("recall_memories", extra={"count": len(memories)})
    """

    def __init__(self, component: str):
        self.component = component
        self.logger = CortexLogger.get_logger(component, category="performance")
        self._timers: Dict[str, float] = {}

    @contextmanager
    def measure(self, operation: str, **extra):
        """Context manager para medir tempo de operação."""
        import time
        start = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start) * 1000
            self.log_metric(operation, duration_ms=duration_ms, **extra)

    def start(self, operation: str):
        """Inicia timer para operação."""
        import time
        self._timers[operation] = time.time()

    def end(self, operation: str, **extra):
        """Finaliza timer e registra métrica."""
        import time
        if operation not in self._timers:
            self.logger.warning(f"Timer não iniciado para: {operation}")
            return

        duration_ms = (time.time() - self._timers[operation]) * 1000
        del self._timers[operation]
        self.log_metric(operation, duration_ms=duration_ms, **extra)

    def log_metric(self, operation: str, **metrics):
        """Registra métrica de performance."""
        extra_data = {
            "operation": operation,
            "component": self.component,
            **metrics
        }

        # Format metrics for message
        metrics_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
        message = f"Performance: {operation} ({metrics_str})" if metrics_str else f"Performance: {operation}"

        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "(performance)",
            0,
            message,
            (),
            None
        )
        record.extra_data = extra_data
        self.logger.handle(record)


# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# =============================================================================

def get_logger(name: str) -> logging.Logger:
    """
    Função de conveniência para obter logger geral.

    Args:
        name: Nome do módulo/componente

    Returns:
        Logger configurado
    """
    return CortexLogger.get_logger(name, category="general")


def get_audit_logger(component: str) -> AuditLogger:
    """
    Função de conveniência para obter audit logger.

    Args:
        component: Nome do componente

    Returns:
        AuditLogger configurado
    """
    return AuditLogger(component)


def get_performance_logger(component: str) -> PerformanceLogger:
    """
    Função de conveniência para obter performance logger.

    Args:
        component: Nome do componente

    Returns:
        PerformanceLogger configurado
    """
    return PerformanceLogger(component)


# =============================================================================
# INICIALIZAÇÃO AUTOMÁTICA COM VARIÁVEIS DE AMBIENTE
# =============================================================================

def initialize_from_env():
    """
    Inicializa logging a partir de variáveis de ambiente.

    Variáveis suportadas:
    - LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL
    - LOG_DIR: Diretório para logs gerais
    - AUDIT_DIR: Diretório para logs de auditoria
    - LOG_ENABLE_CONSOLE: true/false
    - LOG_ENABLE_FILE: true/false
    - LOG_ENABLE_JSON: true/false
    """
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    log_level = log_level_map.get(log_level_str, logging.INFO)

    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    audit_dir = Path(os.getenv("AUDIT_DIR", "logs/audit"))

    enable_console = os.getenv("LOG_ENABLE_CONSOLE", "true").lower() == "true"
    enable_file = os.getenv("LOG_ENABLE_FILE", "true").lower() == "true"
    enable_json = os.getenv("LOG_ENABLE_JSON", "false").lower() == "true"

    CortexLogger.initialize(
        log_dir=log_dir,
        audit_dir=audit_dir,
        level=log_level,
        enable_console=enable_console,
        enable_file=enable_file,
        enable_json=enable_json
    )


# Inicializa automaticamente na importação
initialize_from_env()
