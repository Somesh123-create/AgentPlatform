from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    mcp_api_url: str = "http://localhost:8001"
    llm_api_url: str = "http://localhost:8003"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


runtime_settings = RuntimeSettings()