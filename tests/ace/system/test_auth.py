# vim: ts=4:sw=4:et:cc=120

from ace.api import ApiKey
from ace.exceptions import (
    MissingEncryptionSettingsError,
    InvalidPasswordError,
    DuplicateApiKeyNameError,
    InvalidApiKeyError,
    InvalidAccessError,
)

from tests.systems import RemoteACETestSystem

import pytest

# NOTE there's no remote api call for verify_api_key
# each api call implicitly calls verify_api_key
# so calls to verify_api_key are skipped if the system being tested is remote


@pytest.mark.ace_remote
@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_api_key(system, monkeypatch):
    api_key = await system.create_api_key("api_key_1")
    assert isinstance(api_key, ApiKey) and api_key.api_key
    if not isinstance(system, RemoteACETestSystem):
        assert await system.verify_api_key(api_key.api_key)
        assert not await system.verify_api_key(api_key.api_key, is_admin=True)

    admin_api_key = await system.create_api_key("admin_key", is_admin=True)
    if not isinstance(system, RemoteACETestSystem):
        assert await system.verify_api_key(admin_api_key.api_key)
        assert await system.verify_api_key(admin_api_key.api_key, is_admin=True)

    with pytest.raises(DuplicateApiKeyNameError):
        api_key = await system.create_api_key("api_key_1")

    # with pytest.raises(InvalidPasswordError):
    # api_key = await system.create_api_key("t3st", "api_key_2")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_api_key(system, monkeypatch):
    api_key = await system.create_api_key("api_key_1")
    assert isinstance(api_key, ApiKey) and api_key.api_key
    if not isinstance(system, RemoteACETestSystem):
        assert await system.verify_api_key(api_key.api_key)
    assert await system.delete_api_key("api_key_1")
    if not isinstance(system, RemoteACETestSystem):
        assert not await system.verify_api_key(api_key.api_key)
    assert not await system.delete_api_key("api_key_1")

    api_key = await system.create_api_key("api_key_1")
    # with pytest.raises(InvalidPasswordError):
    # await system.delete_api_key("api_key_1")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_api_keys(system):
    api_key_1 = await system.create_api_key("api_key_1")
    api_key_2 = await system.create_api_key("api_key_2")
    keys = {_.name: _ for _ in await system.get_api_keys()}
    assert api_key_1.name in keys
    assert api_key_2.name in keys


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invalid_api_key(system, monkeypatch):
    if not isinstance(system, RemoteACETestSystem):
        pytest.skip("remote only test")

    monkeypatch.setattr(system.api, "api_key", "invalid_key")
    with pytest.raises(InvalidApiKeyError):
        await system.register_alert_system("test")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invalid_access(system, monkeypatch):
    if not isinstance(system, RemoteACETestSystem):
        pytest.skip("remote only test")

    # create a non-admin api key
    api_key = (await system.create_api_key("non admin key")).api_key
    assert api_key

    # switch to the non-admin api key
    monkeypatch.setattr(system.api, "api_key", api_key)
    with pytest.raises(InvalidAccessError):
        # try to create another key with the non-admin key
        await system.create_api_key("should fail")

    # try the same thing but with an unknown key
    monkeypatch.setattr(system.api, "api_key", "invalid_key")
    with pytest.raises(InvalidApiKeyError):
        await system.create_api_key("should fail")
