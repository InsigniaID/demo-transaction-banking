from pydantic_settings import BaseSettings
from decouple import config


class Settings(BaseSettings):
    # Database
    db_user: str = config("DB_USER")
    db_pass: str = config("DB_PASS")
    db_host: str = config("DB_HOST")
    db_port: str = config("DB_PORT")
    db_name: str = config("DB_NAME")
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    # Security
    secret_key: str = config("SEC_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Kafka
    kafka_bootstrap_servers: str = config("KAFKA_BOOTSTRAP_SERVERS")
    kafka_username: str = config("KAFKA_USERNAME")
    kafka_password: str = config("KAFKA_PASSWORD")
    kafka_topic: str = config("KAFKA_TOPIC")
    
    # App
    app_name: str = "Banking Transaction Demo"
    app_version: str = "1.0.0"
    
    class Config:
        case_sensitive = False


settings = Settings()