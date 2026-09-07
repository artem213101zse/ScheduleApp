import datetime

from django.db import migrations, models


def seed_slots(apps, schema_editor):
    LessonSlot = apps.get_model("journal", "LessonSlot")
    slots = [
        (1, datetime.time(9, 0), datetime.time(10, 30)),
        (2, datetime.time(10, 40), datetime.time(12, 10)),
        (3, datetime.time(12, 40), datetime.time(14, 10)),
        (4, datetime.time(14, 20), datetime.time(15, 50)),
        (5, datetime.time(16, 20), datetime.time(17, 50)),
        (6, datetime.time(18, 0), datetime.time(19, 30)),
        (7, datetime.time(19, 40), datetime.time(21, 10)),
    ]
    for number, start, end in slots:
        LessonSlot.objects.update_or_create(
            number=number,
            defaults={"start_time": start, "end_time": end},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("journal", "0003_attendance_mark"),
    ]

    operations = [
        migrations.CreateModel(
            name="LessonSlot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveSmallIntegerField(unique=True, verbose_name="Номер пары")),
                ("start_time", models.TimeField(verbose_name="Начало")),
                ("end_time", models.TimeField(verbose_name="Конец")),
            ],
            options={
                "verbose_name": "Время пары",
                "verbose_name_plural": "Времена пар",
                "ordering": ["number"],
            },
        ),
        migrations.RunPython(seed_slots, migrations.RunPython.noop),
    ]
