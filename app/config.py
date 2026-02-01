from typing import Optional
from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    configuration for the llm guardrail proxy
    using pydantic for validation and env var loading
    """
    # api keys and secrets - now optional since user provides via request
    GEMINI_API_KEY: Optional[SecretStr] = None
    
    # timeout settings
    GUARDRAIL_TIMEOUT_SECONDS: float = 2.0
    GEMINI_TIMEOUT_SECONDS: float = 30.0
    
    # rate limiting
    RATE_LIMIT: str = "10/minute"
    
    # validation limits
    MAX_PROMPT_LENGTH: int = 10000
    
    # environment
    ENVIRONMENT: str = "development"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# global settings instance
settings = Settings()
