# vim: ts=4:sw=4:et:cc=120

import contextlib
import datetime
import io
import os.path
import shutil

from dataclasses import dataclass, field
from typing import Union, Optional, Iterator

from ace.analysis import RootAnalysis
from ace.system import ACESystemInterface, get_system, get_logger
from ace.system.analysis_tracking import get_root_analysis
from ace.system.constants import EVENT_STORAGE_NEW, EVENT_STORAGE_DELETED
from ace.system.events import fire_event
from ace.time import utc_now


@dataclass
class ContentMetadata:
    # the meta "name" of the content
    # can be anything including the name of the file
    # additional information can be stored in the custom property
    name: str
    # the sha256 (lowercase hex) of the content
    sha256: str = None
    # the total size of the content (in bytes)
    size: int = 0
    # free-form "location" of the content (can be None if not used)
    # for example, on systems that store data locally this can be the path to the file
    # or on systems that store the data externally this can be the reference key to the content
    location: str = None
    # when the content was created (defaults to now)
    insert_date: datetime.datetime = field(default_factory=utc_now)
    # when the content should be discarded (defaults to None which means never)
    expiration_date: Union[datetime.datetime, None] = None
    # dict for storing any required custom properties of the content
    custom: dict = field(default_factory=dict)
    # the list of RootAnalysis UUIDs that reference this content
    # an empty list indicates that nothing references it anymore
    # NOTE this list can reference non-existant root analysis objects
    # this can happen if the file is uploaded before the root is tracked
    roots: list = field(default_factory=list)


#
# how things are actually stored is abstracted away by this interface
# content is referenced by the sha256 of the data in lower case hex string format
#


class StorageInterface(ACESystemInterface):
    def store_content(self, content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
        """Stores the content with the given meta data and returns the key needed to lookup the content.

        Args:
            content: the content to store
            meta: metadata about the content

        Returns:
            the lookup key for the content (sha256 hash)
        """
        raise NotImplementedError()

    def get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        """Returns the requested stored content as a bytes object, or None if the content does not exist."""
        raise NotImplementedError()

    def get_content_stream(self, sha256: str) -> Union[io.IOBase, None]:
        """Returns the requested stored content as some kind of stream, or None if the content does not exist."""
        raise NotImplementedError()

    def get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        """Returns the meta data of the stored content, or None if the content does not exist."""
        raise NotImplementedError()

    def iter_expired_content(self) -> Iterator[ContentMetadata]:
        """Iterates over expired content metadata."""
        raise NotImplementedError()

    def delete_content(self, sha256: str) -> bool:
        """Deletes the given content. Returns True if content was actually deleted."""
        raise NotImplementedError()

    def track_content_root(self, sha256: str, uuid: str):
        """Associates stored content to a root analysis."""
        raise NotImplementedError()


def store_content(content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
    assert isinstance(content, bytes) or isinstance(content, str) or isinstance(content, io.IOBase)
    assert isinstance(meta, ContentMetadata)
    get_logger().debug(f"storing content {meta}")
    sha256 = get_system().storage.store_content(content, meta)
    fire_event(EVENT_STORAGE_NEW, sha256, meta)
    return sha256


def get_content_bytes(sha256: str) -> Union[bytes, None]:
    return get_system().storage.get_content_bytes(sha256)


def get_content_stream(sha256: str) -> Union[io.IOBase, None]:
    return get_system().storage.get_content_stream(sha256)


def get_content_meta(sha256: str) -> Union[ContentMetadata, None]:
    return get_system().storage.get_content_meta(sha256)


def iter_expired_content() -> Iterator[ContentMetadata]:
    """Returns an iterator for all the expired content."""
    return get_system().storage.iter_expired_content()


def delete_content(sha256: str) -> bool:
    get_logger().debug(f"deleting content {sha256}")
    result = get_system().storage.delete_content(sha256)
    if result:
        fire_event(EVENT_STORAGE_DELETED, sha256)

    return result


def track_content_root(sha256: str, root: Union[RootAnalysis, str]):
    assert isinstance(sha256, str)
    assert isinstance(root, RootAnalysis) or isinstance(root, str)

    if isinstance(root, RootAnalysis):
        root = root.uuid

    get_logger().debug(f"tracking content {sha256} to root {root}")
    get_system().storage.track_content_root(sha256, root)


#
# utility functions
#


def store_file(path: str, **kwargs) -> str:
    """Utility function that stores the contents of the given file and returns the sha256 hash."""
    assert isinstance(path, str)
    meta = ContentMetadata(path, **kwargs)
    with open(path, "rb") as fp:
        return store_content(fp, meta)


def get_file(sha256: str, path: Optional[str] = None) -> bool:
    """Utility function that pulls data out of storage into a local file. The
    original path is used unless a target path is specified."""
    assert isinstance(sha256, str)
    assert path is None or isinstance(path, str)

    meta = get_content_meta(sha256)
    if meta is None:
        return False

    if path is None:
        path = meta.name

    with open(path, "wb") as fp_out:
        with contextlib.closing(get_content_stream(sha256)) as fp_in:
            shutil.copyfileobj(fp_in, fp_out)

    return True


def has_valid_root_reference(meta: ContentMetadata) -> bool:
    """Returns True if the given meta has a valid (existing) RootAnalysis reference."""
    for root_uuid in meta.roots:
        if get_root_analysis(root_uuid) is not None:
            return True

    return False


def delete_expired_content() -> int:
    """Deletes all expired content and returns the number of items deleted."""
    get_logger().debug("deleting expired content")
    count = 0
    for meta in iter_expired_content():
        root_exists = False
        for root_uuid in meta.roots:
            if get_root_analysis(root_uuid) is not None:
                root_exists = True
                break

        if root_exists:
            continue

        if delete_content(meta.sha256):
            count += 1

    return count
