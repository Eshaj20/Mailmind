from app.core.config import Settings


def test_database_url_normalizes_render_postgres_scheme():
    settings = Settings(
        database_url="postgres://user:password@host:5432/mailmind",
        secret_key="test-secret-key-at-least-16",
    )

    assert settings.database_url == "postgresql+psycopg://user:password@host:5432/mailmind"


def test_database_url_normalizes_plain_postgresql_scheme():
    settings = Settings(
        database_url="postgresql://user:password@host:5432/mailmind",
        secret_key="test-secret-key-at-least-16",
    )

    assert settings.database_url == "postgresql+psycopg://user:password@host:5432/mailmind"


def test_database_url_keeps_explicit_driver_scheme():
    settings = Settings(
        database_url="postgresql+psycopg://user:password@host:5432/mailmind",
        secret_key="test-secret-key-at-least-16",
    )

    assert settings.database_url == "postgresql+psycopg://user:password@host:5432/mailmind"