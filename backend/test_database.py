import pytest
from sqlalchemy.engine import URL

import main
from database import DatabaseConfigurationError, DatabaseSettings, dispose_database


def test_liveness_does_not_require_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    dispose_database()

    assert main.root()["status"] == "ok"


def test_database_url_is_required_without_disclosing_environment(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL is required"):
        DatabaseSettings.from_environment()


@pytest.mark.parametrize(
    "database_url",
    [
        "not a url",
        "sqlite:///local.db",
        "postgresql+psycopg://db.example.invalid",
    ],
)
def test_database_url_rejects_invalid_or_unsupported_values(monkeypatch, database_url):
    monkeypatch.setenv("DATABASE_URL", database_url)

    with pytest.raises(DatabaseConfigurationError) as error:
        DatabaseSettings.from_environment()

    assert database_url not in str(error.value)


def test_database_settings_repr_redacts_credentials(monkeypatch):
    secret = "unit-test-secret-marker"
    full_url = URL.create(
        "postgresql+psycopg",
        username="app",
        password=secret,
        host="db",
        port=5432,
        database="robodovod",
    ).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", full_url)

    settings = DatabaseSettings.from_environment()

    assert repr(settings) == "DatabaseSettings(url=<redacted>)"
    assert secret not in repr(settings)
    assert full_url not in repr(settings)
