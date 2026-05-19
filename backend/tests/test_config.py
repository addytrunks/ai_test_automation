from app.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRES_MINUTES", "60")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("VAMPI_BASE_URL", "http://localhost:5001")

    s = Settings()

    assert s.database_url == "sqlite+aiosqlite:///:memory:"
    assert s.jwt_secret == "test-secret"
    assert s.jwt_expires_minutes == 60
    assert s.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
