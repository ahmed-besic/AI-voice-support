from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=('services/api/.env', '.env'),
        env_file_encoding='utf-8',
        extra='ignore',
    )

    app_name: str = 'voice-support-api'
    database_url: str = Field(default='postgresql+asyncpg://postgres:postgres@localhost:5432/voice_support', alias='DATABASE_URL')
    jwt_secret: str = Field(default='dev-jwt-secret', alias='JWT_SECRET')
    field_encryption_key: str = Field(default='nP9pizl1otA3KCHhOcY4BA9J8bTA6S_e8x32m0rmI2g=', alias='FIELD_ENCRYPTION_KEY')
    default_google_api_key: str | None = Field(default=None, alias='DEFAULT_GOOGLE_API_KEY')
    demo_site_id: str = Field(default='demo-site', alias='DEMO_SITE_ID')
    demo_site_name: str = Field(default='Demo Site', alias='DEMO_SITE_NAME')
    demo_allowed_origins: str = Field(default='http://localhost:3000', alias='DEMO_ALLOWED_ORIGINS')
    demo_monthly_budget: float = Field(default=25.0, alias='DEMO_MONTHLY_BUDGET')
    demo_max_session_duration_seconds: int = Field(default=480, alias='DEMO_MAX_SESSION_DURATION_SECONDS')
    google_realtime_model: str = Field(default='gemini-3.1-flash-live-preview', alias='GOOGLE_REALTIME_MODEL')
    google_text_model: str = Field(default='gemini-2.5-flash', alias='GOOGLE_TEXT_MODEL')
    google_summary_model: str = Field(default='gemini-2.5-flash-lite', alias='GOOGLE_SUMMARY_MODEL')
    strict_policy_path: str = Field(default='services/api/policies/default.yaml', alias='STRICT_POLICY_PATH')
    strict_policy_override_path: str | None = Field(default=None, alias='STRICT_POLICY_OVERRIDE_PATH')

    @property
    def demo_allowed_origin_list(self) -> list[str]:
        origins: list[str] = []
        for origin in self.demo_allowed_origins.split(','):
            normalized = origin.strip()
            if normalized:
                origins.append(normalized)
        return origins


_SETTINGS = Settings()


def get_settings() -> Settings:
    return _SETTINGS
