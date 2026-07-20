from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    EXTRACTION_LLM_PROVIDER: str = "anthropic"
    ANALYSIS_LLM_PROVIDER: str = "anthropic"
    KG_CLASSIFIER_LLM_PROVIDER: str = "openai"
    KG_CLASSIFIER_OPENAI_MODEL: str = "gpt-4o-mini"
    KG_CLASSIFIER_GEMINI_MODEL: str = "gemini-2.5-flash"

    ALLOWED_ORIGINS: str = "http://localhost:8501"
    LOG_LEVEL: str = "INFO"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = Settings()
