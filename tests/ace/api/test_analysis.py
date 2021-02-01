# vim: ts=4:sw=4:et:cc=120
#

from ace.api.analysis import RootAnalysis, AnalysisModuleType

import pytest


@pytest.mark.unit
def test_serialization():

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    amt = AnalysisModuleType("test", "")
    analysis = observable.add_analysis(type=amt, details={"hello": "world"})

    deserialized = RootAnalysis.from_json(root.to_json())
    assert root == deserialized
    observable == deserialized.get_observable(observable)
    analysis == deserialized.get_observable(observable).get_analysis(amt)
    analysis.details == deserialized.get_observable(observable).get_analysis(amt).details
