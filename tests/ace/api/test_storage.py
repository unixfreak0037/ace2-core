# vim: ts=4:sw=4:et:cc=120
#

from ace.api import get_api
from ace.data_model import ContentMetadata

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_store_content(tmpdir):
    sha256 = await get_api().store_content("test", ContentMetadata(name="test.txt"))
    assert sha256 == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

    sha256 = await get_api().store_content(b"test", ContentMetadata(name="test.txt"))
    assert sha256 == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

    path = str(tmpdir / "test.txt")
    with open(path, "wb") as fp:
        fp.write(b"test")

    with open(path, "rb") as fp:
        sha256 = await get_api().store_content(fp, ContentMetadata(name="test.txt"))
        assert sha256 == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_load_file(tmpdir):
    sha256 = await get_api().store_content("test", ContentMetadata(name="test.txt"))
    assert sha256 == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

    path = str(tmpdir / "test.txt")
    await get_api().load_file(sha256, path)
    with open(path, "rb") as fp:
        assert fp.read() == b"test"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_save_file(tmpdir):

    path = str(tmpdir / "test.txt")
    with open(path, "wb") as fp:
        fp.write(b"test")

    sha256 = await get_api().save_file(path)
    sha256 == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
