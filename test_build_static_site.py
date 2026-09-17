#!/usr/bin/env python3
"""Tests for static site build and change detection."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import build_static_site as site
import ical_core as core


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


class BuildPayloadWindowTests(unittest.TestCase):
    def test_includes_ended_events_from_current_week(self) -> None:
        settings = core.Settings(
            output=Path("out.txt"),
            min_interval_hours=0,
            calendar_remote_id="",
            calendar_display="",
            include_exams=False,
            groups=[],
            courses=[
                core.Course(
                    code="UM4PY101",
                    name="Test",
                    label="Test",
                    slots=[],
                )
            ],
            vacation_weeks=[],
        )
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID=current-week
SUMMARY:UM4PY101 Cours
DTSTART;TZID=Europe/Paris:20260916T100000
DTEND;TZID=Europe/Paris:20260916T120000
END:VEVENT
BEGIN:VEVENT
UID:previous-week
SUMMARY:UM4PY101 Cours
DTSTART;TZID=Europe/Paris:20260913T100000
DTEND;TZID=Europe/Paris:20260913T120000
END:VEVENT
END:VCALENDAR
"""
        fixed_now = datetime(2026, 9, 17, 9, tzinfo=ZoneInfo("Europe/Paris"))
        with patch("build_static_site.datetime") as datetime_class:
            datetime_class.now.return_value = fixed_now
            payload = site.build_payload(ics, settings)

        self.assertEqual([event["start"] for event in payload["events"]], [
            "2026-09-16T10:00:00+02:00",
        ])


if __name__ == "__main__":
    unittest.main()
