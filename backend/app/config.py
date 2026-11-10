"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    # Read backend/.env first, then the repo-root .env. Later files win, so a
    # backend-local .env can override shared root settings.
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(BACKEND_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — PostgreSQL only. No default: the app must not silently fall
    # back to a local file DB when DATABASE_URL is missing or misconfigured.
    database_url: str

    # Storage
    upload_dir: str = "./storage/uploads"
    processed_dir: str = "./storage/processed"
    image_retention_hours: int = 0

    # Image validation / normalization
    max_upload_mb: int = 10
    target_image_size: int = 1024
    allowed_content_types: tuple[str, ...] = ("image/jpeg", "image/png")

    # ------------------------------------------------------------------ auth
    # Signing key for access tokens. NO DEFAULT: a fallback secret is how a development
    # shortcut reaches production and lets anyone forge a token for any account. The app
    # refuses to start without it -- set JWT_SECRET in backend/.env.
    jwt_secret: str
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days — a farmer should not re-login weekly

    # --- Sarvam AI text-to-speech (Weeks 5-6) ---
    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_model: str = "bulbul:v2"
    sarvam_speaker: str = "anushka"
    sarvam_timeout_seconds: float = 20.0

    # --- Supabase Cloud Storage ---
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_bucket: str = "soil-images"

    # App
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,https://soil-health-pwa.onrender.com"

    @field_validator("database_url")
    @classmethod
    def _require_postgres(cls, v: str) -> str:
        """Reject non-PostgreSQL URLs in production, allowing sqlite:// in test suites."""
        if not v.startswith(("postgresql://", "postgresql+psycopg2://", "postgresql+psycopg://", "sqlite://", "sqlite:")):
            raise ValueError(
                f"DATABASE_URL must be a PostgreSQL or SQLite URL, got {v.split('://')[0]!r}://... "
                "Expected postgresql+psycopg2://user:pass@host:5432/dbname"
            )
        return v

    @field_validator("jwt_secret")
    @classmethod
    def _reject_weak_secret(cls, v: str) -> str:
        """Refuse obviously placeholder secrets."""
        weak = {"change-me", "changeme", "secret", "your_secret_here", "test"}
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if v.lower() in weak:
            raise ValueError("JWT_SECRET is a placeholder value. Generate a real secret.")
        return v

    @property
    def upload_path(self) -> Path:
        p = (BACKEND_ROOT / self.upload_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def processed_path(self) -> Path:
        p = (BACKEND_ROOT / self.processed_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
