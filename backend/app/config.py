from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    broker_host: str = "127.0.0.1"
    broker_port: int = 1883
    broker_ws_port: int = 9001
    database_url: str = "sqlite+aiosqlite:///iot.db"
    redis_url: str = ""
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost"]


settings = Settings()
