"""
Configuration settings for the Dehumidifier AI Service
"""

import os
from typing import Optional

class Config:
    """Configuration class for the AI service"""
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Alternative AI Provider Keys
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    
    # Service Configuration
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL")
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