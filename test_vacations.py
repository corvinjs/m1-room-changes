import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import build_static_site
import ical_core as core


class VacationTest(unittest.TestCase):
    def test_week_start_and_vacation_matching(self):
        self.assertEqual(build_static_site.week_start(date(2026, 10, 28)), date(2026, 10, 26))
        self.assertTrue(build_static_site.is_vacation(date(2026, 10, 30), (date(2026, 10, 26),)))
        self.assertFalse(build_static_site.is_vacation(date(2026, 11, 2), (date(2026, 10, 26),)))

    def test_vacation_week_hides_courses_and_is_published(self):
        settings = core.Settings(
            output=Path("test-output.html"),
            min_interval_hours=0,
            calendar_remote_id="",
            calendar_display="",
            include_exams=False,
            groups=[],
            vacation_weeks=(date(2026, 10, 26),),
            courses=[
                core.Course(
                    code="UM4PY101",
                    name="Mécanique quantique",
                    label="MQ",
                    slots=[],
                )
            ],
        )
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;TZID=Europe/Paris:20261026T090000
DTEND;TZID=Europe/Paris:20261026T100000
UID:test-vacation
SUMMARY:UM4PY101 Cours
LOCATION:salle 101
END:VEVENT
END:VCALENDAR
"""
        with patch(
            "build_static_site.datetime",
            wraps=datetime,
        ) as clock:
            clock.now.return_value = datetime(2026, 9, 10, tzinfo=core.PARIS)
            payload = build_static_site.build_payload(ics, settings)

        self.assertEqual(payload["events"], [])
        self.assertEqual(payload["vacations"], [{
            "start": "2026-10-26",
            "end": "2026-11-02",
            "label": "Vacances",
        }])


if __name__ == "__main__":
    unittest.main()
