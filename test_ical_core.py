#!/usr/bin/env python3
"""Tests for course schedule helpers."""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import ical_core as core

PARIS = ZoneInfo("Europe/Paris")


def make_settings(slots: list[core.Slot]) -> core.Settings:
    course = core.Course(
        code="UM4PYOIP",
        name="Insertion professionnelle",
        label="OIP",
        slots=slots,
    )
    return core.Settings(
        output=core.ROOT / "out.txt",
        min_interval_hours=0,
        calendar_remote_id="https://example.test/basic.ics",
        calendar_display="Test",
        include_exams=False,
        groups=[],
        courses=[course],
        vacation_weeks=[],
    )


class GroupNumberTests(unittest.TestCase):
    def test_matches_high_group_numbers(self) -> None:
        self.assertEqual(core.group_number("gr8"), 8)
        self.assertEqual(core.group_number("TD gr6"), 6)


class DefaultRoomTests(unittest.TestCase):
    def test_matches_group_slot(self) -> None:
        settings = make_settings(
            [
                core.Slot("je", "13:45", "15:45", "gr6", "salle 105 couloir 55-65"),
            ]
        )
        occurrence = core.Occurrence(
            start=datetime(2026, 9, 17, 13, 45, tzinfo=PARIS),
            end=datetime(2026, 9, 17, 15, 45, tzinfo=PARIS),
            code="UM4PYOIP",
            summary="UM4PYOIP gr6",
            session="gr6",
            room="salle 999",
            series="series-1",
        )
        self.assertEqual(
            core.default_room(occurrence, settings),
            "salle 105 couloir 55-65",
        )


if __name__ == "__main__":
    unittest.main()
