# vim: ts=4:sw=4:et:cc=120

from tests.systems import RemoteACETestSystem
from ace.system.exceptions import InvalidApiKeyError, InvalidAccessError

import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invalid_api_key(system, monkeypatch):
    if not isinstance(system, RemoteACETestSystem):
        return

    monkeypatch.setattr(system.api, "api_key", "invalid_key")
    with pytest.raises(InvalidApiKeyError):
        await system.register_alert_system("test")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invalid_access(system, monkeypatch):
    if not isinstance(system, RemoteACETestSystem):
        return

    # create a non-admin api key
    api_key = await system.create_api_key("non admin key")
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
