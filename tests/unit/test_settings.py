"""Unit tests for settings.py."""
import pytest

from swingtag.settings import Settings

ENV = {"BUCKET": "b", "PUBLIC_BASE_URL": "https://d1.cloudfront.net/", "TOKEN_SECRET": "s"}


def test_settings_required():
    with pytest.raises(RuntimeError, match="BUCKET"):
        Settings.from_env({k: v for k, v in ENV.items() if k != "BUCKET"})


def test_settings_prefix_normalised():
    settings = Settings.from_env({**ENV, "SOURCE_PREFIX": "/source//"})
    assert settings.source_prefix == "source/"
    assert settings.public_prefix == "public/"
    assert settings.config_key == "config/theme.json"
    assert settings.public_base_url == "https://d1.cloudfront.net"
    assert settings.distribution_id == "" and settings.queue_url == ""
