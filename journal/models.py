from django.db import models


class Group(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=32)
    blurb = models.CharField(max_length=120, blank=True)
    is_journal = models.BooleanField(
        default=False,
        help_text="Расписание этой группы показывается в журнале студента",
    )

    class Meta:
        verbose_name = "Группа"
        verbose_name_plural = "Группы"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Teacher(models.Model):
    full_name = models.CharField(max_length=120)
    short_name = models.CharField(max_length=64)

    class Meta:
        verbose_name = "Преподаватель"
        verbose_name_plural = "Преподаватели"
        ordering = ["short_name"]

    def __str__(self):
        return self.short_name


class LessonSlot(models.Model):
    number = models.PositiveSmallIntegerField(unique=True, verbose_name="Номер пары")
    start_time = models.TimeField(verbose_name="Начало")
    end_time = models.TimeField(verbose_name="Конец")

    class Meta:
        verbose_name = "Время пары"
        verbose_name_plural = "Времена пар"
        ordering = ["number"]

    def __str__(self):
        return f"{self.number} пара: {self.start_time:%H:%M} – {self.end_time:%H:%M}"


class Subject(models.Model):
    name = models.CharField(max_length=160)
    teachers = models.ManyToManyField(
        Teacher,
        blank=True,
        related_name="subjects",
        verbose_name="Преподаватели",
        help_text="Кто ведёт дисциплину (лектор, практик и т.д.)",
    )

    class Meta:
        verbose_name = "Дисциплина"
        verbose_name_plural = "Дисциплины"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Lesson(models.Model):
    TYPE_CHOICES = [
        ("ЛК", "Лекция"),
        ("ПР", "Практика"),
        ("ЛБ", "Лабораторная"),
        ("СМ", "Семинар"),
    ]
    WEEK_CHOICES = [
        ("Н", "Отсутствие"),
        ("+", "Присутствие"),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="lessons")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="lessons")
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="lessons")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    lesson_type = models.CharField(max_length=4, choices=TYPE_CHOICES)
    week_type = models.CharField(
        max_length=1,
        choices=WEEK_CHOICES,
        default="Н",
        verbose_name="Отметка",
        help_text="Н — отсутствие, + — присутствие",
    )
    room = models.CharField(max_length=32, blank=True)
    location = models.CharField(max_length=64, blank=True)
    SOURCE_CHOICES = [
        ("manual", "Вручную"),
        ("sync", "Синхронизация"),
    ]
    source = models.CharField(
        max_length=8,
        choices=SOURCE_CHOICES,
        default="manual",
        verbose_name="Источник",
    )
    accepted = models.BooleanField(
        default=True,
        verbose_name="В расписании",
        help_text="Снято — серый черновик из синхронизации, виден только в редакторе",
    )

    class Meta:
        verbose_name = "Пара"
        verbose_name_plural = "Пары"
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.date} {self.start_time:%H:%M} {self.subject}"

    @property
    def time_label(self):
        return f"{self.start_time:%H:%M} - {self.end_time:%H:%M}"

    @property
    def place(self):
        return self.location or self.room


class StudentProfile(models.Model):
    user = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="student_profile",
        null=True,
        blank=True,
    )
    short_name = models.CharField(max_length=64)
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    student_code = models.CharField(max_length=32)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, related_name="students")
    pass_until = models.DateField(null=True, blank=True)
    language = models.CharField(max_length=64, default="Иностранный язык")
    curator = models.CharField(max_length=120, blank=True)

    class Meta:
        verbose_name = "Профиль студента"
        verbose_name_plural = "Профили студентов"

    def __str__(self):
        return self.full_name


class Absence(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="absences")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=160, default="уважительная причина")

    class Meta:
        verbose_name = "Уважительное отсутствие"
        verbose_name_plural = "Уважительные отсутствия"
        ordering = ["-starts_at"]

    def __str__(self):
        return f"{self.student} {self.starts_at:%d.%m.%Y}"


class Grade(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="grades")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    mark = models.CharField(max_length=8)
    title = models.CharField(max_length=160)

    class Meta:
        verbose_name = "Оценка"
        verbose_name_plural = "Оценки"
        ordering = ["subject__name"]

    def __str__(self):
        return f"{self.subject}: {self.mark}"


class UniService(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=64)
    description = models.TextField()
    svg = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Сервис цифрового университета"
        verbose_name_plural = "Сервисы цифрового университета"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class JournalSettings(models.Model):
    auto_attend = models.BooleanField(
        default=False,
        verbose_name="Автоотметка посещения",
        help_text="Самим ставить «+», когда пара уже закончилась",
    )
    sync_group_name = models.CharField(
        max_length=32,
        blank=True,
        verbose_name="Группа в Excel МИРЭА",
        help_text="Если пусто — берётся группа студента, иначе имя журнальной группы",
    )
    semester_start = models.DateField(
        null=True,
        blank=True,
        verbose_name="Начало семестра",
    )
    semester_end = models.DateField(
        null=True,
        blank=True,
        verbose_name="Конец семестра",
    )
    last_sync_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Последняя синхронизация",
    )
    sync_file_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Последний файл расписания",
    )

    class Meta:
        verbose_name = "Настройки журнала"
        verbose_name_plural = "Настройки журнала"

    def __str__(self):
        return "Настройки журнала"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Notification(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=160)
    text = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
