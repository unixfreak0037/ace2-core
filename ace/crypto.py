# vim: sw=4:ts=4:et:cc=120
#
# cryptography functions used by ACE
#

import base64
import dataclasses
import io
import logging
import os.path
import random
import socket
import struct
import typing

import Crypto.Random

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import PBKDF2

import aiofiles

CHUNK_SIZE = 64 * 1024

ENV_CRYPTO_VERIFICATION_KEY = "ACE_CRYPTO_VERIFICATION_KEY"
ENV_CRYPTO_SALT = "ACE_CRYPTO_SALT"
ENV_CRYPTO_SALT_SIZE = "ACE_CRYPTO_SALT_SIZE"
ENV_CRYPTO_ITERATIONS = "ACE_CRYPTO_ITERATIONS"
ENV_CRYPTO_ENCRYPTED_KEY = "ACE_CRYPTO_ENCRYPTED_KEY"


@dataclasses.dataclass
class EncryptionSettings:

    verification_key: typing.Optional[bytes] = None
    salt: typing.Optional[bytes] = None
    salt_size: typing.Optional[int] = None
    iterations: typing.Optional[int] = None
    encrypted_key: typing.Optional[bytes] = None
    aes_key: typing.Optional[bytes] = None

    def load_from_env(self):
        """Loads the encryption settings from environment variables."""

        #
        # encryption settings can be loaded from (base64 encoded) environment variables
        #

        if ENV_CRYPTO_VERIFICATION_KEY in os.environ:
            self.verification_key = base64.b64decode(os.environ[ENV_CRYPTO_VERIFICATION_KEY])
        if ENV_CRYPTO_SALT in os.environ:
            self.salt = base64.b64decode(os.environ[ENV_CRYPTO_SALT])
        if ENV_CRYPTO_SALT_SIZE in os.environ:
            self.salt_size = int(os.environ[ENV_CRYPTO_SALT_SIZE])
        if ENV_CRYPTO_ITERATIONS in os.environ:
            self.iterations = int(os.environ[ENV_CRYPTO_ITERATIONS])
        if ENV_CRYPTO_ENCRYPTED_KEY in os.environ:
            self.encrypted_key = base64.b64decode(os.environ[ENV_CRYPTO_ENCRYPTED_KEY])

    def load_aes_key(self, password: str):
        """Loads the AES key into the aes_key field, making it available for encryption/decryption."""
        self.aes_key = get_decryption_key(password, self)


def is_valid_password(password: str, settings: EncryptionSettings) -> bool:
    """Returns True if the given password is the valid encryption password, False otherwise."""

    assert isinstance(password, str)
    assert isinstance(settings, EncryptionSettings)

    try:
        get_decryption_key(password, settings)
        return True
    except Exception:
        return False


def get_decryption_key(password: str, settings: EncryptionSettings) -> bytes:
    """Returns the 32 byte key used to decrypt the encryption key.
    Raises InvalidPasswordError if the password is incorrect.
    Raises PasswordNotSetError if the password has not been set."""

    assert isinstance(password, str)
    assert isinstance(settings, EncryptionSettings)

    result = PBKDF2(password, settings.salt, 64, settings.iterations)
    if settings.verification_key != result[32:]:
        from ace.exceptions import InvalidPasswordError

        raise InvalidPasswordError()

    return result[:32]


async def initialize_encryption_settings(
    password: str,
    old_password: typing.Optional[str] = None,
    key: typing.Optional[bytes] = None,
    settings: typing.Optional[EncryptionSettings] = None,
) -> EncryptionSettings:
    """Sets the encryption password for the system. If a password has already been set, then
    old_password can be provided to change the password. Otherwise, the old password is
    over-written by the new password.
    If the key parameter is None then the PRIMARY AES KEY is random. Otherwise, the given key is used.
    The default of a random key is fine."""
    assert isinstance(password, str) and password
    assert old_password is None or isinstance(old_password, str)
    assert key is None or (isinstance(key, bytes) and len(key) == 32)
    assert settings is None or isinstance(settings, EncryptionSettings)

    if settings is None:
        settings = EncryptionSettings()

    encryption_password = None

    # has the encryption password been set yet?
    if settings.encrypted_key:
        # did we provide a password for it?
        if old_password is not None:
            # get the existing encryption password
            encryption_password = await get_aes_key(old_password)

    if encryption_password is None:
        # otherwise we just make a new one
        if key is None:
            encryption_password = Crypto.Random.get_random_bytes(32)
        else:
            encryption_password = key

    # now we compute the key to use to encrypt the encryption key using the user-supplied password
    if settings.salt_size is None:
        settings.salt_size = 32

    if settings.salt is None:
        settings.salt = Crypto.Random.get_random_bytes(settings.salt_size)

    if settings.iterations is None:
        settings.iterations = 8192

    result = PBKDF2(password, settings.salt, 64, settings.iterations)
    user_encryption_key = result[:32]  # the first 32 bytes is the user encryption key
    settings.verification_key = result[32:]  # and the second 32 bytes is used for password verification
    settings.encrypted_key = await encrypt_chunk(user_encryption_key, encryption_password)

    return settings


async def get_aes_key(password: str, settings: EncryptionSettings) -> bytes:
    """Returns the 32 byte system encryption key."""
    assert isinstance(password, str)
    assert isinstance(settings, EncryptionSettings)
    return await decrypt_chunk(get_decryption_key(password, settings), settings.encrypted_key)


#
# file format is as follows
# IV(16)
# CHUNK,CHUNK,...
#
# where IV is the 16 byte IV used
# and CHUNK is defined as follows
# original_size (8 byte int) (little endian)
# padded_size (8 byte int) (little endian)
# byte data (of padded_size bytes)
#
# CHUNK_SIZE defines how big the chunks are (max)
#

#
# credit where credit is due
# https://eli.thegreenplace.net/2010/06/25/aes-encryption-of-files-in-python-with-pycrypto
#


async def iter_encrypt_stream(
    password: typing.Union[str, bytes],
    source: [io.BytesIO, aiofiles.threadpool.binary.AsyncBufferedIOBase, typing.AsyncGenerator[bytes, None]],
    settings: typing.Optional[EncryptionSettings] = None,
) -> typing.AsyncGenerator[bytes, None]:
    """Encrypts the data on the source stream with the given encryption settings. If the password parameter
    is a string, it is used as the password to decrypt the actual AES 32 byte password that is used to perform
    the encryption. The source can be either an io.BytesIO object, or an AsyncBufferedIOBase from aiofiles.

    Each encrypted chunk of data is yielded as a result. Use in a for async iterator like this:

    async for chunk in iter_encrypt_stream(my_password, my_source, settings):
        do_something_with(chunk)
    """

    assert (isinstance(password, str) or (isinstance(password, bytes) and len(password) == 32)) and password
    assert settings is None or isinstance(settings, EncryptionSettings)
    # if you pass the password as str then you need to also provide the settings
    # otherwise you just need to provide the aes 32 byte password
    assert (isinstance(password, bytes) and settings is None) or (
        isinstance(password, str) and isinstance(settings, EncryptionSettings)
    )
    assert (
        isinstance(source, io.BytesIO)
        or isinstance(source, aiofiles.threadpool.binary.AsyncBufferedIOBase)
        or isinstance(source, typing.AsyncGenerator)
    )

    # used to buffer data from an async generator
    _async_buffer = b""

    # utility function to read n bytes regardless of type of source
    async def _read(n: int) -> bytes:
        nonlocal _async_buffer

        if isinstance(source, io.BytesIO):
            return source.read(n)
        elif isinstance(source, aiofiles.threadpool.binary.AsyncBufferedIOBase):
            return await source.read(n)
        else:
            # we break out of this loop once we have enough data
            while len(_async_buffer) < n:
                # get more data from the async generator
                try:
                    chunk = await source.__anext__()
                except StopAsyncIteration:
                    chunk = None

                if not chunk:
                    # if we didn't get anything then we just return what we have left
                    # (which may be nothing)
                    break

                # otherwise append it to the end of our buffer
                _async_buffer += chunk

            # we may have more bytes in our buffer then we asked for
            result = _async_buffer[:n]
            _async_buffer = _async_buffer[n:]
            return result

    if isinstance(password, str):
        password = await get_aes_key(password, settings)

    iv = Crypto.Random.get_random_bytes(AES.block_size)
    encryptor = AES.new(password, AES.MODE_CBC, iv)
    yield iv

    while True:
        chunk = await _read(CHUNK_SIZE)
        chunk_size = len(chunk)
        if chunk_size == 0:
            break
        elif chunk_size % 16 != 0:
            chunk += b" " * (16 - chunk_size % 16)

        # write the original size first so the decryption process knows how much to truncate
        yield struct.pack("<Q", chunk_size)
        # write the actual (padded) size so the decryptor knows how many bytes to actually read next
        yield struct.pack("<Q", len(chunk))
        yield encryptor.encrypt(chunk)


async def iter_decrypt_stream(
    password: typing.Union[str, bytes],
    source: [io.BytesIO, aiofiles.threadpool.binary.AsyncBufferedIOBase, typing.AsyncGenerator[bytes, None]],
    settings: typing.Optional[EncryptionSettings] = None,
) -> typing.AsyncGenerator[bytes, None]:
    """Decrypts the data on the source stream with the given encryption settings. If the password parameter
    is a string, it is used as the password to decrypt the actual AES 32 byte password that is used to perform
    the encryption. The source can be either an io.BytesIO object, or an AsyncBufferedIOBase from aiofiles.

    Each decrypted chunk of data is yielded as a result. Use in a for async iterator like this:

    async for chunk in iter_decrypt_stream(my_password, my_source, settings):
        do_something_with(chunk)
    """

    assert (isinstance(password, str) or (isinstance(password, bytes) and len(password) == 32)) and password
    assert settings is None or isinstance(settings, EncryptionSettings)
    # if you pass the password as str then you need to also provide the settings
    # otherwise you just need to provide the aes 32 byte password
    assert (isinstance(password, bytes) and settings is None) or (
        isinstance(password, str) and isinstance(settings, EncryptionSettings)
    )
    assert (
        isinstance(source, io.BytesIO)
        or isinstance(source, aiofiles.threadpool.binary.AsyncBufferedIOBase)
        or isinstance(source, typing.AsyncGenerator)
    )

    # XXX copy pasta

    # used to buffer data from an async generator
    _async_buffer = b""

    # utility function to read n bytes regardless of type of source
    async def _read(n: int) -> bytes:
        nonlocal _async_buffer

        if isinstance(source, io.BytesIO):
            return source.read(n)
        elif isinstance(source, aiofiles.threadpool.binary.AsyncBufferedIOBase):
            return await source.read(n)
        else:
            # we break out of this loop once we have enough data
            while len(_async_buffer) < n:
                # get more data from the async generator
                try:
                    chunk = await source.__anext__()
                except StopAsyncIteration:
                    chunk = None

                if not chunk:
                    # if we didn't get anything then we just return what we have left
                    # (which may be nothing)
                    break

                # otherwise append it to the end of our buffer
                _async_buffer += chunk

            # we may have more bytes in our buffer then we asked for
            result = _async_buffer[:n]
            _async_buffer = _async_buffer[n:]
            return result

    if isinstance(password, str):
        password = await get_aes_key(password, settings)

    # the IV is the first 16 bytes
    iv = await _read(16)
    decryptor = AES.new(password, AES.MODE_CBC, iv)

    while True:
        # for each "chunk" the size of the chunk is stored first
        _buffer = await _read(struct.calcsize("Q"))
        if not _buffer:
            break

        original_chunk_size = struct.unpack("<Q", _buffer)[0]
        _buffer = await _read(struct.calcsize("Q"))
        if not _buffer:
            break

        padded_chunk_size = struct.unpack("<Q", _buffer)[0]
        if padded_chunk_size > CHUNK_SIZE + 16:
            raise ValueError("decryption error - invalid chunk size: {padded_chunk_size} (file corrupted?)")

        chunk = await _read(padded_chunk_size)
        if not chunk:
            break

        decrypted_chunk = decryptor.decrypt(chunk)

        if original_chunk_size < padded_chunk_size:
            decrypted_chunk = decrypted_chunk[:original_chunk_size]

        yield decrypted_chunk


async def encrypt_stream(
    password: typing.Union[str, bytes],
    source: [io.BytesIO, aiofiles.threadpool.binary.AsyncBufferedIOBase],
    target: [io.BytesIO, aiofiles.threadpool.binary.AsyncBufferedIOBase],
    settings: typing.Optional[EncryptionSettings] = None,
):
    assert (isinstance(password, str) or (isinstance(password, bytes) and len(password) == 32)) and password
    assert settings is None or isinstance(settings, EncryptionSettings)
    # if you pass the password as str then you need to also provide the settings
    # otherwise you just need to provide the aes 32 byte password
    assert (isinstance(password, bytes) and settings is None) or (
        isinstance(password, str) and isinstance(settings, EncryptionSettings)
    )
    assert isinstance(source, io.BytesIO) or isinstance(source, aiofiles.threadpool.binary.AsyncBufferedIOBase)
    assert isinstance(target, io.BytesIO) or isinstance(target, aiofiles.threadpool.binary.AsyncBufferedIOBase)

    async for chunk in iter_encrypt_stream(password, source, settings):
        if isinstance(target, io.BytesIO):
            target.write(chunk)
        else:
            await target.write(chunk)


async def decrypt_stream(
    password: typing.Union[str, bytes],
    source: [io.BytesIO, aiofiles.threadpool.binary.AsyncBufferedIOBase, typing.AsyncGenerator[bytes, None]],
    target: [io.BytesIO, aiofiles.threadpool.binary.AsyncBufferedIOBase],
    settings: typing.Optional[EncryptionSettings] = None,
):
    assert (isinstance(password, str) or (isinstance(password, bytes) and len(password) == 32)) and password
    assert settings is None or isinstance(settings, EncryptionSettings)
    # if you pass the password as str then you need to also provide the settings
    # otherwise you just need to provide the aes 32 byte password
    assert (isinstance(password, bytes) and settings is None) or (
        isinstance(password, str) and isinstance(settings, EncryptionSettings)
    )
    assert (
        isinstance(source, io.BytesIO)
        or isinstance(source, aiofiles.threadpool.binary.AsyncBufferedIOBase)
        or isinstance(source, typing.AsyncGenerator)
    )
    assert isinstance(target, io.BytesIO) or isinstance(target, aiofiles.threadpool.binary.AsyncBufferedIOBase)

    async for chunk in iter_decrypt_stream(password, source, settings):
        if isinstance(target, io.BytesIO):
            target.write(chunk)
        else:
            await target.write(chunk)


async def encrypt_file(
    password: typing.Union[str, bytes],
    source_path: str,
    target_path: str,
    settings: typing.Optional[EncryptionSettings] = None,
):
    """Encrypts the given file at source_path with the given password and saves the results in target_path.
    If password is None then saq.ENCRYPTION_PASSWORD is used instead.
    password must be a byte string 32 bytes in length."""
    assert isinstance(source_path, str) and source_path
    assert isinstance(target_path, str) and target_path

    async with aiofiles.open(source_path, "rb") as fp_in:
        async with aiofiles.open(target_path, "wb") as fp_out:
            await encrypt_stream(password, fp_in, fp_out, settings)


async def decrypt_file(
    password: typing.Union[str, bytes],
    source_path: str,
    target_path: str,
    settings: typing.Optional[EncryptionSettings] = None,
):
    """Decrypts the given file at source_path with the given password and saves the results in target_path.
    If target_path is None then output will be sent to standard output.
    If password is None then saq.ENCRYPTION_PASSWORD is used instead.
    password must be a byte string 32 bytes in length."""
    assert isinstance(source_path, str) and source_path
    assert isinstance(target_path, str) and target_path

    async with aiofiles.open(source_path, "rb") as fp_in:
        async with aiofiles.open(target_path, "wb") as fp_out:
            await decrypt_stream(password, fp_in, fp_out, settings)


async def encrypt_chunk(
    password: typing.Union[str, bytes], chunk: bytes, settings: typing.Optional[EncryptionSettings] = None
):
    """Encrypts the given chunk of data and returns the encrypted chunk.
    If password is None then saq.ENCRYPTION_PASSWORD is used instead.
    password must be a byte string 32 bytes in length."""
    assert isinstance(chunk, bytes) and chunk

    input_buffer = io.BytesIO(chunk)
    output_buffer = io.BytesIO()
    await encrypt_stream(password, input_buffer, output_buffer, settings)
    return output_buffer.getvalue()


async def decrypt_chunk(
    password: typing.Union[str, bytes], chunk: bytes, settings: typing.Optional[EncryptionSettings] = None
):
    """Decrypts the given encrypted chunk with the given password and returns the decrypted chunk.
    If password is None then saq.ENCRYPTION_PASSWORD is used instead.
    password must be a byte string 32 bytes in length."""

    assert isinstance(chunk, bytes) and chunk

    input_buffer = io.BytesIO(chunk)
    output_buffer = io.BytesIO()
    await decrypt_stream(password, input_buffer, output_buffer, settings)
    return output_buffer.getvalue()
