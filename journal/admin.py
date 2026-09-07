from django.contrib import admin

from .models import (
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


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_journal")


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("short_name", "full_name")
    search_fields = ("short_name", "full_name")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(LessonSlot)
class LessonSlotAdmin(admin.ModelAdmin):
    list_display = ("number", "start_time", "end_time")
    ordering = ("number",)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("date", "start_time", "group", "subject", "lesson_type", "room")
    list_filter = ("group", "lesson_type", "date")
    search_fields = ("subject__name", "teacher__short_name", "room")


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
