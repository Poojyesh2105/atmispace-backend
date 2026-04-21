from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0005_employee_ctc_per_annum_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="personal_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
    ]
