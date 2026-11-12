import pytest


@pytest.fixture(autouse=True)
def legacy_ui_language(monkeypatch):
    """Existing behavioral assertions use English; Portuguese tests override explicitly."""
    monkeypatch.setenv("LOGINEXUS_LANGUAGE", "en")
