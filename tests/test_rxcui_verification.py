"""Tests for services/rxcui_verification.py -- RxNav is always mocked."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from services.rxcui_verification import (
    STATUS_ERROR,
    STATUS_MATCH,
    STATUS_NAME_MISMATCH,
    STATUS_NOT_FOUND,
    STATUS_NOT_INGREDIENT,
    verify_rxcuis,
)


def _session(payload=None, error=None):
    response = Mock()
    response.json.return_value = payload
    session = Mock()
    session.get.side_effect = error if error else None
    session.get.return_value = response
    return session


def _verify_one(session, name="warfarin", rxcui="11289"):
    (check,) = verify_rxcuis({name: rxcui}, session, delay=0)
    return check


def test_matching_ingredient_passes():
    check = _verify_one(_session({"properties": {"name": "Warfarin", "tty": "IN"}}))
    assert check.status == STATUS_MATCH and check.passed


def test_name_mismatch_is_reported_with_rxnav_name():
    check = _verify_one(_session({"properties": {"name": "Aspirin", "tty": "IN"}}))
    assert check.status == STATUS_NAME_MISMATCH and check.rxnav_name == "Aspirin"
    assert not check.passed


def test_non_ingredient_term_type_fails():
    check = _verify_one(_session({"properties": {"name": "warfarin 5 MG Oral Tablet", "tty": "SCD"}}))
    assert check.status == STATUS_NOT_INGREDIENT


def test_empty_properties_means_not_found():
    assert _verify_one(_session({})).status == STATUS_NOT_FOUND
    assert _verify_one(_session({"properties": None})).status == STATUS_NOT_FOUND


def test_network_error_is_reported_not_raised():
    check = _verify_one(_session(error=requests.ConnectionError("offline")))
    assert check.status == STATUS_ERROR and "offline" in check.detail


def test_invalid_json_is_reported_not_raised():
    response = Mock()
    response.json.side_effect = ValueError("bad json")
    session = Mock()
    session.get.return_value = response
    assert _verify_one(session).status == STATUS_ERROR


def test_every_entry_is_checked_in_sorted_order():
    session = _session({"properties": {"name": "x", "tty": "IN"}})
    results = verify_rxcuis({"b": "2", "a": "1"}, session, delay=0)
    assert [r.canonical_name for r in results] == ["a", "b"]
    assert session.get.call_count == 2
