from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database connection parameters (no defaults for credentials/secrets)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str  # Mandatory: No default allowed
    POSTGRES_DB: str = "taller_mecanico"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Database Pool and debug settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    SQL_ECHO: bool = False

    # Security and Auth settings
    BCRYPT_ROUNDS: int = 12
    BCRYPT_MAX_CONCURRENCY: int = 4
    JWT_SECRET_KEY: str  # Mandatory: No default allowed
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_SECONDS: int = 1800
    COOKIE_SECURE: bool = False

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
