# vim: sw=4:ts=4:et:cc=120

import base64
import io
import os
import os.path

import aiofiles

from ace.crypto import (
    ENV_CRYPTO_ENCRYPTED_KEY,
    ENV_CRYPTO_ITERATIONS,
    ENV_CRYPTO_SALT,
    ENV_CRYPTO_SALT_SIZE,
    ENV_CRYPTO_VERIFICATION_KEY,
    EncryptionSettings,
    decrypt_chunk,
    decrypt_file,
    decrypt_stream,
    encrypt_chunk,
    encrypt_file,
    encrypt_stream,
    get_aes_key,
    initialize_encryption_settings,
    is_valid_password,
    iter_decrypt_stream,
    iter_encrypt_stream,
)

from ace.exceptions import InvalidPasswordError

import pytest


@pytest.fixture(scope="function")
async def settings():
    return await initialize_encryption_settings("test")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_initialize_encryption_settings():
    with pytest.raises(AssertionError):
        await initialize_encryption_settings("")

    settings = await initialize_encryption_settings("test")
    assert settings.salt_size == 32
    assert settings.iterations == 8192
    assert isinstance(settings.encrypted_key, bytes)
    assert isinstance(settings.salt, bytes) and len(settings.salt) == settings.salt_size
    assert isinstance(settings.verification_key, bytes) and len(settings.verification_key) == 32


@pytest.mark.unit
def test_is_valid_password(settings):
    assert is_valid_password("test", settings)
    assert not is_valid_password("t3st", settings)


@pytest.mark.unit
def test_load_aes_key(settings):
    settings.load_aes_key("test")
    assert isinstance(settings.aes_key, bytes) and len(settings.aes_key) == 32


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_aes_key(settings):
    key = await get_aes_key("test", settings)
    assert isinstance(key, bytes) and len(key) == 32

    with pytest.raises(InvalidPasswordError):
        await get_aes_key("t3st", settings)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_chunk_crypto(settings):
    chunk = b"1234567890"
    assert await decrypt_chunk("test", await encrypt_chunk("test", chunk, settings), settings) == chunk
    assert chunk not in await encrypt_chunk("test", chunk, settings)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_file_crypto(settings, tmp_path):
    source_path = str(tmp_path / "plain_text.txt")
    target_path = str(tmp_path / "crypto.txt")

    with open(source_path, "wb") as fp:
        fp.write(b"1234567890")

    assert not os.path.exists(target_path)
    await encrypt_file("test", source_path, target_path, settings)
    assert os.path.exists(target_path)

    os.unlink(source_path)
    assert not os.path.exists(source_path)
    await decrypt_file("test", target_path, source_path, settings)
    with open(source_path, "rb") as fp:
        assert fp.read() == b"1234567890"


@pytest.mark.unit
def test_load_from_env(settings, monkeypatch):
    monkeypatch.setitem(os.environ, ENV_CRYPTO_VERIFICATION_KEY, base64.b64encode(settings.verification_key).decode())
    monkeypatch.setitem(os.environ, ENV_CRYPTO_SALT, base64.b64encode(settings.salt).decode())
    monkeypatch.setitem(os.environ, ENV_CRYPTO_SALT_SIZE, str(settings.salt_size))
    monkeypatch.setitem(os.environ, ENV_CRYPTO_ITERATIONS, str(settings.iterations))
    monkeypatch.setitem(os.environ, ENV_CRYPTO_ENCRYPTED_KEY, base64.b64encode(settings.encrypted_key).decode())

    new_settings = EncryptionSettings()
    new_settings.load_from_env()

    assert new_settings.verification_key == settings.verification_key
    assert new_settings.salt == settings.salt
    assert new_settings.salt_size == settings.salt_size
    assert new_settings.iterations == settings.iterations
    assert new_settings.encrypted_key == settings.encrypted_key


@pytest.mark.asyncio
@pytest.mark.unit
async def test_stream_crypto(settings):
    source = io.BytesIO(b"test")
    encrypted_target = io.BytesIO()
    await encrypt_stream("test", source, encrypted_target, settings)
    assert source.getvalue() != encrypted_target.getvalue()
    encrypted_target = io.BytesIO(encrypted_target.getvalue())
    decrypted_target = io.BytesIO()
    await decrypt_stream("test", encrypted_target, decrypted_target, settings)
    assert source.getvalue() == decrypted_target.getvalue()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_iter_stream_crypto_BytesIO(settings):
    source = io.BytesIO(b"test")
    encrypted_target = io.BytesIO()
    async for _buffer in iter_encrypt_stream("test", source, settings):
        encrypted_target.write(_buffer)

    assert source.getvalue() != encrypted_target.getvalue()
    encrypted_target = io.BytesIO(encrypted_target.getvalue())
    decrypted_target = io.BytesIO()
    async for _buffer in iter_decrypt_stream("test", encrypted_target, settings):
        decrypted_target.write(_buffer)

    assert source.getvalue() == decrypted_target.getvalue()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_iter_stream_crypto_AsyncBufferedReader(tmp_path, settings):
    target_file = str(tmp_path / "text.txt")
    with open(target_file, "w") as fp:
        fp.write("test")

    async with aiofiles.open(target_file, "rb") as source:
        encrypted_target = io.BytesIO()
        async for _buffer in iter_encrypt_stream("test", source, settings):
            encrypted_target.write(_buffer)

    assert encrypted_target.getvalue() != b"test"

    encrypted_target = io.BytesIO(encrypted_target.getvalue())
    decrypted_target = io.BytesIO()
    async for _buffer in iter_decrypt_stream("test", encrypted_target, settings):
        decrypted_target.write(_buffer)

    assert decrypted_target.getvalue() == b"test"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_iter_stream_crypto_AsyncGenerator(tmp_path, settings):
    target_file = str(tmp_path / "text.txt")
    with open(target_file, "w") as fp:
        fp.write("test")

    async def _reader(target):
        while True:
            chunk = target.read(io.DEFAULT_BUFFER_SIZE)
            if not chunk:
                break

            yield chunk

    with open(target_file, "rb") as source:
        encrypted_target = io.BytesIO()
        async for _buffer in iter_encrypt_stream("test", _reader(source), settings):
            encrypted_target.write(_buffer)

    assert encrypted_target.getvalue() != b"test"

    encrypted_target = io.BytesIO(encrypted_target.getvalue())
    decrypted_target = io.BytesIO()
    async for _buffer in iter_decrypt_stream("test", _reader(encrypted_target), settings):
        decrypted_target.write(_buffer)

    assert decrypted_target.getvalue() == b"test"
