# vim: ts=4:sw=4:et:cc=120

import uuid

import pytest

from ace.analysis import RootAnalysis, Observable, Analysis, AnalysisModuleType
from ace.system import get_system
from ace.system.analysis_module import register_analysis_module_type
from ace.system.analysis_tracking import (
    analysis_details_exists,
    delete_analysis_details,
    delete_root_analysis,
    get_analysis_details,
    get_analysis_details,
    get_root_analysis,
    root_analysis_exists,
    track_analysis_details,
    track_root_analysis,
    update_root_analysis,
    UnknownRootAnalysisError,
)

TEST_DETAILS = {"hello": "world"}
OBSERVABLE_VALUE = "observable value"
OBSERVABLE_VALUE_2 = "observable value 2"


@pytest.mark.integration
def test_track_root_analysis():
    root = RootAnalysis()
    track_root_analysis(root)
    # root should be tracked
    assert get_root_analysis(root.uuid) == root
    # should be OK to do twice
    track_root_analysis(root)
    assert get_root_analysis(root.uuid) == root
    # clear it out
    assert delete_root_analysis(root.uuid)
    # make sure it's gone
    assert get_root_analysis(root.uuid) is None


@pytest.mark.integration
def test_update_root_analysis():
    root = RootAnalysis(desc="test 1")
    track_root_analysis(root)
    assert get_root_analysis(root.uuid) == root
    old_root = get_root_analysis(root.uuid)
    current_version = root.version
    root.description = "test 2"
    assert update_root_analysis(root)
    # version should have updated
    assert current_version != root.version
    # and description should have changed
    assert get_root_analysis(root.uuid).description == "test 2"
    # don't change anything and it should still work
    current_version = root.version
    assert update_root_analysis(root)
    # only the version changes
    assert current_version != root.version

    # now with the old copy try to set the description
    assert old_root.version != root.version
    old_root.description = "test 3"
    # this should fail since the version is out of date
    assert not update_root_analysis(old_root)
    # the description should NOT have changed
    assert get_root_analysis(root.uuid).description == "test 2"


@pytest.mark.integration
def test_parallel_update_logic():
    root = RootAnalysis(desc="test 1")
    track_root_analysis(root)
    assert get_root_analysis(root.uuid) == root
    old_root = get_root_analysis(root)

    # update the root
    updated = get_root_analysis(root)
    updated.description = "test 2"
    assert updated.save()

    # add an observable to the old root and try to save it
    observable = old_root.add_observable("test", "test")
    assert not old_root.save()
    assert not get_root_analysis(root).get_observable(observable)

    assert old_root.update()
    # make sure we still have our change
    assert old_root.get_observable(observable)
    # now we should be able to save it
    assert old_root.save()

    #
    # do it again but with information deeper in the analysis tree
    #

    root = get_root_analysis(root)
    old_root = get_root_analysis(root)

    root.get_observable(observable).add_tag("tag_1")
    assert root.save()

    old_root.get_observable(observable).add_tag("tag_2")
    assert not old_root.save()
    assert old_root.update()
    assert old_root.save()
    root = get_root_analysis(root)
    # both of these tags should exist now
    assert root.get_observable(observable).has_tag("tag_1")
    assert root.get_observable(observable).has_tag("tag_2")

    #
    # test overlapping updates
    #

    root = get_root_analysis(root)
    old_root = get_root_analysis(root)

    observable = root.add_observable("test", "test_2").add_tag("tag_1")
    assert root.save()

    old_root.add_observable("test", "test_2").add_tag("tag_2")
    assert not old_root.save()
    old_root.update()
    assert old_root.get_observable(observable).has_tag("tag_2")
    assert old_root.save()

    # both of these tags should exist now
    root = get_root_analysis(root)
    assert root.get_observable(observable).has_tag("tag_1")
    assert root.get_observable(observable).has_tag("tag_2")


@pytest.mark.unit
def test_root_analysis_exists():
    root = RootAnalysis()
    assert not root_analysis_exists(root)
    track_root_analysis(root)
    assert root_analysis_exists(root)
    delete_root_analysis(root)
    assert not root_analysis_exists(root)


@pytest.mark.integration
def test_track_analysis_details():
    root = RootAnalysis()
    root.details = TEST_DETAILS
    track_root_analysis(root)
    # track the details of the root analysis
    track_analysis_details(root, root.uuid, root.details)
    # make sure it's there
    assert get_analysis_details(root.uuid) == TEST_DETAILS

    # mock up an analysis
    _uuid = str(uuid.uuid4())
    details = TEST_DETAILS
    track_analysis_details(root, _uuid, details)
    assert get_analysis_details(_uuid) == details
    # clear it out
    assert delete_analysis_details(_uuid)
    # make sure it's gone
    assert get_analysis_details(_uuid) is None

    # clear out the root details
    assert delete_analysis_details(root.uuid)
    # make sure it's gone
    assert get_analysis_details(root.uuid) is None


@pytest.mark.unit
def test_analysis_details_exists():
    root = RootAnalysis()
    root.details = TEST_DETAILS
    assert not analysis_details_exists(root.uuid)
    track_root_analysis(root)
    track_analysis_details(root, root.uuid, root.details)
    assert analysis_details_exists(root.uuid)
    delete_root_analysis(root)
    assert not analysis_details_exists(root.uuid)


@pytest.mark.integration
def test_analysis_details_deleted_with_root():
    # any details associated to a root are deleted when the root is deleted
    register_analysis_module_type(amt := AnalysisModuleType("test", ""))
    root = RootAnalysis(details=TEST_DETAILS)
    observable = root.add_observable("test", "test")
    observable.add_analysis(analysis := Analysis(root=root, type=amt, details=TEST_DETAILS))
    root.save()

    # make sure the details are there
    assert get_analysis_details(root.uuid) == TEST_DETAILS
    assert get_analysis_details(analysis.uuid) == TEST_DETAILS

    # delete the root
    assert delete_root_analysis(root.uuid)
    assert get_root_analysis(root) is None
    # root details should be gone
    assert get_analysis_details(root.uuid) is None
    # and analysis details should be gone
    assert get_analysis_details(analysis.uuid) is None


@pytest.mark.integration
def test_delete_unknown_root():
    assert not delete_root_analysis(str(uuid.uuid4()))


@pytest.mark.integration
def test_track_details_to_unknown_root():
    # add analysis details to an unknown root analysis
    root = RootAnalysis()

    _uuid = str(uuid.uuid4())
    details = TEST_DETAILS
    with pytest.raises(UnknownRootAnalysisError):
        track_analysis_details(root, _uuid, details)


@pytest.mark.integration
def test_delete_unknown_analysis_details():
    assert not delete_analysis_details(str(uuid.uuid4()))
