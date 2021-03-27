# vim: ts=4:sw=4:et:cc=120

import uuid

import pytest

from ace.analysis import RootAnalysis, Observable, Analysis, AnalysisModuleType
from ace.exceptions import UnknownRootAnalysisError

TEST_DETAILS = {"hello": "world"}
OBSERVABLE_VALUE = "observable value"
OBSERVABLE_VALUE_2 = "observable value 2"


def _compare_root(a, b):
    assert a is None or isinstance(a, RootAnalysis)
    assert b is None or isinstance(b, RootAnalysis)
    if a is None or b is None:
        return False

    return a.uuid == b.uuid


@pytest.mark.asyncio
@pytest.mark.integration
async def test_track_root_analysis(system):
    root = system.new_root()
    await system.track_root_analysis(root)
    # root should be tracked
    assert (await system.get_root_analysis(root.uuid)).uuid == root.uuid
    # should be OK to do twice
    await system.track_root_analysis(root)
    assert _compare_root(await system.get_root_analysis(root.uuid), root)
    # clear it out
    assert await system.delete_root_analysis(root.uuid)
    # make sure it's gone
    assert await system.get_root_analysis(root.uuid) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_root_analysis(system):
    root = system.new_root(desc="test 1")
    await system.track_root_analysis(root)
    assert await system.get_root_analysis(root.uuid) == root
    old_root = await system.get_root_analysis(root.uuid)
    current_version = root.version
    root.description = "test 2"
    assert await system.update_root_analysis(root)
    # version should have updated
    assert current_version != root.version
    # and description should have changed
    assert (await system.get_root_analysis(root.uuid)).description == "test 2"
    # don't change anything and it should still work
    current_version = root.version
    assert await system.update_root_analysis(root)
    # only the version changes
    assert current_version != root.version

    # now with the old copy try to set the description
    assert old_root.version != root.version
    old_root.description = "test 3"
    # this should fail since the version is out of date
    assert not await system.update_root_analysis(old_root)
    # the description should NOT have changed
    assert (await system.get_root_analysis(root.uuid)).description == "test 2"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_parallel_update_logic(system):
    root = system.new_root(desc="test 1")
    await system.track_root_analysis(root)
    assert await system.get_root_analysis(root.uuid) == root
    old_root = await system.get_root_analysis(root)

    # update the root
    updated = await system.get_root_analysis(root)
    updated.description = "test 2"
    assert await updated.save()

    # add an observable to the old root and try to save it
    observable = old_root.add_observable("test", "test")
    assert not await old_root.save()
    assert not (await system.get_root_analysis(root)).get_observable(observable)

    assert await old_root.update()
    # make sure we still have our change
    assert old_root.get_observable(observable)
    # now we should be able to save it
    assert await old_root.save()

    #
    # do it again but with information deeper in the analysis tree
    #

    root = await system.get_root_analysis(root)
    old_root = await system.get_root_analysis(root)

    root.get_observable(observable).add_tag("tag_1")
    assert await root.save()

    old_root.get_observable(observable).add_tag("tag_2")
    assert not await old_root.save()
    assert await old_root.update()
    assert await old_root.save()
    root = await system.get_root_analysis(root)
    # both of these tags should exist now
    assert root.get_observable(observable).has_tag("tag_1")
    assert root.get_observable(observable).has_tag("tag_2")

    #
    # test overlapping updates
    #

    root = await system.get_root_analysis(root)
    old_root = await system.get_root_analysis(root)

    observable = root.add_observable("test", "test_2").add_tag("tag_1")
    assert await root.save()

    old_root.add_observable("test", "test_2").add_tag("tag_2")
    assert not await old_root.save()
    await old_root.update()
    assert old_root.get_observable(observable).has_tag("tag_2")
    assert await old_root.save()

    # both of these tags should exist now
    root = await system.get_root_analysis(root)
    assert root.get_observable(observable).has_tag("tag_1")
    assert root.get_observable(observable).has_tag("tag_2")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_root_analysis_exists(system):
    root = system.new_root()
    assert not await system.root_analysis_exists(root)
    await system.track_root_analysis(root)
    assert await system.root_analysis_exists(root)
    await system.delete_root_analysis(root)
    assert not await system.root_analysis_exists(root)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_track_analysis_details(system):
    root = system.new_root()
    root.set_details(TEST_DETAILS)
    await system.track_root_analysis(root)
    # track the details of the root analysis
    await system.track_analysis_details(root, root.uuid, await root.get_details())
    # make sure it's there
    assert await system.get_analysis_details(root.uuid) == TEST_DETAILS

    # mock up an analysis
    _uuid = str(uuid.uuid4())
    details = TEST_DETAILS
    await system.track_analysis_details(root, _uuid, details)
    assert await system.get_analysis_details(_uuid) == details
    # clear it out
    assert await system.delete_analysis_details(_uuid)
    # make sure it's gone
    assert await system.get_analysis_details(_uuid) is None

    # clear out the root details
    assert await system.delete_analysis_details(root.uuid)
    # make sure it's gone
    assert await system.get_analysis_details(root.uuid) is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_analysis_details_exists(system):
    root = system.new_root()
    root._details = TEST_DETAILS
    assert not await system.analysis_details_exists(root.uuid)
    await system.track_root_analysis(root)
    await system.track_analysis_details(root, root.uuid, await root.get_details())
    assert await system.analysis_details_exists(root.uuid)
    assert await system.delete_root_analysis(root)
    assert not await system.analysis_details_exists(root.uuid)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_analysis_details_deleted_with_root(system):
    # any details associated to a root are deleted when the root is deleted
    await system.register_analysis_module_type(amt := AnalysisModuleType("test", ""))
    root = system.new_root(details=TEST_DETAILS)
    observable = root.add_observable("test", "test")
    observable.add_analysis(analysis := Analysis(root=root, type=amt, details=TEST_DETAILS))
    await root.save()

    # make sure the details are there
    assert await system.get_analysis_details(root.uuid) == TEST_DETAILS
    assert await system.get_analysis_details(analysis.uuid) == TEST_DETAILS

    # delete the root
    assert await system.delete_root_analysis(root.uuid)
    assert await system.get_root_analysis(root) is None
    # root details should be gone
    assert await system.get_analysis_details(root.uuid) is None
    # and analysis details should be gone
    assert await system.get_analysis_details(analysis.uuid) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_unknown_root(system):
    assert not await system.delete_root_analysis(str(uuid.uuid4()))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_track_details_to_unknown_root(system):
    # add analysis details to an unknown root analysis
    root = system.new_root()

    _uuid = str(uuid.uuid4())
    details = TEST_DETAILS
    with pytest.raises(UnknownRootAnalysisError):
        await system.track_analysis_details(root, _uuid, details)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_unknown_analysis_details(system):
    assert not await system.delete_analysis_details(str(uuid.uuid4()))
