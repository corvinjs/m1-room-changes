"""Shared iCalendar parsing and course schedule logic."""

from __future__ import annotations

import re
import tomllib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr

ROOT = Path(__file__).resolve().parent
PARIS = ZoneInfo("Europe/Paris")
WEEKDAYS_FR = ("lu", "ma", "me", "je", "ve", "sa", "di")
SERIES_SUFFIX = re.compile(r"(?:_R\d{8}T\d{6}(?:Z)?|_\d{8}T\d{6}(?:Z)?)$")
CANCEL_PREFIX = re.compile(r"^\s*(canceled|cancelled|annul[ée]e?)\s*:?\s*", re.I)


@dataclass
class Slot:
    day: str
    start: str
    end: str
    session: str
    room: str


@dataclass
class Course:
    code: str
    name: str
    label: str
    slots: list[Slot]
    opaque: bool = False


@dataclass
class VacationWeek:
    start: str  # ISO date (Monday) of the vacation week


@dataclass
class Settings:
    output: Path
    min_interval_hours: float
    calendar_remote_id: str
    calendar_display: str
    include_exams: bool
    groups: list[int]
    courses: list[Course]
    vacation_weeks: list[VacationWeek]

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(c.code for c in self.courses)

    def course(self, code: str) -> Course | None:
        for item in self.courses:
            if item.code == code:
                return item
        return None


def load_settings(path: Path = ROOT / "settings.toml") -> Settings:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    courses = []
    for item in raw.get("courses", []):
        slots = [
            Slot(
                day=s["day"].lower()[:2],
                start=s["start"],
                end=s.get("end", ""),
                session=s.get("session", ""),
                room=(s.get("room") or "").strip(),
            )
            for s in item.get("slots", [])
        ]
        courses.append(
            Course(
                code=item["code"],
                name=item.get("name", item["code"]),
                label=item.get("label", item["code"]),
                slots=slots,
                opaque=bool(item.get("opaque", False)),
            )
        )
    vacation_weeks = [
        VacationWeek(start=item["start"])
        for item in raw.get("vacation_weeks", [])
    ]
    return Settings(
        output=Path(raw.get("output", "static-site-output.txt")).expanduser(),
        min_interval_hours=float(raw.get("min_interval_hours", 0)),
        calendar_remote_id=raw.get(
            "calendar_remote_id",
            "https://calendar.google.com/calendar/ical/"
            "masterm1physique%40gmail.com/public/basic.ics",
        ),
        calendar_display=raw.get("calendar_display", "Sorbonne PHYSIQUE M1"),
        include_exams=bool(raw.get("include_exams", False)),
        groups=[int(g) for g in raw.get("groups", [])],
        courses=courses,
        vacation_weeks=vacation_weeks,
    )


def unfold(ics: str) -> str:
    return re.sub(r"\r?\n[ \t]", "", ics)


def unescape(value: str) -> str:
    return (
        value.replace("\\\\", "\\")
        .replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .strip()
        .strip("\r")
    )


def parse_props(vevent: str) -> dict[str, list[tuple[dict[str, str], str]]]:
    props: dict[str, list[tuple[dict[str, str], str]]] = defaultdict(list)
    for raw in vevent.splitlines():
        line = raw.rstrip("\r")
        if not line or ":" not in line:
            continue
        nameparams, value = line.split(":", 1)
        parts = nameparams.split(";")
        name = parts[0].upper()
        params = {}
        for part in parts[1:]:
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.upper()] = v
        props[name].append((params, value))
    return props


def first(props, name) -> tuple[dict[str, str], str] | None:
    items = props.get(name)
    return items[0] if items else None


def parse_dt(params: dict[str, str], value: str) -> datetime:
    value = value.strip()
    tzid = params.get("TZID")
    if value.endswith("Z"):
        from datetime import timezone

        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt.astimezone(PARIS)
    if "T" in value:
        dt = datetime.strptime(value, "%Y%m%dT%H%M%S")
    else:
        dt = datetime.strptime(value, "%Y%m%d")
    tz = ZoneInfo(tzid) if tzid else PARIS
    return dt.replace(tzinfo=tz).astimezone(PARIS)


def parse_dt_list(params: dict[str, str], value: str) -> list[datetime]:
    return [parse_dt(params, chunk) for chunk in value.split(",") if chunk.strip()]


def extract_vevents(ics: str) -> list[str]:
    return [
        match.group(0)
        for match in re.finditer(
            r"BEGIN:VEVENT\r?\n(.*?)END:VEVENT", ics, flags=re.S | re.I
        )
    ]


def course_code(summary: str, codes: tuple[str, ...]) -> str | None:
    for code in codes:
        if code in summary:
            return code
    return None


def session_label(summary: str, code: str) -> str:
    rest = summary.replace(code, "", 1).strip(" -")
    rest = re.sub(r"^(MQ-CE|MQ CE|PhyStat ACE|Plasmas)\s*", "", rest)
    return rest or "Cours"


def series_id(remote_id: str) -> str:
    return SERIES_SUFFIX.sub("", remote_id)


@dataclass
class EventDef:
    remote_id: str
    series: str
    summary: str
    code: str
    location: str
    dtstart: datetime
    dtend: datetime
    rrule: str | None
    rdates: list[datetime]
    exdates: list[datetime]
    recurrence_id: datetime | None
    is_exam: bool
    cancelled: bool


@dataclass
class Occurrence:
    start: datetime
    end: datetime
    code: str
    summary: str
    session: str
    room: str
    series: str
    cancelled: bool = False
    usual_room: str = ""
    note: str = ""
    opaque: bool = False
    runs: list[tuple[datetime, datetime, str]] = field(default_factory=list)


def expand(events: list[EventDef], include_exams: bool) -> list[Occurrence]:
    exceptions: dict[tuple[str, datetime], EventDef] = {}
    masters: list[EventDef] = []
    for ev in events:
        if ev.is_exam and not include_exams:
            continue
        if ev.recurrence_id is not None:
            exceptions[(ev.series, ev.recurrence_id)] = ev
        else:
            masters.append(ev)

    occs: list[Occurrence] = []

    def add_occ(ev: EventDef, start: datetime, cancelled: bool | None = None) -> None:
        flag = ev.cancelled if cancelled is None else cancelled
        occs.append(
            Occurrence(
                start=start,
                end=start + (ev.dtend - ev.dtstart),
                code=ev.code,
                summary=ev.summary,
                session=session_label(ev.summary, ev.code),
                room="" if flag else ev.location,
                series=ev.series,
                cancelled=flag,
            )
        )

    for ev in masters:
        starts = [ev.dtstart]
        if ev.rrule:
            try:
                starts = list(rrulestr(ev.rrule, dtstart=ev.dtstart))
            except ValueError:
                starts = [ev.dtstart]
        starts.extend(ev.rdates)
        skip = {d.astimezone(PARIS) for d in ev.exdates}
        seen: set[datetime] = set()
        for start in starts:
            start = start.astimezone(PARIS)
            if start in seen:
                continue
            seen.add(start)
            ex = exceptions.get((ev.series, start))
            if ex is not None:
                add_occ(ex, ex.dtstart)
            elif start in skip or ev.cancelled:
                add_occ(ev, start, cancelled=True)
            else:
                add_occ(ev, start)
        for ex_start in skip:
            if ex_start not in seen:
                seen.add(ex_start)
                ex = exceptions.get((ev.series, ex_start))
                if ex is not None:
                    add_occ(ex, ex.dtstart)
                else:
                    add_occ(ev, ex_start, cancelled=True)

    for (series, _rec_id), ev in exceptions.items():
        if not any(o.series == series and o.start == ev.dtstart for o in occs):
            add_occ(ev, ev.dtstart)

    occs.sort(key=lambda o: (o.start, o.code, o.session))
    return occs


def academic_year(dt: datetime) -> int:
    return dt.year if dt.month >= 8 else dt.year - 1


def slot_key(o: Occurrence) -> tuple:
    return (
        academic_year(o.start),
        o.code,
        o.summary,
        o.start.weekday(),
        o.start.strftime("%H:%M"),
    )


def group_number(session: str) -> int | None:
    m = re.search(r"gr\s*(\d+)", session, re.I)
    return int(m.group(1)) if m else None


def keep_occurrence(o: Occurrence, settings: Settings, group_arg: str | None) -> bool:
    if group_arg:
        needle = f"gr{group_arg}"
        return needle in o.summary.lower() or "cours" in o.session.lower()
    if not settings.groups:
        return True
    n = group_number(o.session)
    if n is None:
        return True
    return n in settings.groups


def default_room(o: Occurrence, settings: Settings) -> str | None:
    course = settings.course(o.code)
    if not course:
        return None
    day = WEEKDAYS_FR[o.start.weekday()]
    start = o.start.strftime("%H:%M")
    session = o.session.lower()
    for slot in course.slots:
        if slot.day != day or slot.start != start:
            continue
        want = slot.session.lower()
        if not want or want == session or want in session or session in want:
            return slot.room
    return None


def annotate(occs: list[Occurrence], settings: Settings) -> None:
    by_slot: dict[tuple, list[Occurrence]] = defaultdict(list)
    for o in occs:
        by_slot[slot_key(o)].append(o)

    for group in by_slot.values():
        group.sort(key=lambda o: o.start)
        runs: list[tuple[datetime, datetime, str]] = []
        for o in group:
            room = "CANCELLED" if o.cancelled else o.room
            if runs and runs[-1][2] == room and o.start.date() <= (
                runs[-1][1].date() + timedelta(days=8)
            ):
                runs[-1] = (runs[-1][0], o.start, room)
            else:
                runs.append((o.start, o.start, room))
        inferred = next((r for _, _, r in runs if r and r != "CANCELLED"), "")
        for o in group:
            configured = default_room(o, settings)
            course = settings.course(o.code)
            o.usual_room = inferred if configured is None else configured
            o.opaque = course.opaque if course else False
            o.runs = runs
            if o.cancelled:
                o.note = "cancelled"
            elif not o.room:
                o.note = "no room" if o.usual_room else ""
            elif o.usual_room and o.room != o.usual_room:
                o.note = f"CHANGE (usual: {o.usual_room})"
            elif configured is None and inferred and o.room == inferred:
                run_idx = next(
                    i
                    for i, (a, b, room) in enumerate(runs)
                    if room == o.room and a <= o.start <= b
                )
                prev_room = runs[run_idx - 1][2] if run_idx else None
                if configured is None and run_idx > 0 and not prev_room:
                    o.note = "room assigned"
