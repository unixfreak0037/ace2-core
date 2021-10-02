import datetime

from ace.analysis import RootAnalysis, AnalysisModuleType
from ace.cli.analysis import display_analysis

import pytest
import pytz


@pytest.mark.unit
def test_display_analysis(capsys):
    root = RootAnalysis(desc="Test Root")
    ipv4_observable = root.add_observable("ipv4", "1.2.3.4")
    ipv4_analysis_type = AnalysisModuleType(name="IPv4 Analyzer", description="Analyzes ipv4.")
    ipv4_analysis = ipv4_observable.add_analysis(type=ipv4_analysis_type, summary="Adversary infrastructure.")
    campaign_observable = ipv4_analysis.add_observable("campaign", "x795")
    campaign_observable.add_tag("apt")
    proxy_analysis_type = AnalysisModuleType(name="Proxy Analyzer", description="Proxy request lookup.")
    proxy_analysis = ipv4_observable.add_analysis(type=proxy_analysis_type, summary="Found 1 user.")
    user_observable = proxy_analysis.add_observable(
        "user", "johnclicker", datetime.datetime(2021, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
    )
    user_observable.add_detection_point("clicker")
    user_observable.add_directive("SCOLD_EMPLOYEE")
    display_analysis(root)
    captured = capsys.readouterr()
    print(captured.out)

    # NOTE below that some of the lines have an extra space at the end
    expected_output = """Test Root
 * ipv4:1.2.3.4
\tIPv4 Analyzer: Adversary infrastructure.
\t * campaign:x795 [ apt ] 
\tProxy Analyzer: Found 1 user.
\t * <!> user:johnclicker @ 2021-01-01 00:00:00 +0000 { SCOLD_EMPLOYEE } 
1 TAGS
* apt
1 DETECTIONS FOUND (marked with <!> above)
* DetectionPoint(clicker)
"""

    assert captured.out == expected_output
