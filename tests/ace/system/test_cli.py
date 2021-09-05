import os.path

from ace.crypto import (
    ENV_CRYPTO_VERIFICATION_KEY,
    ENV_CRYPTO_SALT,
    ENV_CRYPTO_SALT_SIZE,
    ENV_CRYPTO_ITERATIONS,
    ENV_CRYPTO_ENCRYPTED_KEY,
)
from ace.env import ACEOperatingEnvironment, get_base_dir

import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_initialize(monkeypatch, capsys):
    monkeypatch.setenv("ACE_ADMIN_PASSWORD", "test")
    monkeypatch.setenv("ACE_DB_URL", "sqlite+aiosqlite://")
    environment = ACEOperatingEnvironment(["initialize"])
    assert await environment.execute()

    # everything we need will be in stdout
    captured = capsys.readouterr()

    # test the crypto file to make sure it has everything we expect
    for expected_key in [
        ENV_CRYPTO_VERIFICATION_KEY,
        ENV_CRYPTO_SALT,
        ENV_CRYPTO_SALT_SIZE,
        ENV_CRYPTO_ITERATIONS,
        ENV_CRYPTO_ENCRYPTED_KEY,
    ]:
        assert expected_key in captured.out

    assert "ACE_API_KEY=" in captured.out
