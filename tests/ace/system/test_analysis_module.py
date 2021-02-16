# vim: ts=4:sw=4:et:cc=120

import pytest

from ace.analysis import RootAnalysis, Observable, Analysis
from ace.system.analysis_module import (
    AnalysisModuleType,
    AnalysisModuleTypeVersionError,
    AnalysisModuleTypeExtendedVersionError,
    delete_analysis_module_type,
    get_analysis_module_type,
    register_analysis_module_type,
)
from ace.system.caching import get_cached_analysis_result
from ace.system.work_queue import get_queue_size, get_next_analysis_request

amt_1 = AnalysisModuleType(
    name="test", description="test", version="1.0.0", timeout=30, cache_ttl=600, additional_cache_keys=["key1"]
)

amt_1_same = AnalysisModuleType(
    name="test", description="test", version="1.0.0", timeout=30, cache_ttl=600, additional_cache_keys=["key1"]
)

amt_1_upgraded_version = AnalysisModuleType(
    name="test", description="test", version="2.0.0", timeout=30, additional_cache_keys=["key1"]
)

amt_1_upgraded_cache_keys = AnalysisModuleType(
    name="test", description="test", version="1.0.0", timeout=30, additional_cache_keys=["key2"]
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "left, right, expected",
    [
        (amt_1, amt_1_same, True),
        (amt_1, amt_1_upgraded_version, False),
        (amt_1, amt_1_upgraded_cache_keys, False),
    ],
)
def test_version_matches(left, right, expected):
    assert left.extended_version_matches(right) == expected


@pytest.mark.integration
def test_register_new_analysis_module_type():
    assert register_analysis_module_type(amt_1) == amt_1
    assert get_analysis_module_type(amt_1.name) == amt_1
    assert get_queue_size(amt_1) == 0


@pytest.mark.integration
def test_register_existing_analysis_module_type():
    assert register_analysis_module_type(amt_1) == amt_1
    assert get_analysis_module_type(amt_1.name) == amt_1
    wq = get_queue_size(amt_1) == 0

    # amt_1 is the same as amt so only the amt record changes
    assert register_analysis_module_type(amt_1_same) == amt_1_same
    assert get_analysis_module_type(amt_1_same.name) == amt_1_same

    # now the version changes with an upgraded version
    assert register_analysis_module_type(amt_1_upgraded_version) == amt_1_upgraded_version
    assert get_analysis_module_type(amt_1_same.name) == amt_1_upgraded_version
    with pytest.raises(AnalysisModuleTypeVersionError):
        get_next_analysis_request("test", amt_1, 0)  # now this request is invalid because am1 is an older version
    # same but only passing the name and version of the module
    with pytest.raises(AnalysisModuleTypeVersionError):
        get_next_analysis_request(
            "test", "test", 0, version="1.0.0"
        )  # now this request is invalid because am1 is an older version
    assert get_next_analysis_request("test", amt_1_upgraded_version, 0) is None  # but this works

    # extended version data changed
    assert register_analysis_module_type(amt_1_upgraded_cache_keys) == amt_1_upgraded_cache_keys
    assert get_analysis_module_type(amt_1_same.name) == amt_1_upgraded_cache_keys
    with pytest.raises(AnalysisModuleTypeExtendedVersionError):
        get_next_analysis_request(
            "test", amt_1, 0
        )  # now this request is invalid because am1 has different extended version
    # same but only passing name, version and extended versions of the data
    with pytest.raises(AnalysisModuleTypeExtendedVersionError):
        get_next_analysis_request(
            "test",
            "test",
            0,
            "1.0.0",
            ["key1"],
        )  # now this request is invalid because am1 has different extended version
    assert get_next_analysis_request("test", amt_1_upgraded_cache_keys, 0) is None  # but this works


@pytest.mark.integration
def test_delete_analysis_module_type():
    amt = AnalysisModuleType("test", "", cache_ttl=300)
    register_analysis_module_type(amt)

    assert get_analysis_module_type(amt.name)
    delete_analysis_module_type(amt)
    assert get_analysis_module_type(amt.name) is None


class TempAnalysisModuleType(AnalysisModuleType):
    def __init__(self, *args, **kwargs):
        super().__init__(name="test", description="test", *args, **kwargs)


@pytest.mark.parametrize(
    "amt,observable,expected_result",
    [
        # no requirements at all
        (TempAnalysisModuleType(), RootAnalysis().add_observable("test", "test"), True),
        # correct observable type
        (TempAnalysisModuleType(observable_types=["test"]), RootAnalysis().add_observable("test", "test"), True),
        # incorrect observable type
        (TempAnalysisModuleType(observable_types=["test"]), RootAnalysis().add_observable("ipv4", "1.2.3.4"), False),
        # multiple observable types (currently OR)
        (
            TempAnalysisModuleType(observable_types=["test", "ipv4"]),
            RootAnalysis().add_observable("ipv4", "1.2.3.4"),
            True,
        ),
        # correct analysis mode
        (
            TempAnalysisModuleType(modes=["correlation"]),
            RootAnalysis(analysis_mode="correlation").add_observable("ipv4", "1.2.3.4"),
            True,
        ),
        # incorrect analysis mode
        (
            TempAnalysisModuleType(modes=["analysis"]),
            RootAnalysis(analysis_mode="correlation").add_observable("ipv4", "1.2.3.4"),
            False,
        ),
        # multiple analysis modes (currently OR)
        (
            TempAnalysisModuleType(modes=["analysis", "correlation"]),
            RootAnalysis(analysis_mode="correlation").add_observable("ipv4", "1.2.3.4"),
            True,
        ),
        # valid directive
        (
            TempAnalysisModuleType(directives=["crawl"]),
            RootAnalysis().add_observable("ipv4", "1.2.3.4").add_directive("crawl"),
            True,
        ),
        # invalid directive
        (TempAnalysisModuleType(directives=["crawl"]), RootAnalysis().add_observable("ipv4", "1.2.3.4"), False),
        # multiple directives (currently AND)
        (
            TempAnalysisModuleType(directives=["crawl", "sandbox"]),
            RootAnalysis().add_observable("ipv4", "1.2.3.4").add_directive("crawl").add_directive("sandbox"),
            True,
        ),
        # multiple directives missing one (currently AND)
        (
            TempAnalysisModuleType(directives=["crawl", "sandbox"]),
            RootAnalysis().add_observable("ipv4", "1.2.3.4").add_directive("crawl"),
            False,
        ),
        # valid tag
        (TempAnalysisModuleType(tags=["test"]), RootAnalysis().add_observable("ipv4", "1.2.3.4").add_tag("test"), True),
        # invalid tag
        (TempAnalysisModuleType(tags=["test"]), RootAnalysis().add_observable("ipv4", "1.2.3.4"), False),
        # multiple tags (currently AND)
        (
            TempAnalysisModuleType(tags=["test_1", "test_2"]),
            RootAnalysis().add_observable("ipv4", "1.2.3.4").add_tag("test_1").add_tag("test_2"),
            True,
        ),
        # multiple tags missing one
        (
            TempAnalysisModuleType(tags=["test_1", "test_2"]),
            RootAnalysis().add_observable("ipv4", "1.2.3.4").add_tag("test_1"),
            False,
        ),
        # limited analysis
        (
            TempAnalysisModuleType(),
            RootAnalysis().add_observable(Observable("test", "test", limited_analysis=["test"])),
            True,
        ),
        # limited analysis (not in list)
        (
            TempAnalysisModuleType(),
            RootAnalysis().add_observable(Observable("test", "test", limited_analysis=["other"])),
            False,
        ),
        # excluded analysis
        (
            TempAnalysisModuleType(),
            RootAnalysis().add_observable(Observable("test", "test", excluded_analysis=["test"])),
            False,
        ),
        # excluded analysis (not in list)
        (
            TempAnalysisModuleType(),
            RootAnalysis().add_observable(Observable("test", "test", excluded_analysis=["other"])),
            True,
        ),
        # manual analysis, no directive
        (
            TempAnalysisModuleType(manual=True),
            RootAnalysis().add_observable(Observable("test", "test")),
            False,
        ),
        # manual analysis, with directive
        (
            TempAnalysisModuleType(manual=True),
            RootAnalysis().add_observable(Observable("test", "test", requested_analysis=["test"])),
            True,
        ),
        # regex conditions
        (
            TempAnalysisModuleType(conditions=["re:test"]),
            RootAnalysis().add_observable("test", "test"),
            True,
        ),
        (
            TempAnalysisModuleType(conditions=["re:t3st"]),
            RootAnalysis().add_observable("test", "test"),
            False,
        ),
        # valid dependency TODO
        # TODO need to start making modifications to RootAnalysis, Analysis and Observable to support this new system
        # (TempAnalysisModuleType(dependencies=['analysis_module']), RootAnalysis().add_observable("ipv4", '1.2.3.4'), True),
    ],
)
@pytest.mark.integration
def test_accepts(amt: AnalysisModuleType, observable: Observable, expected_result: bool):
    assert amt.accepts(observable) == expected_result
