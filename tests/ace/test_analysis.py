# vim: sw=4:ts=4:et

import copy
import datetime
import json
import os.path

from ace.analysis import (
    RootAnalysis,
    Analysis,
    AnalysisModuleType,
    DetectionPoint,
    DetectableObject,
    TaggableObject,
    Observable,
    recurse_down,
    recurse_tree,
    search_down,
)
from ace.system.analysis_module import register_analysis_module_type
from ace.system.analysis_request import AnalysisRequest
from ace.system.exceptions import UnknownObservableError
from ace.constants import F_TEST
from ace.system.analysis_tracking import (
    get_analysis_details,
    get_root_analysis,
)

import pytest

#
# Detection Points
#


@pytest.mark.unit
def test_detection_point_serialization():
    dp = DetectionPoint("description", "")
    dp == DetectionPoint.from_dict(dp.to_dict())
    dp == DetectionPoint.from_json(dp.to_json())


@pytest.mark.unit
def test_detection_point_eq():
    assert DetectionPoint("description", "") == DetectionPoint("description", "")
    assert DetectionPoint("description", "") != DetectionPoint("other", "")
    assert DetectionPoint("description", "") != DetectionPoint("description", "Hey.")
    assert DetectionPoint("description", "") != object()


@pytest.mark.unit
def test_detectable_object_serialization():
    target = DetectableObject()
    target.add_detection_point("test")

    target == DetectableObject.from_dict(target.to_dict())
    target == DetectableObject.from_json(target.to_json())


@pytest.mark.unit
def test_detectable_object_properties():
    target = DetectableObject()
    target.detections = [DetectionPoint("test")]
    assert target.detections == [DetectionPoint("test")]

    # adding the same detection point doesn't add another one
    target.add_detection_point("test")
    assert target.detections == [DetectionPoint("test")]


@pytest.mark.unit
def test_detectable_object():
    target = DetectableObject()
    assert not target.has_detection_points()
    assert not target.detections

    target.add_detection_point("Something was detected.", "These here are details.")
    assert target.has_detection_points()
    assert target.detections

    target.clear_detection_points()
    assert not target.has_detection_points()
    assert not target.detections


@pytest.mark.unit
def test_apply_merge_detetion_points():
    root = RootAnalysis()
    observable = root.add_observable("test", "test")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("test", "test")
    target_observable.add_detection_point("test")

    assert not observable.has_detection_points()
    observable.apply_merge(target_observable)
    assert observable.has_detection_points


@pytest.mark.unit
def test_apply_diff_merge_detetion_points():
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")

    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    modified_observable.add_detection_point("test")

    target_root = copy.deepcopy(original_root)
    target_observable = target_root.get_observable(original_observable)

    assert not target_observable.has_detection_points()
    target_observable.apply_diff_merge(original_observable, modified_observable)
    assert target_observable.has_detection_points

    # exists before but not after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")

    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)

    target_root = copy.deepcopy(original_root)
    target_observable = target_root.get_observable(original_observable)

    original_observable.add_detection_point("test")

    assert not target_observable.has_detection_points()
    target_observable.apply_diff_merge(original_observable, modified_observable)
    assert not target_observable.has_detection_points()


#
# TaggableObject
#


@pytest.mark.unit
def test_taggable_object_serialization():
    taggable_object = TaggableObject()
    taggable_object.add_tag("test")
    assert taggable_object == TaggableObject.from_dict(taggable_object.to_dict())
    assert taggable_object == TaggableObject.from_json(taggable_object.to_json())


@pytest.mark.unit
def test_taggable_object():
    target = TaggableObject()
    assert not target.tags
    assert target.add_tag("tag") is target
    assert target.tags
    assert target.has_tag("tag")
    assert not target.has_tag("t@g")
    comp_target = TaggableObject()
    comp_target.add_tag("tag")
    assert target == comp_target
    assert target != object()
    comp_target = TaggableObject()
    comp_target.add_tag("t@g")
    assert target != comp_target
    target.clear_tags()
    assert not target.tags


@pytest.mark.unit
def test_apply_merge_tags():
    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    target_observable.add_tag("test")

    assert not observable.tags
    observable.apply_merge(target_observable)
    assert observable.tags
    assert observable.tags[0] == "test"


@pytest.mark.unit
def test_apply_diff_merge_tags():
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    modified_observable.add_tag("test")

    target_root = copy.deepcopy(original_root)
    target_observable = target_root.add_observable("test", "test")

    assert not target_observable.tags
    target_observable.apply_diff_merge(original_observable, modified_observable)
    assert target_observable.tags
    assert target_observable.tags[0] == "test"

    # exists before but not after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)

    target_root = copy.deepcopy(original_root)
    target_observable = target_root.add_observable("test", "test")

    original_observable.add_tag("test")

    assert not target_observable.tags
    target_observable.apply_diff_merge(original_observable, modified_observable)
    assert not target_observable.tags


#
# AnalysisModuleType
#


@pytest.mark.unit
def test_analysis_module_type_serialization():
    amt = AnalysisModuleType(
        name="test",
        description="test",
        observable_types=["test1", "test2"],
        directives=["test1", "test2"],
        dependencies=["test1", "test2"],
        tags=["test1", "test2"],
        modes=["test1", "test2"],
        cache_ttl=60,
        additional_cache_keys=["test1", "test2"],
        types=["test1", "test2"],
    )

    assert amt == AnalysisModuleType.from_dict(amt.to_dict())
    assert amt == AnalysisModuleType.from_json(amt.to_json())


#
# Analysis
#

TEST_DETAILS = {"hello": "world"}


@pytest.mark.unit
def test_root_analysis_serialization():
    root = RootAnalysis(
        tool="test",
        tool_instance="test",
        alert_type="test",
        desc="test",
        event_time=datetime.datetime.now(),
        name="test",
        analysis_mode="test",
        queue="test",
        instructions="test",
    )

    amt = AnalysisModuleType("test", "")
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt, details={"test": "test"})

    new_root = RootAnalysis.from_dict(root.to_dict())
    assert root == new_root
    assert root.tool == new_root.tool
    assert root.tool_instance == new_root.tool
    assert root.alert_type == new_root.alert_type
    assert root.description == new_root.description
    assert root.event_time == new_root.event_time
    assert root.name == new_root.name
    assert root.analysis_mode == new_root.analysis_mode
    assert root.queue == new_root.queue
    assert root.instructions == new_root.instructions

    # the observable property for the root should always be None
    assert root.observable is None
    assert len(root.observables) == 1

    new_root = RootAnalysis.from_json(root.to_json())
    assert root == new_root
    assert root.tool == new_root.tool
    assert root.tool_instance == new_root.tool
    assert root.alert_type == new_root.alert_type
    assert root.description == new_root.description
    assert root.event_time == new_root.event_time
    assert root.name == new_root.name
    assert root.analysis_mode == new_root.analysis_mode
    assert root.queue == new_root.queue
    assert root.instructions == new_root.instructions

    # the observable property for the root should always be None
    assert root.observable is None
    assert len(root.observables) == 1


@pytest.mark.unit
def test_analysis_properties():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt, details={"test": "test"})
    observable_2 = analysis.add_observable("test2", "test2")

    assert analysis.uuid
    assert analysis.root == root
    assert analysis.type == amt
    assert analysis.observable == observable
    assert analysis.observables == [observable_2]
    assert analysis.details == {"test": "test"}
    assert analysis.children == [observable_2]
    assert analysis.observable_types == ["test2"]


@pytest.mark.unit
def test_analysis_get_observables_by_type():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    observable_2 = analysis.add_observable("test", "test_2")
    observable_3 = analysis.add_observable("test", "test_3")
    observable_4 = analysis.add_observable("test_4", "test_4")

    assert analysis.get_observables_by_type("test") == [observable_2, observable_3]
    assert analysis.get_observables_by_type("test_4") == [observable_4]
    assert analysis.get_observables_by_type("unknown") == []

    assert analysis.get_observable_by_type("test") in [observable_2, observable_3]
    assert analysis.get_observable_by_type("test_4") == observable_4
    assert analysis.get_observable_by_type("unknown") is None


@pytest.mark.unit
def test_root_analysis_get_observables_by_type():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable_1 = root.add_observable("test", "test_1")
    observable_2 = root.add_observable("test", "test_2")
    observable_3 = root.add_observable("test_3", "test_3")
    analysis = observable_3.add_analysis(type=amt)
    observable_4 = analysis.add_observable("test_4", "test_4")

    assert root.get_observables_by_type("test") == [observable_1, observable_2]
    assert root.get_observables_by_type("test_3") == [observable_3]
    assert root.get_observables_by_type("test_4") == [observable_4]
    assert root.get_observables_by_type("unknown") == []

    assert root.get_observable_by_type("test") in [observable_1, observable_2]
    assert root.get_observable_by_type("test_3") == observable_3
    assert root.get_observable_by_type("test_4") == observable_4
    assert root.get_observable_by_type("unknown") is None


@pytest.mark.integration
def test_add_analysis():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")

    # test adding an Analysis object
    analysis = Analysis(details={"hello": "world"}, type=amt)
    result = observable.add_analysis(analysis)
    assert result == analysis

    # test adding just a details, type
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(details={"hello": "world"}, type=amt)
    assert result == analysis


@pytest.mark.integration
def test_add_analysis_no_amt():
    """An Analysis must have a type before it can be added."""
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    with pytest.raises(ValueError):
        observable.add_analysis(Analysis())


@pytest.mark.integration
def test_analysis_save():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    root.save()

    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    # the details have not been set so there is nothing to save
    assert not analysis.save()
    assert get_analysis_details(analysis.uuid) is None

    # set the details
    analysis.details = TEST_DETAILS
    # now it should save
    assert analysis.save()
    assert get_analysis_details(analysis.uuid) == TEST_DETAILS

    # save it again, since it didn't change it should not try to save again
    assert not analysis.save()

    # modify the details
    analysis.details = {"hey": "there"}
    assert analysis.save()
    assert get_analysis_details(analysis.uuid) == {"hey": "there"}


@pytest.mark.integration
def test_analysis_load():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis(details=TEST_DETAILS)
    observable = root.add_observable(F_TEST, "test")
    analysis = observable.add_analysis(type=amt, details=TEST_DETAILS)
    root.save()

    root = get_root_analysis(root.uuid)
    # the details should not be loaded yet
    assert root._details is None
    # until we access it
    assert root.details == TEST_DETAILS
    # and then it is loaded
    assert root._details is not None

    # same for Analysis objects
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt)
    assert analysis._details is None
    assert analysis.details == TEST_DETAILS
    assert analysis._details is not None


@pytest.mark.unit
def test_analysis_completed():
    register_analysis_module_type(amt := AnalysisModuleType("test", "test", [F_TEST]))

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    assert not root.analysis_completed(observable, amt)

    observable.add_analysis(Analysis(type=amt, details=TEST_DETAILS))
    assert root.analysis_completed(observable, amt)

    # unknown observable
    with pytest.raises(UnknownObservableError):
        root.analysis_completed(RootAnalysis().add_observable("test", "blah"), amt)


@pytest.mark.unit
def test_analysis_tracked():
    register_analysis_module_type(amt := AnalysisModuleType("test", "test", [F_TEST]))

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    assert not root.analysis_tracked(observable, amt)

    ar = observable.create_analysis_request(amt)
    observable.track_analysis_request(ar)
    assert root.analysis_tracked(observable, amt)

    # invalid observable
    with pytest.raises(UnknownObservableError):
        root.analysis_tracked(RootAnalysis().add_observable("test", "blah"), amt)


@pytest.mark.integration
def test_analysis_flush():
    register_analysis_module_type(amt := AnalysisModuleType("test", "test", [F_TEST]))
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt, details=TEST_DETAILS)
    root.save()

    root = get_root_analysis(root.uuid)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt)
    analysis.flush()
    # should be gone
    assert analysis._details is None
    # but can load it back
    assert analysis.details == TEST_DETAILS


@pytest.mark.unit
def test_has_observable():
    root = RootAnalysis()
    observable = root.add_observable(F_TEST, "test")
    assert root.has_observable(F_TEST, "test")
    assert not root.has_observable(F_TEST, "t3st")
    assert root.has_observable(Observable("test", "test"))
    assert not root.has_observable(Observable("t3st", "test"))
    assert not root.has_observable(Observable("test", "t3st"))


@pytest.mark.unit
def test_root_find_observables():
    root = RootAnalysis()
    o1 = root.add_observable(F_TEST, "test_1")
    o2 = root.add_observable(F_TEST, "test_2")
    o_all = sorted([o1, o2])

    # search by type, single observable
    assert root.find_observable(F_TEST).uuid in [o.uuid for o in o_all]
    # search by type, multi observable
    assert sorted(root.find_observables(F_TEST)) == o_all

    # search by lambda, single observable
    assert root.find_observable(lambda o: o.type == F_TEST).uuid in [o.uuid for o in o_all]
    # search by lambda, multi observable
    assert sorted(root.find_observables(lambda o: o.type == F_TEST)) == o_all


@pytest.mark.unit
def test_analysis_find_observables():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "no find")
    analysis = observable.add_analysis(type=amt)
    o1 = analysis.add_observable("test", "test_1")
    o2 = analysis.add_observable("test", "test_2")
    o_all = sorted([o1, o2])

    # search by type, single observable
    assert analysis.find_observable("test") in o_all
    # search by type, multi observable
    assert sorted(analysis.find_observables("test")) == o_all

    # search by lambda, single observable
    assert analysis.find_observable(lambda o: o.type == "test") in o_all
    # search by lambda, multi observable
    assert sorted(analysis.find_observables(lambda o: o.type == "test")) == o_all


@pytest.mark.unit
def test_analysis_eq():
    amt_1 = AnalysisModuleType("test1", "")
    amt_2 = AnalysisModuleType("test2", "")

    root = RootAnalysis()
    observable_1 = root.add_observable("test", "test")
    analysis_1 = observable_1.add_analysis(type=amt_1)
    analysis_2 = observable_1.add_analysis(type=amt_2)
    observable_2 = root.add_observable("test2", "test")
    analysis_3 = observable_2.add_analysis(type=amt_1)

    # different amt
    assert analysis_1 != analysis_2
    # different observable
    assert analysis_1 != analysis_3
    # wrong object type
    assert analysis_1 != object()

    root_1 = RootAnalysis.from_dict(root.to_dict())
    root_2 = RootAnalysis.from_dict(root.to_dict())

    # same amt and observable
    assert root_1.get_observable(observable_1).get_analysis(amt_1) == root_2.get_observable(observable_1).get_analysis(
        amt_1
    )


@pytest.mark.integration
def test_root_analysis_apply_merge():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    root.save()

    target_root = get_root_analysis(root)
    target_root.analysis_mode = "some_mode"
    target_root.queue = "some_queue"
    target_root.description = "some description"

    root = get_root_analysis(root)
    root.apply_merge(target_root)

    assert root.analysis_mode == target_root.analysis_mode
    assert root.queue == target_root.queue
    assert root.description == target_root.description


@pytest.mark.unit
def test_root_analysis_merge_with_observables():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    existing_observable = root.add_observable("test", "test")
    existing_analysis = existing_observable.add_analysis(type=amt)
    root.save()

    target_root = get_root_analysis(root)
    # add a new observable to the root
    new_observable = target_root.add_observable("test", "new")
    # and then add a new analysis to that
    new_analysis = new_observable.add_analysis(type=amt)

    root = get_root_analysis(root)
    root.apply_merge(target_root)

    # existing observable and analysis should be there
    assert root.get_observable(existing_observable) == existing_observable
    assert root.get_observable(existing_observable).get_analysis(amt) == existing_analysis
    # and the new obs
    assert root.get_observable(new_observable) == new_observable
    assert root.get_observable(new_observable).get_analysis(amt) == new_analysis


@pytest.mark.unit
def test_create_analysis_request():
    root = RootAnalysis()
    request = root.create_analysis_request()
    assert isinstance(request, AnalysisRequest)
    assert request.root == root
    assert request.observable is None
    assert request.type is None
    assert request.is_root_analysis_request


@pytest.mark.unit
def test_deepcopy_root():
    import copy

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    amt = AnalysisModuleType("test", "")
    analysis = observable.add_analysis(type=amt, details={"test": "test"})

    root_copy = copy.deepcopy(root)
    observable_copy = root_copy.get_observable(observable)
    assert observable_copy == observable
    assert not (observable_copy is observable)
    analysis_copy = observable_copy.get_analysis(amt)
    assert analysis_copy == analysis
    assert not (analysis_copy is analysis)


@pytest.mark.unit
def test_storage_dir(tmpdir):
    root = RootAnalysis()
    assert root.storage_dir is None
    # use the default temp dir
    root.initialize_storage()
    assert root.storage_dir
    assert os.path.isdir(root.storage_dir)
    path = root.storage_dir
    root.discard()
    assert root.storage_dir is None
    assert not os.path.isdir(path)

    # specify a temp dir
    path = str(tmpdir.mkdir("temp"))
    root = RootAnalysis()
    assert root.storage_dir is None
    root.initialize_storage(path)
    assert root.storage_dir == path
    assert os.path.exists(path)
    root.discard()
    assert root.storage_dir is None
    assert not os.path.exists(path)

    # specify a temp dir that does not exist yet
    # we'll re-use the previous one
    root = RootAnalysis()
    assert root.storage_dir is None
    root.initialize_storage(path)  # does not currently exist
    assert root.storage_dir == path
    assert os.path.exists(path)
    root.discard()
    assert root.storage_dir is None
    assert not os.path.exists(path)

    # delete on gc
    root = RootAnalysis()
    root.initialize_storage()
    assert os.path.exists(root.storage_dir)
    path = root.storage_dir
    root = None
    import gc

    gc.collect()
    assert not os.path.exists(path)


@pytest.mark.unit
def test_root_str():
    assert str(RootAnalysis())
    root = RootAnalysis()
    root.initialize_storage()
    assert str(root)


@pytest.mark.unit
def test_root_eq():
    # two different uuids
    assert RootAnalysis() != RootAnalysis()
    root = RootAnalysis()
    # same uuids
    assert root == copy.deepcopy(root)
    # invalid compare
    assert root != object()


@pytest.mark.unit
def test_root_all():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    observable_2 = analysis.add_observable("test", "test2")

    assert sorted(root.all) == sorted([root, analysis, observable, observable_2])


@pytest.mark.unit
def test_root_all_tags():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    observable_2 = analysis.add_observable("test", "test2")

    root.add_tag("tag1")
    observable.add_tag("tag2")
    analysis.add_tag("tag3")
    observable_2.add_tag("tag4")

    assert sorted(root.all_tags) == sorted(["tag1", "tag2", "tag3", "tag4"])

    # add a duplicate tag so tag2 exists twice
    root.add_tag("tag2")

    # should be the same list
    assert sorted(root.all_tags) == sorted(["tag1", "tag2", "tag3", "tag4"])


@pytest.mark.unit
def test_root_all_refs():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    observable_2 = analysis.add_observable("test", "test2")

    # root refers to observable
    assert root.get_all_references(observable) == [root]

    # observable refers to analysis
    assert root.get_all_references(analysis) == [observable]

    # analysis refers to observable2
    assert root.get_all_references(observable_2) == [analysis]

    # nothing refers to the root
    assert root.get_all_references(root) == []


@pytest.mark.unit
def test_root_all_detection_points():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    observable_2 = analysis.add_observable("test", "test2")

    root.add_detection_point("test")
    assert root.all_detection_points == [DetectionPoint("test")]
    observable.add_detection_point("test")
    assert root.all_detection_points == [DetectionPoint("test"), DetectionPoint("test")]
    analysis.add_detection_point("test")
    assert root.all_detection_points == [DetectionPoint("test"), DetectionPoint("test"), DetectionPoint("test")]
    observable_2.add_detection_point("test")
    assert root.all_detection_points == [
        DetectionPoint("test"),
        DetectionPoint("test"),
        DetectionPoint("test"),
        DetectionPoint("test"),
    ]


@pytest.mark.unit
def test_root_get_observable():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")

    # get by uuid
    assert root.get_observable(observable.uuid) == observable
    # get by identity
    assert root.get_observable(observable) == observable
    # get by new object
    assert root.get_observable(RootAnalysis().add_observable("test", "test")) == observable
    # get invalid object
    assert root.get_observable("") is None
    assert root.get_observable(RootAnalysis().add_observable("test", "blah")) is None


#
# Merging
#


@pytest.mark.unit
def test_apply_merge_different_roots():
    # you cannot merge two different roots together
    with pytest.raises(ValueError):
        RootAnalysis().apply_merge(RootAnalysis())


@pytest.mark.unit
def test_apply_diff_merge_different_roots():
    # you cannot merge two different roots together
    with pytest.raises(ValueError):
        RootAnalysis().apply_diff_merge(RootAnalysis(), RootAnalysis())


@pytest.mark.unit
def test_root_diff_merge():
    target = RootAnalysis()
    before = RootAnalysis()
    after = copy.deepcopy(before)
    after.analysis_mode = "test"
    after.queue = "test"
    after.description = "test"
    after.analysis_cancelled = True
    after.analysis_cancelled_reason = "test"

    target.apply_diff_merge(before, after)
    assert target.analysis_mode == "test"
    assert target.queue == "test"
    assert target.description == "test"
    assert target.analysis_cancelled
    assert target.analysis_cancelled_reason == "test"


@pytest.mark.unit
def test_recurse_down():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    child = analysis.add_observable("test", "child")
    observable_2 = root.add_observable("test", "other")

    # we'll build a list of the nodes we visit
    result = []

    def _callback(node):
        result.append(node)

    # R -> O1 -> A -> O2
    #   -> O3
    recurse_down(root, _callback)
    assert result == [root]

    result = []
    recurse_down(observable, _callback)
    assert result == [observable, root]

    result = []
    recurse_down(analysis, _callback)
    assert result == [analysis, observable, root]

    result = []
    recurse_down(child, _callback)
    assert result == [child, analysis, observable, root]

    result = []
    recurse_down(observable_2, _callback)
    assert result == [observable_2, root]

    # R -> O1 -> A -> O1
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    # this points to the same observable as before
    child = analysis.add_observable("test", "test")

    result = []
    recurse_down(observable, _callback)
    assert len(result) == 3
    # (order is random when there are multiple paths to root)
    assert analysis in result and observable in result and root in result


@pytest.mark.unit
def test_search_down():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    child = analysis.add_observable("test", "child")
    observable_2 = root.add_observable("test", "other")

    assert search_down(child, lambda obj: obj == analysis) == analysis
    assert search_down(child, lambda obj: obj == observable) == observable
    assert search_down(child, lambda obj: obj == root) == root
    assert search_down(child, lambda obj: False) is None


@pytest.mark.unit
def test_recurse_tree():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    child = analysis.add_observable("test", "child")
    observable_2 = root.add_observable("test", "other")

    result = []

    def _callback(node):
        result.append(node)

    recurse_tree(child, _callback)
    assert result == [child]

    result = []
    recurse_tree(analysis, _callback)
    assert result == [analysis, child]

    result = []
    recurse_tree(observable, _callback)
    assert result == [observable, analysis, child]

    result = []
    recurse_tree(root, _callback)
    assert result == [root, observable, analysis, child, observable_2]

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    # refers to prev observable
    child = analysis.add_observable("test", "test")

    result = []
    recurse_tree(root, _callback)
    assert result == [root, observable, analysis]


@pytest.mark.integration
def test_apply_merge_analysis():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    target_observable.add_analysis(Analysis(type=amt))

    assert not observable.analysis
    observable.apply_merge(target_observable)
    assert observable.analysis
    assert observable.get_analysis("test") is not None


@pytest.mark.integration
def test_apply_diff_merge_analysis():
    amt = AnalysisModuleType("test", "")
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    modified_observable.add_analysis(type=amt)

    target_root = copy.deepcopy(original_root)
    target_observable = target_root.get_observable(original_observable)

    assert not target_observable.analysis
    target_observable.apply_diff_merge(original_observable, modified_observable, amt)
    assert target_observable.analysis
    assert target_observable.get_analysis("test") is not None

    # exists before but not after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)

    target_root = copy.deepcopy(original_root)
    target_observable = target_root.get_observable(original_observable)

    original_observable.add_analysis(type=amt)

    assert not target_observable.analysis
    target_observable.apply_diff_merge(original_observable, modified_observable)
    assert not target_observable.analysis


@pytest.mark.integration
def test_apply_merge_analysis_with_observables():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    analysis = target_observable.add_analysis(Analysis(type=amt))
    extra_observable = analysis.add_observable("other_type", "other_value")

    assert not root.get_observable(extra_observable)
    observable.apply_merge(target_observable)
    assert root.get_observable(extra_observable) == extra_observable


@pytest.mark.integration
def test_apply_diff_merge_analysis_with_observables():
    amt = AnalysisModuleType("test", "")
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    analysis = modified_observable.add_analysis(type=amt)
    new_observable = analysis.add_observable("new", "new")

    target_root = copy.deepcopy(original_root)
    target_observable = target_root.get_observable(original_observable)

    assert not target_root.get_observable(new_observable)
    target_observable.apply_diff_merge(original_observable, modified_observable, type=amt)
    assert target_root.get_observable(new_observable) == new_observable

    # exists before but not after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)

    target_root = copy.deepcopy(original_root)
    target_observable = target_root.get_observable(original_observable)

    analysis = original_observable.add_analysis(type=amt)
    new_observable = analysis.add_observable("new", "new")

    assert not target_root.get_observable(new_observable)
    target_observable.apply_diff_merge(original_observable, modified_observable)
    assert not target_root.get_observable(new_observable)


@pytest.mark.integration
def test_apply_merge_analysis_with_existing_observables():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")
    existing_extra_observable = root.add_observable("other_type", "other_value")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    analysis = target_observable.add_analysis(Analysis(type=amt))
    extra_observable = analysis.add_observable("other_type", "other_value")

    # should only have the root as the parent
    assert len(existing_extra_observable.parents) == 1
    observable.apply_merge(target_observable)
    # should now have both the root and the new analysis as parents
    assert len(existing_extra_observable.parents) == 2


@pytest.mark.integration
def test_apply_diff_merge_analysis_with_existing_observables():
    amt = AnalysisModuleType("test", "")
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    existing_observable = original_root.add_observable("existing", "existing")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    analysis = modified_observable.add_analysis(type=amt)
    new_observable = analysis.add_observable("existing", "existing")

    target_root = copy.deepcopy(original_root)
    target_observable = target_root.get_observable(original_observable)
    existing_observable = target_root.get_observable(existing_observable)

    # should only have the root as the parent
    assert len(existing_observable.parents) == 1
    target_observable.apply_diff_merge(original_observable, modified_observable, amt)
    # should now have both the root and the new analysis as parents
    assert len(existing_observable.parents) == 2

    # exists before but not after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    existing_observable = original_root.add_observable("existing", "existing")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)

    target_root = copy.deepcopy(original_root)
    target_observable = target_root.get_observable(original_observable)
    existing_observable = target_root.get_observable(existing_observable)

    analysis = original_observable.add_analysis(type=amt)
    new_observable = analysis.add_observable("existing", "existing")

    # should only have the root as the parent
    assert len(existing_observable.parents) == 1
    target_observable.apply_diff_merge(original_observable, modified_observable)
    # should not have changed
    assert len(existing_observable.parents) == 1
