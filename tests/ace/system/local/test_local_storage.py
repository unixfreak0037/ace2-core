import pytest

from ace.system.local.storage import LocalStorageInterface


@pytest.mark.unit
def test_missing_storage_root():
    with pytest.raises(RuntimeError):
        storage = LocalStorageInterface()
