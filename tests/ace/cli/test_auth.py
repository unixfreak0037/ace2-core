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
async def test_create_api_key(monkeypatch):
    monkeypatch.setenv(ACE_ADMIN_PASSWORD, "test")
    environment = ACEOperatingEnvironment(["api-key", "create", "test"])
    assert await environment.execute()
