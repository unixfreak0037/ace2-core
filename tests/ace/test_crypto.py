# vim: sw=4:ts=4:et:cc=120

import base64
import os
import os.path

from ace.crypto import (
    ENV_CRYPTO_ENCRYPTED_KEY,
    ENV_CRYPTO_ITERATIONS,
    ENV_CRYPTO_SALT,
    ENV_CRYPTO_SALT_SIZE,
    ENV_CRYPTO_VERIFICATION_KEY,
    EncryptionSettings,
    decrypt_chunk,
    decrypt_file,
    encrypt_chunk,
    encrypt_file,
    get_aes_key,
    initialize_encryption_settings,
    is_valid_password,
)

from ace.exceptions import InvalidPasswordError

import pytest


@pytest.fixture(scope="function")
def settings():
    return initialize_encryption_settings("test")


@pytest.mark.unit
def test_initialize_encryption_settings():
    with pytest.raises(AssertionError):
        initialize_encryption_settings("")

    settings = initialize_encryption_settings("test")
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


@pytest.mark.unit
def test_get_aes_key(settings):
    key = get_aes_key("test", settings)
    assert isinstance(key, bytes) and len(key) == 32

    with pytest.raises(InvalidPasswordError):
        get_aes_key("t3st", settings)


@pytest.mark.unit
def test_chunk_crypto(settings):
    chunk = b"1234567890"
    assert decrypt_chunk("test", encrypt_chunk("test", chunk, settings), settings) == chunk


@pytest.mark.unit
def test_file_crypto(settings, tmp_path):
    source_path = str(tmp_path / "plain_text.txt")
    target_path = str(tmp_path / "crypto.txt")

    with open(source_path, "wb") as fp:
        fp.write(b"1234567890")

    assert not os.path.exists(target_path)
    encrypt_file("test", source_path, target_path, settings)
    assert os.path.exists(target_path)

    os.unlink(source_path)
    assert not os.path.exists(source_path)
    decrypt_file("test", target_path, source_path, settings)
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
