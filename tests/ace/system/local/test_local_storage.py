import pytest

from ace.constants import ACE_STORAGE_ROOT
from ace.system.local.storage import LocalStorageInterface


@pytest.mark.unit
def test_storage_root_property(monkeypatch):
    # passed in on constructor
    assert LocalStorageInterface(storage_root="constructor").storage_root == "constructor"

    # passed in on env var
    monkeypatch.setenv(ACE_STORAGE_ROOT, "env")
    assert LocalStorageInterface().storage_root == "env"

    # missing entirely throws an exception
    monkeypatch.delenv(ACE_STORAGE_ROOT, raising=False)
    with pytest.raises(RuntimeError):
        LocalStorageInterface().storage_root
