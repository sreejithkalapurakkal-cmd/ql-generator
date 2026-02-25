from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://qlgen:qlgen_pass@localhost:5432/qlgen"
    DATABASE_URL_SYNC: str = "postgresql://qlgen:qlgen_pass@localhost:5432/qlgen"

    # AWS Bedrock
    AWS_REGION: str = "us-east-1"
    BEDROCK_MODEL_ID: str = "anthropic.claude-sonnet-4-20250514"

    # CORS
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

    # External APIs
    APOLLO_API_KEY: str = ""
    APOLLO_BASE_URL: str = "https://api.apollo.io/v1"
    EXA_API_KEY: str = ""
    EXA_BASE_URL: str = "https://api.exa.ai"
    HUNTER_API_KEY: str = ""
    HUNTER_BASE_URL: str = "https://api.hunter.io/v2"
    LUSHA_API_KEY: str = ""
    LUSHA_BASE_URL: str = "https://api.lusha.com"
    CLAY_API_KEY: str = ""
    CLAY_BASE_URL: str = "https://api.clay.com"
    TAVILY_API_KEY: str = ""
    TAVILY_BASE_URL: str = "https://api.tavily.com"

    class Config:
        env_file = ".env", "../.env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
