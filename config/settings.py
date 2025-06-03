"""
Centralized configuration management for NovelNexus.

This module provides environment-based configuration classes and utilities
for managing application settings across different deployment environments.
"""

import os
import logging
from typing import Dict, Any, Optional
import dotenv
from dataclasses import dataclass, field
from pathlib import Path

# Load environment variables from .env file
try:
    dotenv.load_dotenv(override=True)
    print("Successfully loaded .env file")
except Exception as e:
    print(f"Could not load .env file: {str(e)}")

@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///novelnexus.db"))
    pool_size: int = field(default_factory=lambda: int(os.environ.get("DB_POOL_SIZE", "10")))
    max_overflow: int = field(default_factory=lambda: int(os.environ.get("DB_MAX_OVERFLOW", "20")))
    echo: bool = field(default_factory=lambda: os.environ.get("DB_ECHO", "False").lower() == "true")

@dataclass
class CeleryConfig:
    """Celery task queue configuration."""
    broker_url: str = field(default_factory=lambda: os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"))
    result_backend: str = field(default_factory=lambda: os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"))
    task_serializer: str = "json"
    accept_content: list = field(default_factory=lambda: ["json"])
    result_serializer: str = "json"
    enable_utc: bool = True
    task_track_started: bool = True
    task_time_limit: int = field(default_factory=lambda: int(os.environ.get("CELERY_TASK_TIME_LIMIT", "18000")))
    worker_max_tasks_per_child: int = field(default_factory=lambda: int(os.environ.get("CELERY_WORKER_MAX_TASKS", "1")))

@dataclass
class OpenAIConfig:
    """OpenAI API configuration."""
    api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    base_url: Optional[str] = field(default_factory=lambda: os.environ.get("OPENAI_BASE_URL"))
    organization: Optional[str] = field(default_factory=lambda: os.environ.get("OPENAI_ORGANIZATION"))
    default_model: str = field(default_factory=lambda: os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o"))
    embedding_model: str = field(default_factory=lambda: os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"))
    max_retries: int = field(default_factory=lambda: int(os.environ.get("OPENAI_MAX_RETRIES", "3")))
    timeout: int = field(default_factory=lambda: int(os.environ.get("OPENAI_TIMEOUT", "60")))

@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = field(default_factory=lambda: os.environ.get("LOG_FILE", "app.log"))
    max_file_size: int = field(default_factory=lambda: int(os.environ.get("LOG_MAX_SIZE", "10485760")))  # 10MB
    backup_count: int = field(default_factory=lambda: int(os.environ.get("LOG_BACKUP_COUNT", "5")))
    buffer_size: int = field(default_factory=lambda: int(os.environ.get("LOG_BUFFER_SIZE", "500")))

@dataclass
class SecurityConfig:
    """Security and authentication configuration."""
    secret_key: str = field(default_factory=lambda: os.environ.get("SECRET_KEY", "novelNexusSecretKey12345"))
    session_timeout: int = field(default_factory=lambda: int(os.environ.get("SESSION_TIMEOUT", "3600")))
    csrf_protection: bool = field(default_factory=lambda: os.environ.get("CSRF_PROTECTION", "True").lower() == "true")
    rate_limit_enabled: bool = field(default_factory=lambda: os.environ.get("RATE_LIMIT_ENABLED", "False").lower() == "true")
    rate_limit_default: str = field(default_factory=lambda: os.environ.get("RATE_LIMIT_DEFAULT", "100 per hour"))

class BaseConfig:
    """Base configuration class with common settings."""
    
    def __init__(self):
        self.database = DatabaseConfig()
        self.celery = CeleryConfig()
        self.openai = OpenAIConfig()
        self.logging = LoggingConfig()
        self.security = SecurityConfig()
        
        # Flask settings
        self.flask_host = os.environ.get("HOST", "0.0.0.0")
        self.flask_port = int(os.environ.get("PORT", "5000"))
        self.flask_debug = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
        
        # Application settings
        self.app_name = "NovelNexus"
        self.app_version = "1.0.0"
        self.memory_data_dir = os.environ.get("MEMORY_DATA_DIR", "memory_data")
        self.max_project_sessions = int(os.environ.get("MAX_PROJECT_SESSIONS", "10"))
        
        # Model settings
        self.use_openai = os.environ.get("USE_OPENAI", "True").lower() == "true"
        self.use_gpu = os.environ.get("USE_GPU", "False").lower() == "true"
        
    def validate(self) -> Dict[str, Any]:
        """Validate configuration and return any errors."""
        errors = {}
        
        # Validate OpenAI configuration
        if self.use_openai and not self.openai.api_key:
            errors["openai_api_key"] = "OpenAI API key is required when USE_OPENAI is True"
        
        # Validate directories
        try:
            Path(self.memory_data_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors["memory_data_dir"] = f"Cannot create memory data directory: {str(e)}"
        
        # Validate secret key strength
        if len(self.security.secret_key) < 16:
            errors["secret_key"] = "Secret key should be at least 16 characters long"
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for easy access."""
        return {
            "database": self.database.__dict__,
            "celery": self.celery.__dict__,
            "openai": self.openai.__dict__,
            "logging": self.logging.__dict__,
            "security": self.security.__dict__,
            "flask": {
                "host": self.flask_host,
                "port": self.flask_port,
                "debug": self.flask_debug
            },
            "app": {
                "name": self.app_name,
                "version": self.app_version,
                "memory_data_dir": self.memory_data_dir,
                "max_project_sessions": self.max_project_sessions
            },
            "model": {
                "use_openai": self.use_openai,
                "use_gpu": self.use_gpu
            }
        }

class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""
    
    def __init__(self):
        super().__init__()
        self.flask_debug = True
        self.logging.level = "DEBUG"
        # Override some settings for development
        self.database.echo = True
        self.celery.task_time_limit = 3600  # 1 hour for development

class ProductionConfig(BaseConfig):
    """Production environment configuration."""
    
    def __init__(self):
        super().__init__()
        self.flask_debug = False
        self.logging.level = "INFO"
        # Production-specific settings
        self.security.csrf_protection = True
        self.security.rate_limit_enabled = True

class TestingConfig(BaseConfig):
    """Testing environment configuration."""
    
    def __init__(self):
        super().__init__()
        self.flask_debug = True
        self.logging.level = "DEBUG"
        # Override for testing
        self.database.url = "sqlite:///:memory:"
        self.celery.broker_url = "memory://"
        self.celery.result_backend = "cache+memory://"

# Configuration factory
def get_config(env: Optional[str] = None) -> BaseConfig:
    """
    Get configuration based on environment.
    
    Args:
        env: Environment name (development, production, testing)
        
    Returns:
        Configuration instance
    """
    if env is None:
        env = os.environ.get("FLASK_ENV", "development")
    
    config_map = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig
    }
    
    config_class = config_map.get(env.lower(), DevelopmentConfig)
    return config_class()

# Global configuration instance
config = get_config()

# Configuration validation
config_errors = config.validate()
if config_errors:
    logger = logging.getLogger(__name__)
    logger.warning(f"Configuration validation errors: {config_errors}")

def setup_logging(config: BaseConfig) -> None:
    """Setup logging based on configuration."""
    from logging.handlers import RotatingFileHandler
    
    # Create formatter
    formatter = logging.Formatter(config.logging.format)
    
    # Setup file handler with rotation
    file_handler = RotatingFileHandler(
        config.logging.file_path,
        maxBytes=config.logging.max_file_size,
        backupCount=config.logging.backup_count
    )
    file_handler.setFormatter(formatter)
    
    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.logging.level.upper()))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels for key components
    logging.getLogger('orchestration.workflow').setLevel(logging.DEBUG)
    logging.getLogger('agents').setLevel(logging.DEBUG)
    logging.getLogger('hubs.central_hub').setLevel(logging.DEBUG)
    logging.getLogger('memory.dynamic_memory').setLevel(logging.DEBUG)

def get_celery_config() -> Dict[str, Any]:
    """Get Celery configuration dictionary."""
    celery_config = config.celery
    return {
        'broker_url': celery_config.broker_url,
        'result_backend': celery_config.result_backend,
        'task_serializer': celery_config.task_serializer,
        'accept_content': celery_config.accept_content,
        'result_serializer': celery_config.result_serializer,
        'enable_utc': celery_config.enable_utc,
        'task_track_started': celery_config.task_track_started,
        'task_time_limit': celery_config.task_time_limit,
        'worker_max_tasks_per_child': celery_config.worker_max_tasks_per_child
    }

def create_directories() -> None:
    """Create necessary directories for the application."""
    directories = [
        config.memory_data_dir,
        "logs",
        "temp",
        "uploads"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

# Initialize directories on import
create_directories()
