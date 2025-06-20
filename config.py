"""
Configuration settings for the dehumidifier assistant
"""
import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "supersecret")
    
    # Redis Configuration
    REDIS_URL = os.getenv("REDIS_URL")
    
    # Session Configuration
    SESSION_TYPE = 'redis' if REDIS_URL else 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'dehum:'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Rate Limiting
    MAX_DAILY_QUESTIONS = int(os.getenv("MAX_DAILY_QUESTIONS", "20"))
    MAX_DAILY_TOKENS = int(os.getenv("MAX_DAILY_TOKENS", "50000"))
    
    # Data Retention
    CONVERSATION_HISTORY_TTL = timedelta(days=7)
    USAGE_STATS_TTL = timedelta(hours=25)
    
    # Input Validation
    MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", "400"))
    
    # AI Configuration
    USE_OPENAI = os.getenv("USE_OPENAI", "true").lower() == "true"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "o3")
    
    # Ollama Configuration (fallback)
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")
    
    # Context Optimization
    MAX_CONVERSATION_EXCHANGES = int(os.getenv("MAX_CONVERSATION_EXCHANGES", "6"))
    MAX_TOTAL_CONTEXT_MESSAGES = int(os.getenv("MAX_TOTAL_CONTEXT_MESSAGES", "10"))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    
# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'default').lower()
    return config.get(env, config['default']) 