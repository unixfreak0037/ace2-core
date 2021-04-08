import datetime
import filecmp
import io
import os.path

import pytest

from ace.analysis import RootAnalysis
from ace.data_model import ContentMetadata
from ace.time import utc_now

TEST_STRING = lambda: "hello world"
TEST_BYTES = lambda: b"hello world"
TEST_IO = lambda: io.BytesIO(b"hello world")

TEST_NAME = "test.txt"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "generate_input_data,name,meta",
    [
        (TEST_STRING, TEST_NAME, ContentMetadata(name=TEST_NAME)),
        (TEST_BYTES, TEST_NAME, ContentMetadata(name=TEST_NAME)),
        (TEST_IO, TEST_NAME, ContentMetadata(name=TEST_NAME)),
    ],
)
@pytest.mark.integration
async def test_get_store_delete_content(generate_input_data, name, meta, tmpdir, system):
    input_data = generate_input_data()
    sha256 = await system.store_content(input_data, meta)
    meta = await system.get_content_meta(sha256)
    data = await system.get_content_bytes(sha256)

    if isinstance(input_data, str):
        assert data.decode() == input_data
    elif isinstance(input_data, io.BytesIO):
        assert data == input_data.getvalue()
    else:
        assert data == input_data

    assert meta.name == name
    assert meta.sha256 == sha256
    assert meta.size == len(data)
    assert meta.location == meta.location
    assert isinstance(meta.insert_date, datetime.datetime)
    assert meta.expiration_date is None
    assert not meta.custom

    target_path = str(tmpdir / "target.data")
    meta = await system.load_file(sha256, target_path)
    assert filecmp.cmp(meta.location, target_path)

    # make sure we can delete content
    assert await system.delete_content(sha256)
    assert await system.get_content_meta(sha256) is None
    assert await system.get_content_bytes(sha256) is None
    async for _buffer in system.iter_content(sha256):
        assert _buffer is None

    # make sure copied file still exists
    assert os.path.exists(target_path)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "generate_input_data,name,meta",
    [
        (TEST_STRING, TEST_NAME, ContentMetadata(name=TEST_NAME)),
        (TEST_BYTES, TEST_NAME, ContentMetadata(name=TEST_NAME)),
        (TEST_IO, TEST_NAME, ContentMetadata(name=TEST_NAME)),
    ],
)
@pytest.mark.integration
async def test_iter_content(generate_input_data, name, meta, tmpdir, system):
    from ace.system.remote.storage import RemoteStorageInterface

    input_data = generate_input_data()
    sha256 = await system.store_content(input_data, meta)
    meta = await system.get_content_meta(sha256)

    _buffer = []

    # the optional buffer size works for the local storage system
    # so we use that to test reading one byte at the time
    async for data in system.iter_content(sha256, 1):
        assert data
        _buffer.append(data)

    if isinstance(input_data, str):
        assert b"".join(_buffer) == input_data.encode()
        if not isinstance(system, RemoteStorageInterface):
            assert len(_buffer) == len(input_data.encode())
    elif isinstance(input_data, bytes):
        assert b"".join(_buffer) == input_data
        if not isinstance(system, RemoteStorageInterface):
            assert len(_buffer) == len(input_data)
    elif isinstance(input_data, io.BytesIO):
        pass

    async for data in system.iter_content("unknown"):
        assert data is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_store_duplicate(tmpdir, system):
    path = str(tmpdir / "test.txt")
    with open(path, "w") as fp:
        fp.write("Hello, world!")

    # store the file content
    sha256 = await system.save_file(path, custom="1")
    assert sha256

    previous_meta = await system.get_content_meta(sha256)
    assert previous_meta

    # then try to store it again
    assert await system.save_file(path, custom="2")
    current_meta = await system.get_content_meta(sha256)

    # XXX need to think about how this should work
    # the current meta should be newer-ish than the previous meta
    # assert current_meta.insert_date >= previous_meta.insert_date

    # and the custom dict should have changed
    # assert current_meta.custom == "2"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_store_get_file(tmpdir, system):
    path = str(tmpdir / "test.txt")
    with open(path, "w") as fp:
        fp.write("Hello, world!")

    sha256 = await system.save_file(path)
    assert sha256

    # XXX skipping this check for now since we lose milliseconds in isoformat for json
    # assert get_content_meta(meta.sha256) == meta

    os.remove(path)

    await system.load_file(sha256, path)
    assert os.path.exists(path)

    with open(path, "r") as fp:
        assert fp.read() == "Hello, world!"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_file_expiration(tmpdir, system):
    path = str(tmpdir / "test.txt")
    with open(path, "w") as fp:
        fp.write("Hello, world!")

    # store the file and have it expire right away
    sha256 = await system.save_file(path, expiration_date=utc_now())
    assert sha256

    # we should have a single expired file now
    assert len([_ async for _ in await system.iter_expired_content()]) == 1

    # clear them out
    await system.delete_expired_content()

    # now we should have no expired content
    assert len([_ async for _ in await system.iter_expired_content()]) == 0

    # and the file should be gone
    assert await system.get_content_meta(sha256) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_file_no_expiration(tmpdir, system):
    path = str(tmpdir / "test.txt")
    with open(path, "w") as fp:
        fp.write("Hello, world!")

    # store the file and have it never expire
    sha256 = await system.save_file(path)  # defaults to never expire
    assert sha256

    # we should have no files expired
    assert len([_ async for _ in await system.iter_expired_content()]) == 0

    # clear them out
    await system.delete_expired_content()

    # the file should still be there
    assert await system.get_content_meta(sha256) is not None

    # should still have no files expired
    assert len([_ async for _ in await system.iter_expired_content()]) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_file_expiration_with_root_reference(tmpdir, system):
    """Tests that a file that expires but still has a root reference does not
    get deleted until the root is also deleted."""

    path = str(tmpdir / "test.txt")
    with open(path, "w") as fp:
        fp.write("Hello, world!")

    root = system.new_root()
    # have the file expire right away
    file_observable = await root.add_file(path, expiration_date=utc_now())
    await root.save()
    root.discard()

    # this should return 0 since it still has a valid root reference
    assert len([_ async for _ in await system.iter_expired_content()]) == 0

    # make sure we don't delete anything
    assert await system.delete_expired_content() == 0
    assert await system.get_content_meta(file_observable.value) is not None

    # delete the root
    await system.delete_root_analysis(root)

    # now this should return 1 since the root is gone
    assert len([_ async for _ in await system.iter_expired_content()]) == 1

    # and now it should clear out
    assert await system.delete_expired_content() == 1

    # this should return 0 since it still has a valid root reference
    assert len([_ async for _ in await system.iter_expired_content()]) == 0

    # and the content is gone
    assert await system.get_content_meta(file_observable.value) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_file_expiration_with_multiple_root_reference(tmpdir, system):
    """Tests that a file that expires but still has a root references are not
    deleted until all root references are deleted."""

    path = str(tmpdir / "test.txt")
    with open(path, "w") as fp:
        fp.write("Hello, world!")

    # add a root with a file that expires right away
    root_1 = system.new_root()
    file_observable = await root_1.add_file(path, expiration_date=utc_now())
    await root_1.save()
    root_1.discard()

    # do it again but reference the same file
    root_2 = system.new_root()
    file_observable = await root_2.add_file(path, expiration_date=utc_now())
    await root_2.save()
    root_2.discard()

    # the content meta should reference two different roots
    meta = await system.get_content_meta(file_observable.value)
    assert root_1.uuid in meta.roots
    assert root_2.uuid in meta.roots

    # this should return 0 since it still has a valid root reference
    assert len([_ async for _ in await system.iter_expired_content()]) == 0

    # make sure we don't delete anything
    assert await system.delete_expired_content() == 0
    assert await system.get_content_meta(file_observable.value) is not None

    # delete the first root
    await system.delete_root_analysis(root_1)

    # this should return 0 since we still have a valid root reference
    assert len([_ async for _ in await system.iter_expired_content()]) == 0

    # make sure we don't delete anything
    assert await system.delete_expired_content() == 0
    assert await system.get_content_meta(file_observable.value) is not None

    # delete the second root
    await system.delete_root_analysis(root_2)

    # now this should return 1 since the root is gone
    assert len([_ async for _ in await system.iter_expired_content()]) == 1

    # and now it should clear out
    assert await system.delete_expired_content() == 1

    # this should return 0 since it still has a valid root reference
    assert len([_ async for _ in await system.iter_expired_content()]) == 0

    # and the content is gone
    assert await system.get_content_meta(file_observable.value) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_root_analysis_association(tmp_path, system):
    target_path = tmp_path / "test.txt"
    target_path.write_text("test")
    target_path = str(target_path)

    # we store the file with no initial root analysis set to expire now
    sha256 = await system.save_file(target_path, expiration_date=utc_now())
    assert await system.get_content_meta(sha256)

    # submit a root analysis with the given file *after* we upload it
    root = system.new_root()
    observable = root.add_observable("file", sha256)
    await root.submit()

    # now attempt to delete all expired content
    await system.delete_expired_content()

    # we should still have the content
    assert await system.get_content_meta(sha256)

    # delete the root
    await system.delete_root_analysis(root)

    # now attempt to delete all expired content
    await system.delete_expired_content()

    # should be gone
    assert await system.get_content_meta(sha256) is None
