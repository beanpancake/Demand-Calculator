import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from webapp.server import parse_load


def test_negative_values_return_zero():
    assert parse_load("-50", 240) == 0


def test_amp_to_watt_conversion():
    assert parse_load("50", 240) == 50 * 240 * 0.8


def test_blank_returns_zero():
    assert parse_load("   ", 240) == 0


def test_values_over_500_treated_as_watts():
    assert parse_load("600", 240) == 600


def test_value_500_treated_as_amps():
    assert parse_load("500", 240) == 500 * 240 * 0.8

