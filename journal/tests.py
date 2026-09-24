from datetime import date, time

from django.contrib.auth.models import User
from django.test import Client, TestCase

from journal.models import Group, Lesson, Subject, Teacher


class LessonEditorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="kononov.a.s@edu.mirea.ru",
            email="kononov.a.s@edu.mirea.ru",
            password="mirea2026",
        )
        self.group = Group.objects.create(slug="is", name="ИС-21-1", is_journal=True)
        self.t1 = Teacher.objects.create(short_name="Лебедев А. С.", full_name="Лебедев Александр Сергеевич")
        self.t2 = Teacher.objects.create(short_name="Морозов Д. П.", full_name="Морозов Дмитрий Павлович")
        self.subj = Subject.objects.create(name="Облачные технологии")
        self.subj.teachers.add(self.t1, self.t2)
        self.client = Client()
        self.client.login(username="kononov.a.s@edu.mirea.ru", password="mirea2026")
        session = self.client.session
        session["schedule_edit"] = True
        session.save()

    def test_index_uses_native_selects(self):
        html = self.client.get("/").content.decode("utf-8")
        self.assertIn('<select class="login-input" id="fSubject" required>', html)
        self.assertIn('<select class="login-input" id="fTeacher" required>', html)
        self.assertIn('id="btnCopyToggle"', html)
        self.assertIn('id="fCopyDate"', html)
        self.assertNotIn('id="subjectList"', html)
        self.assertNotIn('list="subjectList"', html)

    def test_bootstrap_nests_subject_teachers(self):
        data = self.client.get("/api/bootstrap/").json()
        cloud = next(s for s in data["subjects"] if s["name"] == "Облачные технологии")
        names = {t["short_name"] for t in cloud["teachers"]}
        self.assertEqual(names, {"Лебедев А. С.", "Морозов Д. П."})

    def test_create_binds_teacher_to_subject(self):
        extra = Teacher.objects.create(short_name="Ким А. В.", full_name="Ким Анна Викторовна")
        resp = self.client.post(
            "/api/lessons/create/",
            data={
                "date": "2026-09-14",
                "subject_id": self.subj.id,
                "teacher_id": extra.id,
                "start": "18:00",
                "end": "19:30",
                "type": "ПР",
                "week": "Н",
                "room": "402",
            },
            content_type="application/json",
        )
        self.assertTrue(resp.json().get("ok"), resp.json())
        self.assertTrue(self.subj.teachers.filter(pk=extra.pk).exists())
        self.assertEqual(Lesson.objects.filter(date=date(2026, 9, 14)).count(), 1)

    def test_copy_creates_same_pair_on_other_day(self):
        payload = {
            "date": "2026-09-07",
            "subject_id": self.subj.id,
            "teacher_id": self.t1.id,
            "start": "18:00",
            "end": "19:30",
            "type": "ПР",
            "week": "Н",
            "room": "402",
        }
        first = self.client.post("/api/lessons/create/", data=payload, content_type="application/json")
        self.assertTrue(first.json().get("ok"), first.json())
        payload["date"] = "2026-09-14"
        payload["start"] = "19:40"
        payload["end"] = "21:10"
        copied = self.client.post("/api/lessons/create/", data=payload, content_type="application/json")
        self.assertTrue(copied.json().get("ok"), copied.json())
        days = list(Lesson.objects.order_by("date", "start_time").values_list("date", "start_time"))
        self.assertEqual(len(days), 2)
        self.assertEqual(days[0][0], date(2026, 9, 7))
        self.assertEqual(days[1][0], date(2026, 9, 14))
        self.assertEqual(days[1][1], time(19, 40))

    def _lesson(self, day, start=None, end=None, week="Н"):
        return Lesson.objects.create(
            group=self.group,
            subject=self.subj,
            teacher=self.t1,
            date=day,
            start_time=start or time(18, 0),
            end_time=end or time(19, 30),
            lesson_type="ПР",
            week_type=week,
            room="402",
        )

    def test_index_has_week_copy_controls(self):
        html = self.client.get("/").content.decode("utf-8")
        self.assertIn('id="btnCopyWeekToggle"', html)
        self.assertIn('id="fCopyWeekDate"', html)
        self.assertIn('id="btnCopyWeekGo"', html)

    def test_quick_attendance_toggles_mark(self):
        lesson = self._lesson(date(2026, 9, 7), week="Н")
        resp = self.client.post(
            f"/api/lessons/{lesson.pk}/update/",
            data={"week": "+"},
            content_type="application/json",
        )
        self.assertTrue(resp.json().get("ok"), resp.json())
        lesson.refresh_from_db()
        self.assertEqual(lesson.week_type, "+")
        resp = self.client.post(
            f"/api/lessons/{lesson.pk}/update/",
            data={"week": "Н"},
            content_type="application/json",
        )
        self.assertTrue(resp.json().get("ok"), resp.json())
        lesson.refresh_from_db()
        self.assertEqual(lesson.week_type, "Н")

    def test_copy_week_shifts_lessons_and_resets_mark(self):
        self._lesson(date(2026, 9, 7), week="+")
        self._lesson(date(2026, 9, 9), start=time(19, 40), end=time(21, 10), week="+")
        resp = self.client.post(
            "/api/lessons/copy-week/",
            data={"from": "2026-09-08", "to": "2026-09-16"},
            content_type="application/json",
        )
        body = resp.json()
        self.assertTrue(body.get("ok"), body)
        self.assertEqual(body["created"], 2)
        self.assertEqual(body["skipped"], 0)
        monday = Lesson.objects.get(date=date(2026, 9, 14))
        wednesday = Lesson.objects.get(date=date(2026, 9, 16))
        self.assertEqual(monday.week_type, "Н")
        self.assertEqual(monday.subject_id, self.subj.id)
        self.assertEqual(monday.teacher_id, self.t1.id)
        self.assertEqual(monday.room, "402")
        self.assertEqual(wednesday.start_time, time(19, 40))
        again = self.client.post(
            "/api/lessons/copy-week/",
            data={"from": "2026-09-07", "to": "2026-09-14"},
            content_type="application/json",
        )
        self.assertEqual(again.json()["created"], 0)
        self.assertEqual(again.json()["skipped"], 2)

    def test_copy_week_rejects_same_week(self):
        self._lesson(date(2026, 9, 7))
        resp = self.client.post(
            "/api/lessons/copy-week/",
            data={"from": "2026-09-07", "to": "2026-09-09"},
            content_type="application/json",
        )
        self.assertFalse(resp.json().get("ok"))
        self.assertEqual(resp.status_code, 400)
