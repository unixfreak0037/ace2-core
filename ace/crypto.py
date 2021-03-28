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
    except:
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


def initialize_encryption_settings(
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
            encryption_password = get_aes_key(old_password)

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
    settings.encrypted_key = encrypt_chunk(user_encryption_key, encryption_password)

    return settings


def get_aes_key(password: str, settings: EncryptionSettings) -> bytes:
    """Returns the 32 byte system encryption key."""
    assert isinstance(password, str)
    assert isinstance(settings, EncryptionSettings)
    return decrypt_chunk(get_decryption_key(password, settings), settings.encrypted_key)


def encrypt_chunk(
    password: typing.Union[str, bytes], chunk: bytes, settings: typing.Optional[EncryptionSettings] = None
):
    """Encrypts the given chunk of data and returns the encrypted chunk.
    If password is None then saq.ENCRYPTION_PASSWORD is used instead.
    password must be a byte string 32 bytes in length."""

    assert (isinstance(password, str) or (isinstance(password, bytes) and len(password) == 32)) and password
    assert isinstance(chunk, bytes) and chunk
    assert settings is None or isinstance(settings, EncryptionSettings)
    # if you pass the password as str then you need to also provide the settings
    # otherwise you just need to provide the aes 32 byte password
    assert (isinstance(password, bytes) and settings is None) or (
        isinstance(password, str) and isinstance(settings, EncryptionSettings)
    )

    if isinstance(password, str):
        password = get_aes_key(password, settings)

    iv = Crypto.Random.get_random_bytes(AES.block_size)
    encryptor = AES.new(password, AES.MODE_CBC, iv)

    original_size = len(chunk)

    if len(chunk) % 16 != 0:
        chunk += b" " * (16 - len(chunk) % 16)

    result = struct.pack("<Q", original_size) + iv + encryptor.encrypt(chunk)
    return result


def decrypt_chunk(
    password: typing.Union[str, bytes], chunk: bytes, settings: typing.Optional[EncryptionSettings] = None
):
    """Decrypts the given encrypted chunk with the given password and returns the decrypted chunk.
    If password is None then saq.ENCRYPTION_PASSWORD is used instead.
    password must be a byte string 32 bytes in length."""

    assert (isinstance(password, str) or (isinstance(password, bytes) and len(password) == 32)) and password
    assert isinstance(chunk, bytes) and chunk
    assert settings is None or isinstance(settings, EncryptionSettings)
    # if you pass the password as str then you need to also provide the settings
    # otherwise you just need to provide the aes 32 byte password
    assert (isinstance(password, bytes) and settings is None) or (
        isinstance(password, str) and isinstance(settings, EncryptionSettings)
    )

    if isinstance(password, str):
        password = get_aes_key(password, settings)

    _buffer = io.BytesIO(chunk)
    original_size = struct.unpack("<Q", _buffer.read(struct.calcsize("Q")))[0]
    iv = _buffer.read(16)
    chunk = _buffer.read()
    decryptor = AES.new(password, AES.MODE_CBC, iv)
    result = decryptor.decrypt(chunk)
    return result[:original_size]


# https://eli.thegreenplace.net/2010/06/25/aes-encryption-of-files-in-python-with-pycrypto
def encrypt_file(
    password: typing.Union[str, bytes],
    source_path: str,
    target_path: str,
    settings: typing.Optional[EncryptionSettings] = None,
):
    """Encrypts the given file at source_path with the given password and saves the results in target_path.
    If password is None then saq.ENCRYPTION_PASSWORD is used instead.
    password must be a byte string 32 bytes in length."""

    assert (isinstance(password, str) or (isinstance(password, bytes) and len(password) == 32)) and password
    assert settings is None or isinstance(settings, EncryptionSettings)
    # if you pass the password as str then you need to also provide the settings
    # otherwise you just need to provide the aes 32 byte password
    assert (isinstance(password, bytes) and settings is None) or (
        isinstance(password, str) and isinstance(settings, EncryptionSettings)
    )
    assert isinstance(source_path, str) and source_path
    assert isinstance(target_path, str) and target_path

    if isinstance(password, str):
        password = get_aes_key(password, settings)

    iv = Crypto.Random.get_random_bytes(AES.block_size)
    encryptor = AES.new(password, AES.MODE_CBC, iv)
    file_size = os.path.getsize(source_path)

    with open(source_path, "rb") as fp_in:
        with open(target_path, "wb") as fp_out:
            fp_out.write(struct.pack("<Q", file_size))
            fp_out.write(iv)

            while True:
                chunk = fp_in.read(CHUNK_SIZE)
                if len(chunk) == 0:
                    break
                elif len(chunk) % 16 != 0:
                    chunk += b" " * (16 - len(chunk) % 16)

                fp_out.write(encryptor.encrypt(chunk))


def decrypt_file(
    password: typing.Union[str, bytes],
    source_path: str,
    target_path: str,
    settings: typing.Optional[EncryptionSettings] = None,
):
    """Decrypts the given file at source_path with the given password and saves the results in target_path.
    If target_path is None then output will be sent to standard output.
    If password is None then saq.ENCRYPTION_PASSWORD is used instead.
    password must be a byte string 32 bytes in length."""

    assert (isinstance(password, str) or (isinstance(password, bytes) and len(password) == 32)) and password
    assert settings is None or isinstance(settings, EncryptionSettings)
    # if you pass the password as str then you need to also provide the settings
    # otherwise you just need to provide the aes 32 byte password
    assert (isinstance(password, bytes) and settings is None) or (
        isinstance(password, str) and isinstance(settings, EncryptionSettings)
    )
    assert isinstance(source_path, str) and source_path
    assert isinstance(target_path, str) and target_path

    if isinstance(password, str):
        password = get_aes_key(password, settings)

    with open(source_path, "rb") as fp_in:
        original_size = struct.unpack("<Q", fp_in.read(struct.calcsize("Q")))[0]
        iv = fp_in.read(16)
        decryptor = AES.new(password, AES.MODE_CBC, iv)

        with open(target_path, "wb") as fp_out:
            while True:
                chunk = fp_in.read(CHUNK_SIZE)
                if len(chunk) == 0:
                    break

                fp_out.write(decryptor.decrypt(chunk))

            fp_out.truncate(original_size)
