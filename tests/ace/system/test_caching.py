# vim: ts=4:sw=4:et:cc=120

import datetime

import pytest

from ace.analysis import RootAnalysis, Observable

from ace.system.analysis_module import AnalysisModuleType, register_analysis_module_type
from ace.system.caching import (
    generate_cache_key,
    cache_analysis_result,
    get_cached_analysis_result,
    get_total_cache_size,
    delete_expired_cached_analysis_results,
    delete_cached_analysis_results_by_module_type,
)
from ace.system.work_queue import get_next_analysis_request

amt_1 = AnalysisModuleType(name="test_1", description="test_1", cache_ttl=600)

amt_2 = AnalysisModuleType(name="test_2", description="test_2", cache_ttl=600)

amt_1_v2 = AnalysisModuleType(name="test_2", description="test_2", version="1.0.2", cache_ttl=600)

amt_no_cache = AnalysisModuleType(name="test_no_cache", description="test_no_cache2")

amt_fast_expire_cache = AnalysisModuleType(
    name="test_fast_expire_cache", description="test_fast_expire_cache", cache_ttl=0
)

amt_extended_version_1 = AnalysisModuleType(
    name="test_extended_version",
    description="test_extended_version",
    cache_ttl=600,
    extended_version=["yara_rules:v1.0.0"],
)

amt_extended_version_2 = AnalysisModuleType(
    name="test_extended_version",
    description="test_extended_version",
    cache_ttl=600,
    extended_version=["yara_rules:v1.0.1"],
)

amt_multiple_cache_keys_1 = AnalysisModuleType(
    name="test_multiple_cache_keys",
    description="test_multiple_cache_keys",
    cache_ttl=600,
    extended_version=["key_a", "key_b"],
)

amt_multiple_cache_keys_2 = AnalysisModuleType(
    name="test_multiple_cache_keys",
    description="test_multiple_cache_keys",
    cache_ttl=600,
    extended_version=["key_b", "key_a"],
)

TEST_1 = "test_1"
TEST_2 = "test_2"

observable_1 = Observable("test", TEST_1)
observable_2 = Observable("test", TEST_2)
observable_1_with_time = Observable("test", TEST_2, time=datetime.datetime.now())


@pytest.mark.unit
@pytest.mark.parametrize(
    "o_left, amt_left, o_right, amt_right, expected",
    [
        # same observable and amt
        (observable_1, amt_1, observable_1, amt_1, True),
        # different observable same amt
        (observable_1, amt_1, observable_2, amt_1, False),
        # same observable but with different times same amt
        (observable_1, amt_1, observable_1_with_time, amt_1, False),
        # same observable but with different amt
        (observable_1, amt_1, observable_1, amt_2, False),
        # same observable same amt but different amt version
        (observable_1, amt_1, observable_1, amt_1_v2, False),
        # same observable same amt same additional cache keys
        (observable_1, amt_extended_version_1, observable_1, amt_extended_version_1, True),
        # same observable same amt different additional cache keys
        (observable_1, amt_extended_version_1, observable_1, amt_extended_version_2, False),
        # order of cache keys should not matter
        (observable_1, amt_multiple_cache_keys_1, observable_1, amt_multiple_cache_keys_2, True),
    ],
)
def test_generate_cache_key(o_left, amt_left, o_right, amt_right, expected):
    assert (generate_cache_key(o_left, amt_left) == generate_cache_key(o_right, amt_right)) == expected


@pytest.mark.unit
def test_generate_cache_key_no_cache():
    # if the cache_ttl is 0 (the default) then this function returns a 0
    assert generate_cache_key(observable_1, amt_no_cache) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "observable, amt",
    [
        (observable_1, None),
        (None, amt_1),
        (None, None),
    ],
)
def test_generate_cache_invalid_parameters(observable, amt):
    assert generate_cache_key(observable, amt) is None


@pytest.mark.integration
def test_cache_analysis_result():
    root = RootAnalysis()
    observable = root.add_observable("type", "value")
    request = observable.create_analysis_request(amt_1)
    request.initialize_result()
    analysis = request.modified_observable.add_analysis(type=amt_1)

    assert cache_analysis_result(request) is not None
    assert get_cached_analysis_result(observable, amt_1) == request


@pytest.mark.integration
def test_nocache_analysis():
    root = RootAnalysis()
    observable = root.add_observable("type", "value")
    request = observable.create_analysis_request(amt_no_cache)
    request.initialize_result()
    analysis = request.modified_observable.add_analysis(type=amt_no_cache)

    assert cache_analysis_result(request) is None
    assert get_cached_analysis_result(observable, amt_no_cache) is None


@pytest.mark.integration
def test_cache_expiration():
    root = RootAnalysis()
    observable = root.add_observable("type", "value")
    request = observable.create_analysis_request(amt_fast_expire_cache)
    request.initialize_result()
    analysis = request.modified_observable.add_analysis(type=amt_fast_expire_cache)

    assert cache_analysis_result(request) is not None
    # should have expired right away
    assert get_cached_analysis_result(observable, amt_fast_expire_cache) is None


@pytest.mark.integration
def test_delete_expired_cached_analysis_results():
    register_analysis_module_type(amt_fast_expire_cache)

    root = RootAnalysis()
    observable = root.add_observable("type", "value")
    root.submit()

    request = get_next_analysis_request("owner", amt_fast_expire_cache, 0)
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt_fast_expire_cache)
    request.submit()

    # should have one expired cache result
    assert get_total_cache_size() == 1
    delete_expired_cached_analysis_results()
    # and none after we clear them all out
    assert get_total_cache_size() == 0


@pytest.mark.integration
def test_delete_cached_analysis_results_by_module_type():
    register_analysis_module_type(amt_1)

    root = RootAnalysis()
    observable = root.add_observable("type", "value")
    root.submit()

    request = get_next_analysis_request("owner", amt_1, 0)
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt_1)
    request.submit()

    # should have one cache result
    assert get_total_cache_size(amt_1) == 1
    delete_cached_analysis_results_by_module_type(amt_1)
    # and none after we clear them all out
    assert get_total_cache_size(amt_1) == 0
