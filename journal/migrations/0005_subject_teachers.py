from django.db import migrations, models


def fill_subject_teachers(apps, schema_editor):
    Lesson = apps.get_model("journal", "Lesson")
    Subject = apps.get_model("journal", "Subject")
    Through = Subject.teachers.through
    pairs = {
        (lesson.subject_id, lesson.teacher_id)
        for lesson in Lesson.objects.all()
        if lesson.subject_id and lesson.teacher_id
    }
    Through.objects.bulk_create(
        [Through(subject_id=s, teacher_id=t) for s, t in pairs],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("journal", "0004_lessonslot"),
    ]

    operations = [
        migrations.AddField(
            model_name="subject",
            name="teachers",
            field=models.ManyToManyField(
                blank=True,
                help_text="Кто ведёт дисциплину (лектор, практик и т.д.)",
                related_name="subjects",
                to="journal.teacher",
                verbose_name="Преподаватели",
            ),
        ),
        migrations.RunPython(fill_subject_teachers, migrations.RunPython.noop),
    ]
