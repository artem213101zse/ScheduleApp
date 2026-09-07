from django.db import migrations, models


def convert_marks(apps, schema_editor):
    Lesson = apps.get_model("journal", "Lesson")
    Lesson.objects.filter(week_type="В").update(week_type="+")


class Migration(migrations.Migration):
    dependencies = [
        ("journal", "0002_studentprofile_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lesson",
            name="week_type",
            field=models.CharField(
                choices=[("Н", "Отсутствие"), ("+", "Присутствие")],
                default="Н",
                help_text="Н — отсутствие, + — присутствие",
                max_length=1,
                verbose_name="Отметка",
            ),
        ),
        migrations.RunPython(convert_marks, migrations.RunPython.noop),
    ]
