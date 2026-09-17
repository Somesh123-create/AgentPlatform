from pydantic_settings import BaseSettings, SettingsConfigDict


class BuildSettings(BaseSettings):
    container_engine: str = "podman"
    build_image_namespace: str = "agenthub"
    build_timeout_seconds: int = 600
    build_log_limit: int = 20000
    runtime_timeout_seconds: int = 90

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


build_settings = BuildSettings()