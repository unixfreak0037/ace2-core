# vim: ts=4:sw=4:et:cc=120

from ace.system.exceptions import MissingEncryptionSettingsError, InvalidPasswordError, DuplicateApiKeyNameError

import pytest


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_api_key(system, monkeypatch):
    api_key = await system.create_api_key("api_key_1")
    assert isinstance(api_key, str) and api_key
    assert await system.verify_api_key(api_key)
    assert not await system.verify_api_key(api_key, is_admin=True)

    admin_api_key = await system.create_api_key("admin_key", is_admin=True)
    assert await system.verify_api_key(admin_api_key)
    assert await system.verify_api_key(admin_api_key, is_admin=True)

    with pytest.raises(DuplicateApiKeyNameError):
        api_key = await system.create_api_key("api_key_1")

    # with pytest.raises(InvalidPasswordError):
    # api_key = await system.create_api_key("t3st", "api_key_2")

    # the client side of the remote system interface does not have encryption settings
    if system.encryption_settings:
        monkeypatch.setattr(system, "encryption_settings", None)
        with pytest.raises(MissingEncryptionSettingsError):
            api_key = await system.create_api_key("api_key_3")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_api_key(system, monkeypatch):
    api_key = await system.create_api_key("api_key_1")
    assert isinstance(api_key, str) and api_key
    assert await system.verify_api_key(api_key)
    assert await system.delete_api_key("api_key_1")
    assert not await system.verify_api_key(api_key)
    assert not await system.delete_api_key("api_key_1")

    api_key = await system.create_api_key("api_key_1")
    # with pytest.raises(InvalidPasswordError):
    # await system.delete_api_key("api_key_1")

    # the client side of the remote system interface does not have encryption settings
    if system.encryption_settings:
        monkeypatch.setattr(system, "encryption_settings", None)
        with pytest.raises(MissingEncryptionSettingsError):
            api_key = await system.delete_api_key("api_key_1")
