from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    MONGODB_URI: str = "mongodb://localhost:27017"
    JWT_SECRET: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days

    HIVEMQ_HOST: str = ""
    HIVEMQ_PORT: int = 8883
    HIVEMQ_USER: str = ""
    HIVEMQ_PASSWORD: str = ""
    WS_MQTT_PORT: int = 8884  # Puerto WebSocket MQTT de HiveMQ (para clientes directos)

    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    FIREBASE_PROJECT_ID: str = "noray4"
    ENVIRONMENT: str = "development"


settings = Settings()
