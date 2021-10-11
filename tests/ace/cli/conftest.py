from ace.crypto import initialize_encryption_settings
from ace.env import get_env
from tests.systems import DatabaseACETestSystem

import pytest


@pytest.fixture(scope="function", autouse=True)
async def initialize_cli_environment(monkeypatch):
    monkeypatch.setenv("ACE_ADMIN_PASSWORD", "test")
    monkeypatch.setenv("ACE_DB_URL", "sqlite+aiosqlite://")
    system = DatabaseACETestSystem()
    system.encryption_settings = await initialize_encryption_settings("test")
    system.encryption_settings.load_aes_key("test")
    await system.initialize()
    await system.start()
    await system.reset()
    get_env().set_system(system)
    yield
    await system.stop()
