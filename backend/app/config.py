from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://llmproxy:dbpassword9090@localhost:5432/litellm"

    # LiteLLM Proxy
    litellm_base_url: str = "http://localhost:4000"
    litellm_admin_api_key: str = "sk-1234"

    # Keycloak / JWT
    keycloak_issuer: str = "http://localhost:8080/realms/litellm"
    keycloak_jwks_uri: str = ""  # auto-derived from issuer if empty
    jwt_audience: str = "litellm-portal"

    # Slack Webhook
    slack_webhook_url: str = ""

    # App
    cors_origins: list[str] = ["http://localhost:3000"]
    debug: bool = False

    # Super user role name in Keycloak token
    super_user_role: str = "super_user"

    model_config = {"env_prefix": "APP_", "env_file": ".env", "extra": "ignore"}

    @property
    def effective_jwks_uri(self) -> str:
        if self.keycloak_jwks_uri:
            return self.keycloak_jwks_uri
        return f"{self.keycloak_issuer}/protocol/openid-connect/certs"


settings = Settings()
