#!/usr/bin/env python3
"""Tests for static site build and change detection."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import build_static_site as site


class PayloadDigestTests(unittest.TestCase):
    def test_ignores_generated_at(self) -> None:
        payload_a = {
            "generatedAt": "2026-01-01T10:00:00+01:00",
            "courses": [{"code": "UM4PY101", "name": "Test", "slots": []}],
            "events": [],
            "vacationWeeks": [],
        }
        payload_b = dict(payload_a)
        payload_b["generatedAt"] = "2026-09-10T12:00:00+02:00"
        self.assertEqual(site.payload_digest(payload_a), site.payload_digest(payload_b))

    def test_detects_event_change(self) -> None:
        base = {
            "generatedAt": "2026-01-01T10:00:00+01:00",
            "courses": [],
            "events": [{"code": "UM4PY101", "room": "salle 101"}],
            "vacationWeeks": [],
        }
        changed = dict(base)
        changed["events"] = [{"code": "UM4PY101", "room": "salle 202"}]
        self.assertNotEqual(site.payload_digest(base), site.payload_digest(changed))


class DataUnchangedTests(unittest.TestCase):
    def test_matches_when_only_generated_at_differs(self) -> None:
        payload = {
            "generatedAt": "2026-01-01T10:00:00+01:00",
            "courses": [],
            "events": [],
            "vacationWeeks": [],
        }
        old_html = site.render(payload)
        payload["generatedAt"] = "2026-09-10T12:00:00+02:00"
        new_html = site.render(payload)
        with tempfile.TemporaryDirectory() as tmpdir:
            compare_with = Path(tmpdir) / "index.html"
            compare_with.write_text(old_html, encoding="utf-8")
            self.assertTrue(site.data_unchanged(compare_with, new_html))

    def test_differs_when_events_change(self) -> None:
        payload = {
            "generatedAt": "2026-01-01T10:00:00+01:00",
            "courses": [],
            "events": [{"code": "UM4PY101", "room": "salle 101"}],
            "vacationWeeks": [],
        }
        old_html = site.render(payload)
        payload["events"] = [{"code": "UM4PY101", "room": "salle 202"}]
        new_html = site.render(payload)
        with tempfile.TemporaryDirectory() as tmpdir:
            compare_with = Path(tmpdir) / "index.html"
            compare_with.write_text(old_html, encoding="utf-8")
            self.assertFalse(site.data_unchanged(compare_with, new_html))


class ExtractPayloadTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        payload = {
            "generatedAt": "2026-01-01T10:00:00+01:00",
            "courses": [{"code": "X", "name": "Y", "slots": []}],
            "events": [],
            "vacationWeeks": [{"start": "2026-10-26"}],
        }
        html = site.render(payload)
        extracted = site.extract_payload_from_html(html)
        self.assertEqual(extracted["courses"], payload["courses"])
        self.assertEqual(extracted["vacationWeeks"], payload["vacationWeeks"])


if __name__ == "__main__":
    unittest.main()
