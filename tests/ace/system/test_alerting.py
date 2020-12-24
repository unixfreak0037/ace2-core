# vim: ts=4:sw=4:et:cc=120

import pytest

from ace.analysis import RootAnalysis, AnalysisModuleType
from ace.system.analysis_module import register_analysis_module_type
from ace.system.alerting import track_alert, get_alert
from ace.system.inbound import process_analysis_request
from ace.system.work_queue import get_next_analysis_request


@pytest.mark.unit
def test_alert_tracking():
    root = RootAnalysis()
    assert track_alert(RootAnalysis())


@pytest.mark.integration
def test_root_detection():
    root = RootAnalysis()
    root.add_detection_point("test")
    process_analysis_request(root.create_analysis_request())
    assert get_alert(root)


@pytest.mark.integration
def test_observable_detection():
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    observable.add_detection_point("test")
    process_analysis_request(root.create_analysis_request())
    assert get_alert(root)


@pytest.mark.integration
def test_analysis_detection():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    analysis.add_detection_point("test")
    process_analysis_request(root.create_analysis_request())
    assert get_alert(root)


@pytest.mark.integration
def test_no_detection():
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    process_analysis_request(root.create_analysis_request())
    assert get_alert(root) is None


@pytest.mark.integration
def test_analysis_result_detection():
    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    process_analysis_request(root.create_analysis_request())
    assert get_alert(root) is None
    request = get_next_analysis_request("test", amt, 0)
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt).add_detection_point("test")
    process_analysis_request(request)
    assert get_alert(root)
