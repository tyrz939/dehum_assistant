"""
Configuration settings for the Dehumidifier AI Service
"""

import os
from typing import Optional

class Config:
    """Configuration class for the AI service"""
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Service Configuration
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.3"))
    SERVICE_HOST: str = os.getenv("SERVICE_HOST", "0.0.0.0")
    SERVICE_PORT: int = int(os.getenv("PORT", 8000))
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
    MAX_TOKENS_PER_REQUEST: int = int(os.getenv("MAX_TOKENS_PER_REQUEST", "1000"))
    
    # CORS Settings
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    
    # WordPress Integration
    WORDPRESS_URL: str = os.getenv("WORDPRESS_URL", "http://localhost")
    
    THINKING_MODEL: str = os.getenv("THINKING_MODEL")
    
    # RAG Configuration
    RAG_ENABLED: bool = os.getenv("RAG_ENABLED", "True").lower() in ("true", "1", "yes")
    RAG_CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", "500"))
    RAG_CHUNK_OVERLAP: int = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "3"))
    
    # GPT-5 Optimization Settings
    GPT5_REASONING_EFFORT: str = os.getenv("GPT5_REASONING_EFFORT", "minimal")  # minimal, low, medium, high
    GPT5_VERBOSITY: str = os.getenv("GPT5_VERBOSITY", "low")                   # low, medium, high
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration"""
        if not cls.OPENAI_API_KEY:
            print("WARNING: OPENAI_API_KEY not set. The service may not function properly.")
            return False
        return True
    
    @classmethod
    def get_cors_origins(cls) -> list:
        """Get CORS origins as a list"""
        if cls.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in cls.CORS_ORIGINS.split(",")]

# Validate configuration on import
config = Config()
config.validate() 