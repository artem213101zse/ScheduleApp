from django.contrib import admin

from .models import (
    Absence,
    Grade,
    Group,
    JournalSettings,
    Lesson,
    LessonSlot,
    Notification,
    StudentProfile,
    Subject,
    Teacher,
    UniService,
)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_journal")
    search_fields = ("name", "slug")


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("short_name", "full_name")
    search_fields = ("short_name", "full_name")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    filter_horizontal = ("teachers",)
    list_display = ("name", "teacher_names")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("teachers")

    @admin.display(description="Преподаватели")
    def teacher_names(self, obj):
        return ", ".join(t.short_name for t in obj.teachers.all()) or "—"


@admin.register(LessonSlot)
class LessonSlotAdmin(admin.ModelAdmin):
    list_display = ("number", "start_time", "end_time")
    ordering = ("number",)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("date", "start_time", "group", "subject", "teacher", "lesson_type", "room", "source", "accepted")
    list_filter = ("group", "lesson_type", "date", "source", "accepted")
    search_fields = ("subject__name", "teacher__short_name", "room")
    autocomplete_fields = ("subject", "teacher", "group")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.subject_id and obj.teacher_id:
            obj.subject.teachers.add(obj.teacher)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "group", "student_code", "user")


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ("student", "starts_at", "ends_at")


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("student", "subject", "mark", "title")


@admin.register(UniService)
class UniServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "created_at")


@admin.register(JournalSettings)
class JournalSettingsAdmin(admin.ModelAdmin):
    list_display = ("auto_attend", "sync_group_name", "semester_start", "semester_end", "last_sync_at")
