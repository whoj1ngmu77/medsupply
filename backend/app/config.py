from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = ""
    postgres_password: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = ""

    mongo_user: str = ""
    mongo_password: str = ""
    mongo_host: str = "localhost"
    mongo_port: int = 27017
    mongo_db: str = "medsupply_incidents"

    jwt_secret: str = "dev_only"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    enable_dbms_demos: bool = True

    # Full-URL overrides for managed databases (Neon, MongoDB Atlas).
    # When set, these win over the host/port/user fields above, which
    # cannot express sslmode, SRV records or pooled endpoints.
    database_url: str = ""
    mongo_uri: str = ""

    @property
    def postgres_url(self) -> str:
        if self.database_url:
            # SQLAlchemy needs the psycopg3 driver named explicitly;
            # managed providers hand out a bare postgresql:// URL.
            url = self.database_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg://", 1)
            return url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def mongo_url(self) -> str:
        if self.mongo_uri:
            return self.mongo_uri
        # A locally-started mongod runs without auth; the containerised one
        # has a root user. Send credentials only when they are configured.
        if self.mongo_user and self.mongo_password:
            return (
                f"mongodb://{self.mongo_user}:{self.mongo_password}"
                f"@{self.mongo_host}:{self.mongo_port}/?authSource=admin"
            )
        return f"mongodb://{self.mongo_host}:{self.mongo_port}"


settings = Settings()
