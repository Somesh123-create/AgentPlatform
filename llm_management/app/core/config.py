from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLM Management Service"
    app_env: str = "development"
    debug: bool = False
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    auth_token_url: str = "http://localhost:8000/auth/login"
    llm_encryption_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
