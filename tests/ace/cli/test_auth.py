from ace.constants import ACE_ADMIN_PASSWORD
from ace.env import ACEOperatingEnvironment

TEST_PASSWORD = "test"

import pytest


@pytest.fixture(scope="function")
async def initialize_crypto():
    encryption_settings = await initialize_encryption_settings(TEST_PASSWORD)
    system = await get_system()

    verification_key_encoded = base64.b64encode(system.encryption_settings.verification_key).decode()
    salt_encoded = base64.b64encode(system.encryption_settings.salt).decode()
    salt_size_encoded = str(system.encryption_settings.salt_size)
    iterations_encoded = str(system.encryption_settings.iterations)
    encrypted_key_encoded = base64.b64encode(system.encryption_settings.encrypted_key).decode()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_api_key(monkeypatch, capsys):
    monkeypatch.setenv(ACE_ADMIN_PASSWORD, TEST_PASSWORD)
    environment = ACEOperatingEnvironment(
        ["api-key", "create", "test_key_1", "--description", "automation functional key", "--is-admin"]
    )
    assert await environment.execute()
    captured = capsys.readouterr()

    # grab the api key we got from stdout
    api_key = captured.out.strip()

    environment = ACEOperatingEnvironment(["api-key", "list"])
    assert await environment.execute()
    captured = capsys.readouterr()

    assert "test_key_1" in captured.out
    assert "automation functional key" in captured.out
    assert "(admin)" in captured.out

    environment = ACEOperatingEnvironment(["api-key", "delete", "test_key_1"])
    assert await environment.execute()
    captured = capsys.readouterr()

    assert "key deleted" in captured.out

    # make sure non-admin keys can be created
    environment = ACEOperatingEnvironment(
        ["api-key", "create", "test_key_1", "--description", "automation functional key"]
    )
    assert await environment.execute()
    environment = ACEOperatingEnvironment(["api-key", "list"])
    assert await environment.execute()
    captured = capsys.readouterr()

    assert "test_key_1" in captured.out
    assert "(admin)" not in captured.out

    # test deleting an unknown key
    environment = ACEOperatingEnvironment(["api-key", "delete", "test_key_2"])
    assert await environment.execute()
    captured = capsys.readouterr()

    assert "key not found" in captured.out
