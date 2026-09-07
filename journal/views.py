import json
from datetime import datetime

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import Group, Lesson, LessonSlot, StudentProfile, Subject, Teacher, UniService


def _lesson_payload(lesson: Lesson) -> dict:
    return {
        "id": lesson.id,
        "time": lesson.time_label,
        "type": lesson.lesson_type,
        "room": lesson.room,
        "location": lesson.place,
        "subject": lesson.subject.name,
        "week": "+" if lesson.week_type == "В" else lesson.week_type,
        "teacher": lesson.teacher.short_name,
        "teacher_full": lesson.teacher.full_name,
        "subject_id": lesson.subject_id,
        "teacher_id": lesson.teacher_id,
        "start": lesson.start_time.strftime("%H:%M"),
        "end": lesson.end_time.strftime("%H:%M"),
    }


def _lessons_by_date(queryset) -> dict:
    data = {}
    for lesson in queryset.select_related("subject", "teacher"):
        data.setdefault(lesson.date.isoformat(), []).append(_lesson_payload(lesson))
    return data


def _student(request=None):
    if request is not None and request.user.is_authenticated:
        profile = getattr(request.user, "student_profile", None)
        if profile is not None:
            return (
                StudentProfile.objects.select_related("group")
                .prefetch_related("grades__subject", "absences", "notifications")
                .get(pk=profile.pk)
            )
    return (
        StudentProfile.objects.select_related("group")
        .prefetch_related("grades__subject", "absences", "notifications")
        .first()
    )


def bootstrap_payload(request=None):
    student = _student(request)
    groups = []
    journal_lessons = {}
    default_group = "bsmo"
    journal_slug = None

    for group in Group.objects.all():
        lessons = _lessons_by_date(group.lessons.all())
        groups.append(
            {
                "id": group.slug,
                "name": group.name,
                "blurb": group.blurb,
                "lessons": lessons,
            }
        )
        if group.is_journal:
            journal_lessons = lessons
            journal_slug = group.slug

    if journal_slug:
        default_group = journal_slug
    elif groups:
        default_group = groups[0]["id"]

    uni = []
    uni_svg = {}
    for item in UniService.objects.all():
        uni.append({"id": item.slug, "name": item.name, "text": item.description})
        uni_svg[item.slug] = item.svg

    grades = []
    absences = []
    notifications = []
    student_data = {
        "short_name": "Кононов А.",
        "full_name": "Кононов Артём Сергеевич",
        "email": "kononov.a.s@edu.mirea.ru",
        "student_code": "2561919",
        "group_name": "БСМО-31-25",
        "curator": "Чебураева А. А.",
        "language": "Иностранный язык",
        "pass_until": "31.08.2027",
    }

    if student:
        student_data = {
            "short_name": student.short_name,
            "full_name": student.full_name,
            "email": student.email,
            "student_code": student.student_code,
            "group_name": student.group.name if student.group else "",
            "curator": student.curator,
            "language": student.language,
            "pass_until": student.pass_until.strftime("%d.%m.%Y") if student.pass_until else "",
        }
        grades = [
            {"name": g.subject.name, "mark": g.mark, "sub": g.title}
            for g in student.grades.all()
        ]
        notifications = [
            {"title": n.title, "text": n.text} for n in student.notifications.all()
        ]
        absences = [
            {
                "starts": a.starts_at.strftime("%d.%m.%Y %H:%M"),
                "ends": a.ends_at.strftime("%d.%m.%Y %H:%M"),
                "reason": a.reason,
            }
            for a in student.absences.all()
        ]

    can_edit = bool(request and request.session.get("schedule_edit"))
    return {
        "student": student_data,
        "journal_lessons": journal_lessons,
        "groups": groups,
        "default_group": default_group,
        "journal_group_name": next((g["name"] for g in groups if g["id"] == default_group), ""),
        "uni": uni,
        "uni_svg": uni_svg,
        "grades": grades,
        "notifications": notifications,
        "absences": absences,
        "app_version": "1.9.0+9478",
        "android_version": "2.1.0+253",
        "contact_email": "attendance@mirea.ru",
        "can_edit": can_edit,
        "subjects": list(Subject.objects.order_by("name").values("id", "name")),
        "teachers": list(Teacher.objects.order_by("short_name").values("id", "short_name", "full_name")),
        "slots": [
            {
                "number": s.number,
                "start": s.start_time.strftime("%H:%M"),
                "end": s.end_time.strftime("%H:%M"),
                "label": f"{s.number} пара: {s.start_time:%H:%M} – {s.end_time:%H:%M}",
            }
            for s in LessonSlot.objects.all()
        ],
    }


def index(request):
    if not request.user.is_authenticated:
        return render(request, "journal/guest.html")
    payload = bootstrap_payload(request)
    return render(
        request,
        "journal/index.html",
        {"bootstrap": payload, "student": payload["student"]},
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("journal:index")
    error = ""
    email = ""
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""
        remember = bool(request.POST.get("remember"))
        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            user = authenticate(request, username=user.username, password=password)
        else:
            user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            request.session.set_expiry(60 * 60 * 24 * 14 if remember else 0)
            return redirect("journal:index")
        error = "Неверный e-mail или пароль"
    return render(request, "journal/login.html", {"error": error, "email": email})


def logout_view(request):
    logout(request)
    return redirect("journal:index")


def instruction_view(request):
    return render(request, "journal/instruction.html")


def api_bootstrap(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "auth"}, status=401)
    return JsonResponse(bootstrap_payload(request))


def api_lessons(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "auth"}, status=401)
    slug = request.GET.get("group")
    if request.GET.get("journal") == "1":
        group = Group.objects.filter(is_journal=True).first()
    elif slug:
        group = get_object_or_404(Group, slug=slug)
    else:
        group = Group.objects.filter(is_journal=True).first()
    if group is None:
        return JsonResponse({"lessons": {}})
    qs = group.lessons.all()
    date_from = request.GET.get("from")
    date_to = request.GET.get("to")
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return JsonResponse({"group": group.slug, "lessons": _lessons_by_date(qs)})


def _json_body(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST


def _require_edit(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Нужна авторизация"}, status=401)
    if not request.session.get("schedule_edit"):
        return JsonResponse({"ok": False, "error": "Редактор выключен"}, status=403)
    return None


def _parse_time(value):
    return datetime.strptime(value, "%H:%M").time()


def _get_or_create_subject(name):
    name = (name or "").strip()
    if not name:
        raise ValueError("Укажите дисциплину")
    obj, _ = Subject.objects.get_or_create(name=name)
    return obj


def _get_or_create_teacher(name):
    name = (name or "").strip()
    if not name:
        raise ValueError("Укажите преподавателя")
    obj = Teacher.objects.filter(short_name=name).first()
    if obj:
        return obj
    obj = Teacher.objects.filter(full_name=name).first()
    if obj:
        return obj
    return Teacher.objects.create(short_name=name, full_name=name)


@require_http_methods(["POST"])
def api_edit_mode(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Нужна авторизация"}, status=401)
    data = _json_body(request)
    enabled = bool(data.get("enabled"))
    if not enabled:
        request.session["schedule_edit"] = False
        return JsonResponse({"ok": True, "can_edit": False})
    password = data.get("password") or ""
    if password != getattr(settings, "SCHEDULE_EDIT_PASSWORD", ""):
        return JsonResponse({"ok": False, "error": "Неверный пароль"}, status=403)
    request.session["schedule_edit"] = True
    return JsonResponse({"ok": True, "can_edit": True})


@require_http_methods(["POST"])
def api_lesson_create(request):
    denied = _require_edit(request)
    if denied:
        return denied
    data = _json_body(request)
    try:
        group = Group.objects.filter(is_journal=True).first()
        if group is None:
            raise ValueError("Группа журнала не найдена")
        day = datetime.strptime(data.get("date") or "", "%Y-%m-%d").date()
        lesson = Lesson.objects.create(
            group=group,
            subject=_get_or_create_subject(data.get("subject")),
            teacher=_get_or_create_teacher(data.get("teacher")),
            date=day,
            start_time=_parse_time(data.get("start") or "18:00"),
            end_time=_parse_time(data.get("end") or "19:30"),
            lesson_type=data.get("type") or "ПР",
            week_type=(data.get("week") or "Н").replace("В", "+"),
            room=(data.get("room") or "").strip(),
            location=(data.get("location") or "").strip(),
        )
    except (ValueError, TypeError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": True, "lesson": _lesson_payload(lesson)})


@require_http_methods(["POST"])
def api_lesson_update(request, pk):
    denied = _require_edit(request)
    if denied:
        return denied
    lesson = get_object_or_404(Lesson, pk=pk)
    data = _json_body(request)
    try:
        if data.get("subject"):
            lesson.subject = _get_or_create_subject(data.get("subject"))
        if data.get("teacher"):
            lesson.teacher = _get_or_create_teacher(data.get("teacher"))
        if data.get("start"):
            lesson.start_time = _parse_time(data["start"])
        if data.get("end"):
            lesson.end_time = _parse_time(data["end"])
        if data.get("type"):
            lesson.lesson_type = data["type"]
        if data.get("week"):
            lesson.week_type = data["week"].replace("В", "+")
        if "room" in data:
            lesson.room = (data.get("room") or "").strip()
        if "location" in data:
            lesson.location = (data.get("location") or "").strip()
        lesson.save()
    except (ValueError, TypeError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": True, "lesson": _lesson_payload(lesson)})


@require_http_methods(["POST"])
def api_lesson_delete(request, pk):
    denied = _require_edit(request)
    if denied:
        return denied
    lesson = get_object_or_404(Lesson, pk=pk)
    lesson.delete()
    return JsonResponse({"ok": True})
