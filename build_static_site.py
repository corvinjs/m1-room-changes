#!/usr/bin/env python3
"""Build the static m1-room-changes page from a downloaded iCalendar feed."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import ical_core as core

ROOT = Path(__file__).resolve().parent
SETTINGS = ROOT / "settings.toml"
TEMPLATE = ROOT / "template.html"


def parse_ics(ics: str, settings: core.Settings) -> list[core.EventDef]:
    events: list[core.EventDef] = []
    for block in core.extract_vevents(core.unfold(ics)):
        props = core.parse_props(block)
        summary_p = core.first(props, "SUMMARY")
        start_p = core.first(props, "DTSTART")
        end_p = core.first(props, "DTEND")
        if not (summary_p and start_p and end_p):
            continue

        summary = core.unescape(summary_p[1])
        cancelled = bool(core.CANCEL_PREFIX.match(summary))
        summary = core.CANCEL_PREFIX.sub("", summary)
        code = core.course_code(summary, settings.codes)
        if not code:
            continue

        status_p = core.first(props, "STATUS")
        if status_p and "CANCEL" in status_p[1].upper():
            cancelled = True
        location_p = core.first(props, "LOCATION")
        recurrence_p = core.first(props, "RECURRENCE-ID")
        rrule_p = core.first(props, "RRULE")
        rdates = [
            date
            for params, value in props.get("RDATE", [])
            for date in core.parse_dt_list(params, value)
            if date.year >= 2020
        ]
        exdates = [
            date
            for params, value in props.get("EXDATE", [])
            for date in core.parse_dt_list(params, value)
        ]
        rrule = rrule_p[1].strip().rstrip("\r") if rrule_p else None
        if rrule:
            until_match = re.search(r"UNTIL=([^;]+)", rrule)
            if until_match:
                raw_until = until_match.group(1)
                until = (
                    core.parse_dt({}, raw_until)
                    if raw_until.endswith("Z")
                    else core.parse_dt({"TZID": "Europe/Paris"}, raw_until)
                )
                if until < core.parse_dt(*start_p):
                    rrule = None

        remote_id_p = core.first(props, "UID")
        remote_id = core.unescape(remote_id_p[1]) if remote_id_p else ""
        events.append(
            core.EventDef(
                remote_id=remote_id,
                series=core.series_id(remote_id),
                summary=summary,
                code=code,
                location=core.unescape(location_p[1]) if location_p else "",
                dtstart=core.parse_dt(*start_p),
                dtend=core.parse_dt(*end_p),
                rrule=rrule,
                rdates=rdates,
                exdates=exdates,
                recurrence_id=core.parse_dt(*recurrence_p) if recurrence_p else None,
                is_exam=bool(re.search(r"\b(EXAMEN|CC\d*)\b", summary, re.I)),
                cancelled=cancelled,
            )
        )
    return events


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def is_vacation(day: date, vacation_weeks: tuple[date, ...]) -> bool:
    return week_start(day) in vacation_weeks


def canonicalize_ics(ics: str) -> str:
    """Return a stable representation of an iCalendar feed.

    The feed is semantically insensitive to VEVENT order, but providers can
    return those blocks in a different order on each request.  Normalize line
    endings and sort the blocks so the checked-in snapshot only changes when
    the calendar data changes.
    """
    text = ics.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(re.finditer(r"BEGIN:VEVENT\n.*?END:VEVENT\n?", text, re.S | re.I))
    if not matches:
        return text.rstrip("\n") + "\n"

    def sort_key(block: str) -> tuple[str, str, str]:
        props = core.parse_props(core.unfold(block))
        uid = core.first(props, "UID")
        recurrence_id = core.first(props, "RECURRENCE-ID")
        return (
            uid[1] if uid else "",
            recurrence_id[1] if recurrence_id else "",
            block,
        )

    events = sorted((match.group(0) for match in matches), key=sort_key)
    prefix = text[: matches[0].start()]
    suffix = text[matches[-1].end() :]
    return prefix + "".join(events) + suffix.lstrip("\n")


def build_payload(ics: str, settings: core.Settings) -> dict:
    occurrences = core.expand(parse_ics(ics, settings), settings.include_exams)
    occurrences = [o for o in occurrences if core.keep_occurrence(o, settings, None)]
    occurrences = [
        o for o in occurrences
        if not is_vacation(o.start.date(), settings.vacation_weeks)
    ]
    core.annotate(occurrences, settings)
    now = datetime.now(core.PARIS)
    end = now + timedelta(days=120)
    vacation_events = [
        {
            "start": week.isoformat(),
            "end": (week + timedelta(days=7)).isoformat(),
            "vacation": True,
        }
        for week in settings.vacation_weeks
        if week_start(week) == week and week + timedelta(days=7) > now.date() and week < end.date()
    ]
    courses = [
        {
            "code": course.code,
            "name": course.name,
            "label": course.label,
            "opaque": course.opaque,
            "slots": [
                {
                    "day": slot.day,
                    "start": slot.start,
                    "end": slot.end,
                    "session": slot.session,
                    "room": slot.room,
                }
                for slot in course.slots
            ],
        }
        for course in settings.courses
    ]
    events = [
        {
            "start": occurrence.start.isoformat(),
            "end": occurrence.end.isoformat(),
            "code": occurrence.code,
            "summary": occurrence.summary,
            "session": occurrence.session,
            "room": occurrence.room,
            "usualRoom": occurrence.usual_room,
            "note": occurrence.note,
            "cancelled": occurrence.cancelled,
            "opaque": occurrence.opaque,
        }
        for occurrence in occurrences
        if occurrence.end > now and occurrence.start < end
    ]
    events.extend(vacation_events)
    events.sort(key=lambda event: event["start"])
    return {
        "generatedAt": now.isoformat(),
        "courses": courses,
        "events": events,
    }


DATA_RE = re.compile(r"const DATA = (\{.*?\});\n", re.S)


def semantic_payload(payload: dict) -> dict:
    """Return the page data without volatile metadata."""
    return {"courses": payload["courses"], "events": payload["events"]}


def payload_digest(payload: dict) -> str:
    blob = json.dumps(
        semantic_payload(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def extract_payload_from_html(html: str) -> dict:
    match = DATA_RE.search(html)
    if not match:
        raise ValueError("no embedded DATA payload found")
    return json.loads(match.group(1))


def _diff_has_substantive_changes(diff_text: str) -> bool:
    for line in diff_text.splitlines():
        if not line or line[0] not in "+-":
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if "generatedAt" in line:
            continue
        return True
    return False


def html_diff_is_cosmetic_only(old_html: str, new_html: str) -> bool:
    """True when a git diff only touches the generatedAt timestamp."""
    if old_html == new_html:
        return True
    with tempfile.TemporaryDirectory() as tmpdir:
        old_path = Path(tmpdir) / "old.html"
        new_path = Path(tmpdir) / "new.html"
        old_path.write_text(old_html, encoding="utf-8")
        new_path.write_text(new_html, encoding="utf-8")
        result = subprocess.run(
            ["git", "diff", "--no-index", "-U0", "--", str(old_path), str(new_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode == 0:
        return True
    return not _diff_has_substantive_changes(result.stdout)


def data_unchanged(
    compare_with: Path,
    candidate_html: str,
) -> bool:
    if not compare_with.is_file():
        return False
    return html_diff_is_cosmetic_only(
        compare_with.read_text(encoding="utf-8"),
        candidate_html,
    )


def render(payload: dict) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    return template.replace("__DATA_JSON__", data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ics", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument(
        "--canonical-ics",
        type=Path,
        help="write a stable, normalized copy of the input feed",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=SETTINGS,
        help="static-site course configuration",
    )
    parser.add_argument(
        "--compare-with",
        type=Path,
        help="existing index.html to compare rendered data against",
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        help="pre-built HTML to compare with --compare-with",
    )
    parser.add_argument(
        "--data-unchanged",
        action="store_true",
        help="exit 0 when git diff vs --compare-with only changes generatedAt",
    )
    args = parser.parse_args()
    ics = canonicalize_ics(args.ics.read_text(encoding="utf-8"))
    if args.canonical_ics:
        args.canonical_ics.write_text(ics, encoding="utf-8")
    settings = core.load_settings(args.config)
    if args.data_unchanged:
        if not args.compare_with:
            parser.error("--data-unchanged requires --compare-with")
        if args.candidate:
            candidate_html = args.candidate.read_text(encoding="utf-8")
        elif args.output:
            candidate_html = render(build_payload(ics, settings))
        else:
            parser.error("--data-unchanged requires --candidate or output")
        raise SystemExit(0 if data_unchanged(args.compare_with, candidate_html) else 1)
    if not args.output:
        if not args.canonical_ics:
            parser.error("output is required unless --canonical-ics or --data-unchanged is given")
        return
    args.output.write_text(
        render(build_payload(ics, settings)),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
