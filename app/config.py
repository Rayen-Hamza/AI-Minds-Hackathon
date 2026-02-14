from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True

    cors_origins: list[str] = ["http://localhost:3000"]

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
