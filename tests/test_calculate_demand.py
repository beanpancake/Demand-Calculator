import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from calculator.core import calculate_demand


def test_calculate_demand_main_only():
    inputs, results, debug = calculate_demand(
        voltage=240,
        area_main=100,
        range_main_w=12000,
        heat_main_w=15000,
        ac_main_w=0,
        evse_main_w=0,
        interlocked=False,
        add_main_list_w=[2000, 3000],
        tankless_main_w=0,
        sps_main_all=[],
    )
    assert results["Final Calculated Load (W)"] == "27000"
    # ensure debug contains basic information
    assert any("Basic load" in line for line in debug)
