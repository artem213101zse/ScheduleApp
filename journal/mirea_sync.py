"""Download and parse official MIREA Excel timetable into journal lessons."""

from __future__ import annotations

import json
import re
import ssl
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Group, JournalSettings, Lesson, StudentProfile, Subject, Teacher

GROUP_RE = re.compile(r"([А-Яа-яA-Za-z]{4}-\d{2}-\d{2})")
HREF_RE = re.compile(
    r"""(?:href\s*=\s*["']([^"']+\.(?:xlsx?|XLSX?))["']|(https?://[^\s"'<>]+\.(?:xlsx?|XLSX?))|(/upload/[^\s"'<>]+\.(?:xlsx?|XLSX?)))""",
    re.I,
)
SCHEDULE_OF_BASES = (
    "https://schedule-of.mirea.ru",
    "https://timetable.mirea.ru",
    "https://schedule.mirea.ru",
)
BLOCKED_MARKERS = (
    "ddos-guard",
    "restricted access from your current ip",
    "access denied",
    "ошибка 403",
)
WEEK_HINT_RE = re.compile(r"кр\.?\s*([\d,\s\-]+)\s*н", re.I)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
WEEKDAY_NAMES = {
    "понедельник": 0,
    "пн": 0,
    "вторник": 1,
    "вт": 1,
    "среда": 2,
    "ср": 2,
    "четверг": 3,
    "чт": 3,
    "пятница": 4,
    "пт": 4,
    "суббота": 5,
    "сб": 5,
    "воскресенье": 6,
    "вс": 6,
}


class SyncError(Exception):
    pass


@dataclass
class WeeklyLesson:
    weekday: int
    start: time
    end: time
    parity: str
    weeks: list[int] | None
    subject: str
    lesson_type: str
    teacher: str
    room: str


@dataclass
class ConcreteLesson:
    date: date
    start: time
    end: time
    subject: str
    lesson_type: str
    teacher: str
    room: str


def normalize_group(name: str) -> str:
    return re.sub(r"\s+", "", name or "").upper().replace("Ё", "Е")


def cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value).strip()


def parse_time_value(value) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        total = int(round(float(value) * 24 * 60))
        return time((total // 60) % 24, total % 60)
    text = cell_text(value).replace(".", ":").replace("—", "-").replace("–", "-")
    match = re.search(r"(\d{1,2})[:\-](\d{2})", text)
    if not match:
        return None
    return time(int(match.group(1)) % 24, int(match.group(2)) % 60)


def parse_weekday(value) -> int | None:
    text = cell_text(value).lower().replace("ё", "е")
    if not text:
        return None
    first = text.split()[0]
    return WEEKDAY_NAMES.get(first)


def parse_parity(value) -> str | None:
    text = cell_text(value).upper().replace(" ", "")
    if text in {"I", "1", "ЧИСЛ", "НЧ"}:
        return "odd"
    if text in {"II", "2", "ЗНАМ", "ЧЕТ"}:
        return "even"
    return None


def parse_week_list(text: str) -> list[int] | None:
    match = WEEK_HINT_RE.search(text or "")
    if not match:
        return None
    weeks: list[int] = []
    for part in match.group(1).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            if left.strip().isdigit() and right.strip().isdigit():
                weeks.extend(range(int(left), int(right) + 1))
        elif part.isdigit():
            weeks.append(int(part))
    return weeks or None


def clean_subject(text: str) -> str:
    text = WEEK_HINT_RE.sub("", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,;.-")


def map_lesson_type(text: str) -> str:
    lowered = (text or "").lower()
    if "лек" in lowered:
        return "ЛК"
    if "лаб" in lowered:
        return "ЛБ"
    if "сем" in lowered or "с/р" in lowered or "с.р" in lowered:
        return "СМ"
    return "ПР"


def short_teacher(name: str) -> str:
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p]
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}. {parts[2][0]}."
    if len(parts) == 2 and len(parts[1]) > 1:
        return f"{parts[0]} {parts[1][0]}."
    return name.strip() or "—"


def _fill_merges(grid: list[list], merges) -> None:
    for item in merges:
        if hasattr(item, "min_row"):
            r0, r1, c0, c1 = item.min_row, item.max_row, item.min_col, item.max_col
        else:
            r0, r1, c0, c1 = item
            r0 += 1
            r1 += 1
            c0 += 1
            c1 += 1
        val = grid[r0 - 1][c0 - 1]
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                if grid[row - 1][col - 1] in (None, ""):
                    grid[row - 1][col - 1] = val


def load_sheets(path: str | Path) -> list[list[list]]:
    path = str(path)
    lower = path.lower()
    if lower.endswith(".xls"):
        import xlrd

        book = xlrd.open_workbook(path)
        sheets = []
        for sheet in book.sheets():
            grid = []
            for r in range(sheet.nrows):
                grid.append([sheet.cell_value(r, c) for c in range(sheet.ncols)])
            merges = getattr(sheet, "merged_cells", []) or []
            _fill_merges(grid, merges)
            sheets.append(grid)
        return sheets

    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True)
    sheets = []
    for ws in wb.worksheets:
        max_r = ws.max_row or 0
        max_c = ws.max_column or 0
        grid = [[None] * max_c for _ in range(max_r)]
        for row in ws.iter_rows(min_row=1, max_row=max_r, max_col=max_c):
            for cell in row:
                grid[cell.row - 1][cell.column - 1] = cell.value
        _fill_merges(grid, ws.merged_cells.ranges)
        sheets.append(grid)
    return sheets


def _find_group_cell(grid: list[list], group_name: str) -> tuple[int, int] | None:
    want = normalize_group(group_name)
    for r, row in enumerate(grid[:40]):
        for c, value in enumerate(row):
            text = normalize_group(cell_text(value))
            found = GROUP_RE.search(text)
            if found and normalize_group(found.group(1)) == want:
                return r, c
            if text == want:
                return r, c
    return None


def parse_excel(path: str | Path, group_name: str) -> list[WeeklyLesson]:
    want = normalize_group(group_name)
    if not want:
        raise SyncError("Не указана учебная группа для синхронизации")
    lessons: list[WeeklyLesson] = []
    for grid in load_sheets(path):
        if not grid:
            continue
        found = _find_group_cell(grid, group_name)
        if found is None:
            continue
        row_i, col_i = found
        start_row = row_i + 2
        weekday = num = start = end = parity = None
        for r in range(start_row, min(len(grid), start_row + 120)):
            row = grid[r]
            def at(offset):
                idx = col_i + offset
                if idx < 0 or idx >= len(row):
                    return None
                return row[idx]

            weekday = parse_weekday(at(-5)) if parse_weekday(at(-5)) is not None else weekday
            if cell_text(at(-4)):
                try:
                    num = int(float(cell_text(at(-4)).split()[0]))
                except (TypeError, ValueError):
                    pass
            start = parse_time_value(at(-3)) or start
            end = parse_time_value(at(-2)) or end
            parity = parse_parity(at(-1)) or parity
            subject_raw = cell_text(at(0))
            if weekday is None or not start or not end or not subject_raw:
                continue
            if GROUP_RE.search(subject_raw) or normalize_group(subject_raw) == want:
                continue
            subject = clean_subject(subject_raw)
            if subject.lower() in {"предмет", "дисциплина", "видзанятий"}:
                continue
            if subject:
                lessons.append(
                    WeeklyLesson(
                        weekday=weekday,
                        start=start,
                        end=end,
                        parity=parity or "odd",
                        weeks=parse_week_list(subject_raw),
                        subject=subject,
                        lesson_type=map_lesson_type(cell_text(at(1)) or subject_raw),
                        teacher=short_teacher(cell_text(at(2))),
                        room=cell_text(at(3))[:32],
                    )
                )
    if not lessons:
        raise SyncError(f"В файле расписания нет пар для группы {group_name}")
    return lessons


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def academic_week(day: date, semester_start: date) -> int:
    return ((monday_of(day) - monday_of(semester_start)).days // 7) + 1


def semester_bounds(cfg: JournalSettings | None = None) -> tuple[date, date]:
    cfg = cfg or JournalSettings.get()
    if cfg.semester_start and cfg.semester_end:
        return cfg.semester_start, cfg.semester_end
    today = timezone.localdate()
    if today.month >= 8:
        return date(today.year, 9, 1), date(today.year, 12, 31)
    return date(today.year, 2, 9), date(today.year, 6, 30)


def expand_semester(weekly: list[WeeklyLesson], start: date, end: date) -> list[ConcreteLesson]:
    out: list[ConcreteLesson] = []
    day = start
    while day <= end:
        week_no = academic_week(day, start)
        odd = week_no % 2 == 1
        for item in weekly:
            if item.weekday != day.weekday():
                continue
            if item.weeks is not None:
                if week_no not in item.weeks:
                    continue
            elif item.parity == "odd" and not odd:
                continue
            elif item.parity == "even" and odd:
                continue
            out.append(
                ConcreteLesson(
                    date=day,
                    start=item.start,
                    end=item.end,
                    subject=item.subject,
                    lesson_type=item.lesson_type,
                    teacher=item.teacher,
                    room=item.room,
                )
            )
        day += timedelta(days=1)
    return out


def resolve_excel_group_name() -> str:
    override = (getattr(settings, "MIREA_SCHEDULE_GROUP", "") or "").strip()
    if override:
        return override
    cfg = JournalSettings.get()
    if cfg.sync_group_name.strip():
        return cfg.sync_group_name.strip()
    student = StudentProfile.objects.select_related("group").first()
    if student and student.group_id:
        return student.group.name
    group = Group.objects.filter(is_journal=True).first()
    if group:
        return group.name
    raise SyncError("Не найдена группа для синхронизации")


def _is_blocked_body(data: bytes) -> bool:
    text = data[:4000].decode("utf-8", "ignore").lower()
    return any(marker in text for marker in BLOCKED_MARKERS)


def _http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Referer": "https://www.mirea.ru/schedule/",
        },
    )
    context = ssl.create_default_context()
    try:
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
                data = resp.read()
        except ssl.SSLError:
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
                data = resp.read()
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read()
        except Exception:
            pass
        if exc.code in (401, 403) or _is_blocked_body(body):
            raise SyncError(
                "МИРЭА закрыла доступ с этого IP (403). "
                "С нидерландского сервера сайт не открывается — загрузите Excel файлом."
            ) from exc
        raise SyncError(f"Сайт расписания ответил {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise SyncError(f"Нет доступа к {url}") from exc
    if _is_blocked_body(data):
        raise SyncError(
            "МИРЭА закрыла доступ с этого IP (403). Загрузите Excel файлом."
        )
    return data


def _schedule_links(html: str, base: str) -> list[str]:
    links = []
    seen = set()
    for groups in HREF_RE.findall(html or ""):
        href = next((part for part in groups if part), "")
        if not href:
            continue
        url = urllib.parse.urljoin(base, href.replace("&amp;", "&"))
        if url not in seen:
            seen.add(url)
            links.append(url)
    return links


def _link_score(url: str, group_name: str) -> int:
    lowered = urllib.parse.unquote(url).lower()
    score = 0
    compact = normalize_group(group_name).lower()
    if compact and compact.replace("-", "") in lowered.replace("-", ""):
        score += 100
    prefix = compact[:4]
    if prefix and prefix.lower() in lowered:
        score += 40
    if any(word in lowered for word in ("магистр", "magistr", "маг_")):
        score += 25
    if any(word in lowered for word in ("вечер", "заоч", "очно-заоч")):
        score += 15
    if any(word in lowered for word in ("экзам", "зачет", "зачёт", "session", "сессия")):
        score -= 50
    return score


def _save_temp_workbook(data: bytes, name: str = "schedule.xlsx") -> Path:
    suffix = ".xlsx" if data[:2] == b"PK" or name.lower().endswith(".xlsx") else ".xls"
    path = Path(tempfile.mkdtemp(prefix="mirea-sched-")) / f"schedule{suffix}"
    path.write_bytes(data)
    return path


def _unfold_ical(raw: str) -> list[str]:
    lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _ical_dt(value: str) -> datetime:
    value = (value or "").split(":")[-1].rstrip("Z")
    if "T" in value:
        return datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    return datetime.strptime(value[:8], "%Y%m%d")


def expand_rrule_dates(start: datetime, rrule: str, until: date) -> list[date]:
    interval = 1
    match = re.search(r"INTERVAL=(\d+)", rrule or "")
    if match:
        interval = max(1, int(match.group(1)))
    bound = until
    match = re.search(r"UNTIL=(\d{8})", rrule or "")
    if match:
        bound = min(bound, datetime.strptime(match.group(1), "%Y%m%d").date())
    days = []
    day = start.date()
    if not rrule:
        return [day] if day <= bound else []
    while day <= bound:
        days.append(day)
        day += timedelta(weeks=interval)
    return days


def parse_ical(text: str, start: date, end: date) -> list[ConcreteLesson]:
    lessons: list[ConcreteLesson] = []
    in_event = False
    fields: dict[str, str] = {}
    for line in _unfold_ical(text):
        if line == "BEGIN:VEVENT":
            in_event = True
            fields = {}
            continue
        if line == "END:VEVENT":
            in_event = False
            dt_raw = next((v for k, v in fields.items() if k.startswith("DTSTART")), "")
            end_raw = next((v for k, v in fields.items() if k.startswith("DTEND")), "")
            if not dt_raw or not end_raw:
                continue
            try:
                dt_start = _ical_dt(dt_raw)
                dt_end = _ical_dt(end_raw)
            except ValueError:
                continue
            if dt_start.hour == 0 and dt_end.hour == 0:
                continue
            subject = (
                fields.get("X-META-DISCIPLINE")
                or fields.get("SUMMARY")
                or ""
            ).strip()
            if subject.lower().startswith(("пр ", "лек ", "лаб ", "сем ")):
                subject = subject.split(" ", 1)[-1]
            subject = clean_subject(subject)
            if not subject:
                continue
            rrule = fields.get("RRULE", "")
            teacher = fields.get("X-META-TEACHER") or ""
            room = (fields.get("X-META-AUDITORIUM") or fields.get("LOCATION") or "")[:32]
            lesson_type = map_lesson_type(
                fields.get("X-META-LESSON_TYPE") or fields.get("SUMMARY") or ""
            )
            for day in expand_rrule_dates(dt_start, rrule, end):
                if day < start:
                    continue
                lessons.append(
                    ConcreteLesson(
                        date=day,
                        start=dt_start.time(),
                        end=dt_end.time(),
                        subject=subject,
                        lesson_type=lesson_type,
                        teacher=short_teacher(teacher),
                        room=room,
                    )
                )
            continue
        if in_event and ":" in line:
            key, value = line.split(":", 1)
            fields[key] = value.strip()
            fields[key.split(";", 1)[0]] = value.strip()
    if not lessons:
        raise SyncError("В календаре МИРЭА нет пар для выбранного семестра")
    return lessons


def _search_items(payload) -> list:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    items = payload.get("data") or payload.get("results") or payload.get("items") or []
    if isinstance(items, dict):
        items = items.get("data") or items.get("results") or []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def fetch_from_schedule_of(group_name: str, start: date, end: date) -> list[ConcreteLesson]:
    want = normalize_group(group_name)
    last_error = None
    for base in SCHEDULE_OF_BASES:
        search = f"{base}/schedule/api/search?limit=50&match={urllib.parse.quote(group_name)}"
        try:
            payload = json.loads(_http_get(search, timeout=15).decode("utf-8", "ignore"))
        except (SyncError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            last_error = exc
            continue
        hit = None
        for item in _search_items(payload):
            title = (
                item.get("targetTitle")
                or item.get("fullTitle")
                or item.get("name")
                or ""
            )
            target = item.get("scheduleTarget", 1)
            if str(target) in {"1", "None"} or target is None:
                if normalize_group(str(title)) == want:
                    hit = item
                    break
        if hit is None:
            last_error = SyncError(f"Группа {group_name} не найдена в API расписания")
            continue
        group_id = hit.get("id") or hit.get("uid")
        schedule_target = hit.get("scheduleTarget", 1)
        ical_url = (
            hit.get("iCalLink")
            or hit.get("icalLink")
            or f"{base}/schedule/api/ical/{schedule_target}/{group_id}?includeMeta=true"
        )
        try:
            raw = _http_get(ical_url, timeout=25).decode("utf-8", "ignore")
        except SyncError as exc:
            last_error = exc
            continue
        if "BEGIN:VEVENT" not in raw:
            last_error = SyncError("API расписания не вернуло календарь")
            continue
        return parse_ical(raw, start, end)
    raise last_error or SyncError("Официальный API расписания недоступен")


def download_excel_for_group(group_name: str) -> Path:
    local = (getattr(settings, "MIREA_SCHEDULE_FILE", "") or "").strip()
    if local:
        path = Path(local)
        if not path.is_file():
            raise SyncError(f"Локальный файл расписания не найден: {local}")
        return path

    cfg = JournalSettings.get()
    page_url = getattr(settings, "MIREA_SCHEDULE_URL", "https://www.mirea.ru/schedule/")
    candidates: list[str] = []
    if cfg.sync_file_url:
        candidates.append(cfg.sync_file_url)
    page_error = None
    try:
        html = _http_get(page_url, timeout=15).decode("utf-8", "ignore")
        links = sorted(_schedule_links(html, page_url), key=lambda u: -_link_score(u, group_name))
        for url in links:
            if url not in candidates:
                candidates.append(url)
    except SyncError as exc:
        page_error = exc
    if not candidates:
        raise SyncError(
            "На странице mirea.ru/schedule больше нет ссылок на Excel "
            "(расписание перенесли в МАХ). Загрузите файл вручную."
            + (f" {page_error}" if page_error else "")
        )

    last_error = None
    for url in candidates[:18]:
        try:
            data = _http_get(url)
        except SyncError as exc:
            last_error = exc
            continue
        if len(data) < 1000:
            continue
        path = _save_temp_workbook(data, url)
        try:
            parse_excel(path, group_name)
        except SyncError:
            continue
        cfg.sync_file_url = url
        cfg.save(update_fields=["sync_file_url"])
        return path
    raise SyncError(
        f"Группа {group_name} не найдена в Excel. "
        + (str(last_error) if last_error else "Загрузите файл вручную.")
    )


def _get_subject(name: str) -> Subject:
    name = clean_subject(name) or "Дисциплина"
    obj, _ = Subject.objects.get_or_create(name=name[:160])
    return obj


def _get_teacher(name: str) -> Teacher:
    short = short_teacher(name)[:64]
    full = (name or short).strip()[:120] or short
    obj = Teacher.objects.filter(short_name=short).first()
    if obj:
        return obj
    obj = Teacher.objects.filter(full_name=full).first()
    if obj:
        return obj
    return Teacher.objects.create(short_name=short, full_name=full)


def apply_sync(group: Group, concrete: list[ConcreteLesson]) -> dict:
    created = 0
    updated = 0
    skipped_manual = 0
    kept_pending: set[int] = set()
    with transaction.atomic():
        manuals = {
            (item.date, item.start_time)
            for item in group.lessons.filter(source="manual").only("date", "start_time")
        }
        for item in concrete:
            key = (item.date, item.start)
            if key in manuals:
                skipped_manual += 1
                continue
            subject = _get_subject(item.subject)
            teacher = _get_teacher(item.teacher)
            subject.teachers.add(teacher)
            existing = (
                group.lessons.filter(source="sync", date=item.date, start_time=item.start)
                .order_by("id")
                .first()
            )
            if existing:
                existing.subject = subject
                existing.teacher = teacher
                existing.end_time = item.end
                existing.lesson_type = item.lesson_type
                existing.room = item.room[:32]
                existing.save(
                    update_fields=["subject", "teacher", "end_time", "lesson_type", "room"]
                )
                if not existing.accepted:
                    kept_pending.add(existing.id)
                updated += 1
                continue
            lesson = Lesson.objects.create(
                group=group,
                subject=subject,
                teacher=teacher,
                date=item.date,
                start_time=item.start,
                end_time=item.end,
                lesson_type=item.lesson_type,
                week_type="Н",
                room=item.room[:32],
                source="sync",
                accepted=False,
            )
            created += 1
            kept_pending.add(lesson.id)
        stale = group.lessons.filter(source="sync", accepted=False).exclude(id__in=kept_pending)
        removed = stale.count()
        stale.delete()
    pending = group.lessons.filter(source="sync", accepted=False).count()
    return {
        "created": created,
        "updated": updated,
        "skipped_manual": skipped_manual,
        "removed": removed,
        "pending": pending,
    }


def _collect_concrete(
    excel_group: str,
    start: date,
    end: date,
    *,
    file_bytes: bytes | None = None,
    filename: str = "schedule.xlsx",
) -> tuple[list[ConcreteLesson], str]:
    if file_bytes:
        path = _save_temp_workbook(file_bytes, filename)
        weekly = parse_excel(path, excel_group)
        return expand_semester(weekly, start, end), "file"
    local = (getattr(settings, "MIREA_SCHEDULE_FILE", "") or "").strip()
    if local:
        weekly = parse_excel(local, excel_group)
        return expand_semester(weekly, start, end), "file"
    errors: list[str] = []
    try:
        return fetch_from_schedule_of(excel_group, start, end), "api"
    except SyncError as exc:
        errors.append(str(exc))
    try:
        path = download_excel_for_group(excel_group)
        weekly = parse_excel(path, excel_group)
        return expand_semester(weekly, start, end), "excel"
    except SyncError as exc:
        errors.append(str(exc))
    detail = " ".join(errors).strip()
    raise SyncError(
        "Не удалось скачать расписание автоматически. "
        "На сайте МИРЭА Excel больше не публикуют, а с зарубежного IP сайт часто закрыт. "
        "Загрузите файл .xlsx кнопкой «Загрузить файл». "
        + (detail if detail else "")
    )


def sync_journal(file_bytes: bytes | None = None, filename: str = "schedule.xlsx") -> dict:
    group = Group.objects.filter(is_journal=True).first()
    if group is None:
        raise SyncError("Группа журнала не найдена")
    excel_group = resolve_excel_group_name()
    cfg = JournalSettings.get()
    start, end = semester_bounds(cfg)
    concrete, source = _collect_concrete(
        excel_group, start, end, file_bytes=file_bytes, filename=filename
    )
    if not concrete:
        raise SyncError("В пределах семестра нет пар из официального файла")
    stats = apply_sync(group, concrete)
    cfg.last_sync_at = timezone.now()
    cfg.save(update_fields=["last_sync_at"])
    stats["group"] = excel_group
    stats["from"] = start.isoformat()
    stats["to"] = end.isoformat()
    stats["weekly"] = len(concrete)
    stats["source"] = source
    return stats


def cancel_pending() -> int:
    group = Group.objects.filter(is_journal=True).first()
    if group is None:
        return 0
    deleted, _ = group.lessons.filter(source="sync", accepted=False).delete()
    return deleted


def accept_pending(pk: int | None = None) -> int:
    group = Group.objects.filter(is_journal=True).first()
    if group is None:
        return 0
    qs = group.lessons.filter(source="sync", accepted=False)
    if pk is not None:
        qs = qs.filter(pk=pk)
    return qs.update(accepted=True)
