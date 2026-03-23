from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Inventory SaaS"
    DATABASE_URL: str
    SECRET_KEY: str = "sua_chave_secreta_super_segura_aqui_para_dev"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    WEBHOOK_API_KEY: str = "sua_chave_de_api_secreta_para_webhooks" # Substitua no .env em produção
    
    # URL do Ollama. Permite sobrescrever no .env se for expor remotamente
    OLLAMA_URL: str = "http://localhost:11434"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
