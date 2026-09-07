from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from journal.models import (
    Absence,
    Grade,
    Group,
    Lesson,
    LessonSlot,
    Notification,
    StudentProfile,
    Subject,
    Teacher,
    UniService,
)

UNI = [
    ("lks", "ЛКС", "Личный кабинет студента: зачётная книжка, заявления и справки.", 1,
     '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M20 18h24l-2 8H22l-2-8z"/><path d="M24 18c0-5 16-8 16 1"/><circle cx="32" cy="32" r="7"/><path d="M18 54c3-9 9-13 14-13s11 4 14 13"/></svg>'),
    ("sdo", "СДО", "Система дистанционного обучения: курсы, задания и вебинары.", 2,
     '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><rect x="8" y="18" width="36" height="24" rx="2"/><path d="M18 50h20M26 42v8"/><path d="M48 14l10 6-10 6v-4h-6v-4h6v-4z"/></svg>'),
    ("ibc", "ИБЦ", "Информационно-библиотечный центр: электронный каталог и бронирование.", 3,
     '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M12 16h18c8 0 12 4 12 10v26c-4-4-8-6-12-6H12V16z"/><path d="M52 16H34c-8 0-12 4-12 10v26c4-4 8-6 12-6h18V16z"/></svg>'),
    ("idea", "«Есть идея?»", "Площадка инициатив: предложите улучшение университета.", 4,
     '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M32 8a16 16 0 00-7 30c1 2 2 5 2 7h10c0-2 1-5 2-7a16 16 0 00-7-30z"/><path d="M26 49h12M28 54h8"/><path d="M26 30l5 5 9-9"/></svg>'),
    ("sprav", "Справочник", "Контакты кафедр, расписание сессии и телефоны деканата.", 5,
     '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><rect x="16" y="14" width="32" height="40" rx="3"/><path d="M24 10h16v8H24z"/><path d="M24 32h16M24 40h12"/><path d="M22 24h6"/></svg>'),
    ("stud", "Студофис", "Справки, обходные листы и документы об обучении.", 6,
     '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M8 30L32 12l24 18"/><rect x="14" y="28" width="36" height="26" rx="1"/><path d="M28 54V38h8v16"/><path d="M20 36h6v6h-6zM38 36h6v6h-6zM20 46h6v6h-6zM38 46h6v6h-6z"/></svg>'),
    ("fond", "Фонд", "Стипендии, материальная помощь и гранты.", 7,
     '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M10 40c6-8 12-8 22-2 10-6 16-6 22 2"/><path d="M16 44c6 10 26 10 32 0"/><path d="M32 16c2 8-8 10-6 16 4-2 8-2 12 0 2-6-8-8-6-16 0-4 6-2 6 2"/></svg>'),
    ("vo", "ВО", "Военный учебный центр: учёт и расписание занятий.", 8,
     '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M18 20l14-10 14 10-4 4H22l-4-4z"/><circle cx="32" cy="30" r="7"/><path d="M16 54c3-10 10-14 16-14s13 4 16 14"/><path d="M46 28l8 2-2 8"/></svg>'),
]


class Command(BaseCommand):
    help = "Заполняет журнал демо-данными из вёрстки"

    def handle(self, *args, **options):
        Lesson.objects.all().delete()
        Grade.objects.all().delete()
        Absence.objects.all().delete()
        Notification.objects.all().delete()
        UniService.objects.all().delete()
        StudentProfile.objects.all().delete()

        g_is, _ = Group.objects.update_or_create(
            slug="is",
            defaults={"name": "ИС-21-1", "blurb": "Бакалавриат · вечерняя форма", "is_journal": True},
        )
        g_bsmo, _ = Group.objects.update_or_create(
            slug="bsmo",
            defaults={"name": "БСМО-31-25", "blurb": "Магистратура · вечерняя форма", "is_journal": False},
        )

        def teacher(short, full=None):
            obj, _ = Teacher.objects.update_or_create(
                short_name=short, defaults={"full_name": full or short}
            )
            return obj

        def subject(name):
            obj, _ = Subject.objects.get_or_create(name=name)
            return obj

        t_lebedev = teacher("Лебедев А. С.", "Лебедев Александр Сергеевич")
        t_morozov = teacher("Морозов Д. П.", "Морозов Дмитрий Павлович")
        t_orlova = teacher("Орлова Е. М.", "Орлова Елена Михайловна")
        t_kim = teacher("Ким А. В.", "Ким Анна Викторовна")
        t_sokolova = teacher("Соколова Н. В.", "Соколова Наталья Владимировна")
        t_vasiliev = teacher("Васильев И. К.", "Васильев Игорь Константинович")
        t_cheb = teacher("Чебураева А. А.", "Чебураева Александра Алексеевна")
        t_ivanov = teacher("Иванов П. Н.", "Иванов Пётр Николаевич")
        t_sergeeva = teacher("Сергеева О. В.", "Сергеева Ольга Викторовна")

        s_cloud = subject("Облачные технологии")
        s_is = subject("Проектирование ИС")
        s_ml = subject("Машинное обучение")
        s_web = subject("Web-программирование")
        s_sec = subject("Информационная безопасность")
        s_db = subject("Базы данных")
        s_deploy = subject("Системы автоматизированного развертывания")
        s_it = subject("Управление IT-проектами")
        s_research = subject("Методы исследования")

        def add(group, day, start, end, typ, week, room, subj, teach, location=""):
            Lesson.objects.create(
                group=group,
                subject=subj,
                teacher=teach,
                date=day,
                start_time=start,
                end_time=end,
                lesson_type=typ,
                week_type=week,
                room=room,
                location=location,
            )

        t1800, t1930, t1940, t2110 = time(18, 0), time(19, 30), time(19, 40), time(21, 10)

        add(g_is, date(2026, 8, 31), t1800, t1930, "ЛК", "+", "301", s_db, t_sokolova)
        add(g_is, date(2026, 9, 2), t1800, t1930, "ПР", "+", "215", s_is, t_morozov)
        add(g_is, date(2026, 9, 2), t1940, t2110, "ПР", "+", "215", s_is, t_morozov)
        add(g_is, date(2026, 9, 4), t1800, t1930, "ЛБ", "+", "118", s_sec, t_kim)
        add(g_is, date(2026, 9, 7), t1800, t1930, "ПР", "Н", "402", s_cloud, t_lebedev)
        add(g_is, date(2026, 9, 7), t1940, t2110, "ПР", "Н", "402", s_cloud, t_lebedev)
        add(g_is, date(2026, 9, 8), t1800, t1930, "ПР", "Н", "215", s_is, t_morozov)
        add(g_is, date(2026, 9, 8), t1940, t2110, "ПР", "Н", "215", s_is, t_morozov)
        add(g_is, date(2026, 9, 9), t1800, t1930, "ЛК", "Н", "501", s_ml, t_orlova)
        add(g_is, date(2026, 9, 9), t1940, t2110, "ПР", "Н", "210", s_ml, t_orlova)
        add(g_is, date(2026, 9, 14), t1800, t1930, "ПР", "+", "402", s_cloud, t_lebedev)
        add(g_is, date(2026, 9, 14), t1940, t2110, "ПР", "+", "402", s_cloud, t_lebedev)
        add(g_is, date(2026, 9, 16), t1800, t1930, "СМ", "+", "307", s_is, t_morozov)
        add(g_is, date(2026, 9, 18), t1800, t1930, "ЛБ", "+", "118", s_sec, t_kim)
        add(g_is, date(2026, 9, 18), t1940, t2110, "ЛБ", "+", "118", s_sec, t_kim)

        add(g_bsmo, date(2026, 9, 7), t1800, t1930, "ЛК", "Н", "201", s_research, t_ivanov, "201 (А-1)")
        add(g_bsmo, date(2026, 9, 8), t1800, t1930, "ПР", "Н", "333", s_deploy, t_cheb, "333 (С-20)")
        add(g_bsmo, date(2026, 9, 8), t1940, t2110, "ПР", "Н", "333", s_deploy, t_cheb, "333 (С-20)")
        add(g_bsmo, date(2026, 9, 9), t1800, t1930, "ПР", "Н", "410", s_it, t_sergeeva, "410 (Б-2)")
        add(g_bsmo, date(2026, 9, 14), t1800, t1930, "ПР", "+", "333", s_deploy, t_cheb, "333 (С-20)")
        add(g_bsmo, date(2026, 9, 14), t1940, t2110, "ПР", "+", "333", s_deploy, t_cheb, "333 (С-20)")

        user, _ = User.objects.get_or_create(
            username="kononov.a.s@edu.mirea.ru",
            defaults={
                "email": "kononov.a.s@edu.mirea.ru",
                "first_name": "Артём",
                "last_name": "Кононов",
            },
        )
        user.email = "kononov.a.s@edu.mirea.ru"
        user.set_password("mirea2026")
        user.is_staff = True
        user.is_superuser = True
        user.save()

        student = StudentProfile.objects.create(
            user=user,
            short_name="Кононов А.",
            full_name="Кононов Артём Сергеевич",
            email="kononov.a.s@edu.mirea.ru",
            student_code="2561919",
            group=g_bsmo,
            pass_until=date(2027, 8, 31),
            language="Иностранный язык",
            curator="Чебураева А. А.",
        )

        tz = timezone.get_current_timezone()
        Absence.objects.create(
            student=student,
            starts_at=timezone.make_aware(datetime(2026, 4, 30, 18, 0), tz),
            ends_at=timezone.make_aware(datetime(2026, 4, 30, 23, 59), tz),
            reason="уважительная причина",
        )

        for subj, mark, title in [
            (s_cloud, "5", "Практическая работа №1"),
            (s_ml, "4", "Коллоквиум"),
            (s_is, "5", "Курсовой этап 1"),
            (s_web, "5", "Лабораторная №2"),
            (s_sec, "4", "Тест"),
        ]:
            Grade.objects.create(student=student, subject=subj, mark=mark, title=title)

        for title, text in [
            ("Пара через 15 минут", "Системы автоматизированного развертывания · 333"),
            ("Уважительное отсутствие", "Заявка рассмотрена · 30.04.2026"),
            ("Изменение расписания", "Пара 8 сентября перенесена в 333"),
            ("Новое объявление", "Студофис: приём справок до 18:00"),
            ("Оценка выставлена", "Практическая работа №1 · 5"),
        ]:
            Notification.objects.create(student=student, title=title, text=text)

        for slug, name, desc, order, svg in UNI:
            UniService.objects.create(slug=slug, name=name, description=desc, order=order, svg=svg)

        LessonSlot.objects.all().delete()
        for number, start, end in [
            (1, time(9, 0), time(10, 30)),
            (2, time(10, 40), time(12, 10)),
            (3, time(12, 40), time(14, 10)),
            (4, time(14, 20), time(15, 50)),
            (5, time(16, 20), time(17, 50)),
            (6, time(18, 0), time(19, 30)),
            (7, time(19, 40), time(21, 10)),
        ]:
            LessonSlot.objects.create(number=number, start_time=start, end_time=end)

        self.stdout.write(self.style.SUCCESS("Демо-данные загружены."))
