from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AWS
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_default_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-sonnet-4-20250514-v1:0"

    # Tool API Keys
    tavily_api_key: str = ""
    hunter_api_key: str = ""
    lusha_api_key: str = ""
    exa_api_key: str = ""
    clay_api_key: str = ""

    # Backend
    backend_callback_base_url: str = "http://backend:8080"

    # Agent
    max_search_results: int = 50
    max_enrichment_concurrent: int = 5
    tool_timeout_seconds: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
