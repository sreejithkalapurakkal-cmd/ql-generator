from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://qlgen:qlgen_pass@localhost:5432/qlgen"
    DATABASE_URL_SYNC: str = "postgresql://qlgen:qlgen_pass@localhost:5432/qlgen"

    # AWS Bedrock
    AWS_REGION: str = "us-east-1"
    BEDROCK_MODEL_ID: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    BEDROCK_EMBEDDING_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
    EMBEDDING_DIMENSION: int = 1024

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
    GOOGLE_PLACES_API_KEY: str = ""
    SIMFIN_API_KEY: str = ""
    FMP_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    FRED_API_KEY: str = ""

    class Config:
        env_file = ".env", "../.env", "backend/.env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_settings() -> Settings:
    return Settings()
