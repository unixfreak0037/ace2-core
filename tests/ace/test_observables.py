import copy
import os.path
import shutil

import pytest

from ace.analysis import RootAnalysis, AnalysisModuleType, Analysis
from ace.constants import R_DOWNLOADED_FROM
from ace.system.analysis_tracking import get_root_analysis


@pytest.mark.unit
def test_add_limited_analysis():
    observable = RootAnalysis().add_observable("test", "test")
    assert not observable.limited_analysis
    observable.limit_analysis("test")
    assert observable.limited_analysis
    assert "test" in observable.limited_analysis

    observable.limit_analysis(AnalysisModuleType("other", ""))
    assert "other" in observable.limited_analysis


@pytest.mark.unit
def test_add_excluded_analysis():
    observable = RootAnalysis().add_observable("test", "test")
    assert not observable.excluded_analysis
    assert not observable.is_excluded("test")
    observable.exclude_analysis("test")
    assert observable.excluded_analysis
    assert "test" in observable.excluded_analysis
    assert observable.is_excluded("test")

    observable.exclude_analysis(AnalysisModuleType("other", ""))
    assert "other" in observable.excluded_analysis


@pytest.mark.unit
def test_apply_merge_directives():
    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    target_observable.add_directive("some_directive")

    assert not observable.has_directive("some_directive")
    observable.apply_merge(target_observable)
    assert observable.has_directive("some_directive")


@pytest.mark.unit
def test_apply_diff_merge_directives():
    # does not exist before but exists after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    modified_observable.add_directive("test")

    target_root = RootAnalysis()
    observable = target_root.add_observable("test", "test")
    assert not observable.has_directive("test")
    observable.apply_diff_merge(original_observable, modified_observable)
    assert observable.has_directive("test")

    # exists before but not after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    original_observable.add_directive("test")
    modified_observable = modified_root.get_observable(original_observable)

    target_root = RootAnalysis()
    observable = target_root.add_observable("test", "test")
    assert not observable.has_directive("test")
    observable.apply_diff_merge(original_observable, modified_observable)
    # should still not exist
    assert not observable.has_directive("test")


@pytest.mark.unit
def test_apply_merge_redirection():
    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")

    # test the case where the redirection target does not exist in the root analysis

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    target_redirection_observable = target_root.add_observable("other_type", "other_value")
    target_observable.redirection = target_redirection_observable

    assert observable.redirection is None
    observable.apply_merge(target_observable)
    assert observable.redirection == target_redirection_observable

    # also test the case where the redirection target already exists in the root analysis

    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")
    root.add_observable("other_type", "other_value")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    target_redirection_observable = target_root.add_observable("other_type", "other_value")
    target_observable.redirection = target_redirection_observable

    assert observable.redirection is None
    observable.apply_merge(target_observable)
    assert observable.redirection == target_redirection_observable


@pytest.mark.unit
def test_apply_diff_merge_redirection():
    # test redirection created
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    modified_observable.redirection = modified_root.add_observable("target", "target")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("test", "test")

    assert target_observable.redirection is None
    target_observable.apply_diff_merge(original_observable, modified_observable)
    assert target_root.get_observable(modified_observable.redirection)
    assert target_observable.redirection == target_root.get_observable(modified_observable.redirection)

    # test redirection modified
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    original_observable.redirection = original_root.add_observable("target", "target")

    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    modified_observable.redirection = modified_root.add_observable("other", "other")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("test", "test")

    assert target_observable.redirection is None
    target_observable.apply_diff_merge(original_observable, modified_observable)
    assert target_root.get_observable(modified_observable.redirection)
    assert target_observable.redirection == target_root.get_observable(modified_observable.redirection)


@pytest.mark.unit
def test_apply_merge_links():
    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")

    # test the case where the link target does not exist in the root analysis

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    linked_observable = target_root.add_observable("other_type", "other_value")
    target_observable.add_link(linked_observable)

    assert not observable.links
    observable.apply_merge(target_observable)
    assert observable.links
    assert observable.links[0] == linked_observable

    # also test the case where the link target already exists in the root analysis

    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")
    root.add_observable("other_type", "other_value")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    linked_observable = target_root.add_observable("other_type", "other_value")
    target_observable.add_link(linked_observable)

    assert not observable.links
    observable.apply_merge(target_observable)
    assert observable.links
    assert observable.links[0] == linked_observable


@pytest.mark.unit
def test_apply_diff_merge_links():
    # does not exist before but exists after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    link_target = modified_root.add_observable("target", "target")
    modified_observable.add_link(link_target)

    target_root = RootAnalysis()
    observable = target_root.add_observable("test", "test")
    assert not observable.links
    observable.apply_diff_merge(original_observable, modified_observable)
    linked_observable = target_root.get_observable(link_target)
    assert linked_observable
    assert observable.links[0] == linked_observable

    # exists before but not after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)

    link_target = original_root.add_observable("target", "target")
    original_observable.add_link(link_target)

    target_root = RootAnalysis()
    observable = target_root.add_observable("test", "test")
    assert not observable.links
    observable.apply_diff_merge(original_observable, modified_observable)
    # should still not exist
    assert not observable.links


@pytest.mark.unit
def test_apply_merge_limited_analysis():
    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    target_observable.limit_analysis("some_module")

    assert not observable.limited_analysis
    observable.apply_merge(target_observable)
    assert observable.limited_analysis
    assert observable.limited_analysis[0] == "some_module"


@pytest.mark.unit
def test_apply_diff_merge_limited_analysis():
    # does not exist before but exists after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    modified_observable.limit_analysis("test")

    target_root = RootAnalysis()
    observable = target_root.add_observable("test", "test")
    assert not observable.limited_analysis
    observable.apply_diff_merge(original_observable, modified_observable)
    assert observable.limited_analysis[0] == "test"

    # exists before but not after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)

    original_observable.limit_analysis("test")

    target_root = RootAnalysis()
    observable = target_root.add_observable("test", "test")
    assert not observable.limited_analysis
    observable.apply_diff_merge(original_observable, modified_observable)
    # should still not exist
    assert not observable.limited_analysis


@pytest.mark.unit
def test_apply_merge_excluded_analysis():
    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    target_observable.exclude_analysis("some_module")

    assert not observable.excluded_analysis
    observable.apply_merge(target_observable)
    assert observable.excluded_analysis
    assert observable.excluded_analysis[0] == "some_module"


@pytest.mark.unit
def test_apply_diff_merge_excluded_analysis():
    # does not exist before but exists after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    modified_observable.exclude_analysis("test")

    target_root = RootAnalysis()
    observable = target_root.add_observable("test", "test")
    assert not observable.excluded_analysis
    observable.apply_diff_merge(original_observable, modified_observable)
    assert observable.excluded_analysis[0] == "test"

    # exists before but not after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)

    original_observable.exclude_analysis("test")

    target_root = RootAnalysis()
    observable = target_root.add_observable("test", "test")
    assert not observable.excluded_analysis
    observable.apply_diff_merge(original_observable, modified_observable)
    # should still not exist
    assert not observable.excluded_analysis


@pytest.mark.unit
def test_apply_merge_relationships():
    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")

    # test the case where the relationship target does not exist in the root analysis

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    r_observable = target_root.add_observable("other_type", "other_value")
    target_observable.add_relationship(R_DOWNLOADED_FROM, r_observable)

    assert not observable.relationships
    observable.apply_merge(target_observable)
    assert observable.relationships
    assert observable.relationships[0].r_type == R_DOWNLOADED_FROM
    assert observable.relationships[0].target == r_observable

    # also test the case where the relationship target already exists in the root analysis

    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")
    root.add_observable("other_type", "other_value")

    # test the case where the relationship target does not exist in the root analysis

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    r_observable = target_root.add_observable("other_type", "other_value")
    target_observable.add_relationship(R_DOWNLOADED_FROM, r_observable)

    assert not observable.relationships
    observable.apply_merge(target_observable)
    assert observable.relationships
    assert observable.relationships[0].r_type == R_DOWNLOADED_FROM
    assert observable.relationships[0].target == r_observable


@pytest.mark.unit
def test_apply_diff_merge_relationships():
    # does not exist before but exists after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    target_observable = modified_root.add_observable("target", "target")
    modified_observable.add_relationship(R_DOWNLOADED_FROM, target_observable)

    target_root = RootAnalysis()
    observable = target_root.add_observable("test", "test")
    assert not observable.relationships
    observable.apply_diff_merge(original_observable, modified_observable)
    target_observable = target_root.get_observable(target_observable)
    assert observable.relationships[0].r_type == R_DOWNLOADED_FROM
    assert observable.relationships[0].target == target_observable

    # exists before but not after
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)

    target_observable = original_root.add_observable("target", "target")
    original_observable.add_relationship(R_DOWNLOADED_FROM, target_observable)

    target_root = RootAnalysis()
    observable = target_root.add_observable("test", "test")
    assert not observable.relationships
    observable.apply_diff_merge(original_observable, modified_observable)
    # should still not exist
    assert not observable.relationships


@pytest.mark.unit
def test_apply_merge_grouping_target():
    root = RootAnalysis()
    observable = root.add_observable("some_type", "some_value")

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("some_type", "some_value")
    target_observable.grouping_target = True

    assert not observable.grouping_target
    observable.apply_merge(target_observable)
    assert observable.grouping_target


@pytest.mark.unit
def test_apply_diff_merge_grouping_target():
    # grouping target modified
    original_root = RootAnalysis()
    original_observable = original_root.add_observable("test", "test")
    modified_root = copy.deepcopy(original_root)
    modified_observable = modified_root.get_observable(original_observable)
    modified_observable.grouping_target = True

    target_root = RootAnalysis()
    target_observable = target_root.add_observable("test", "test")

    assert not target_observable.grouping_target
    target_observable.apply_diff_merge(original_observable, modified_observable)
    assert target_observable.grouping_target
