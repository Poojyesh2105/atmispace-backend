from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leave_management", "0007_leavepolicy_carry_forward_leavecarryforwardlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="leavepolicy",
            name="carry_forward_frequency",
            field=models.CharField(
                choices=[("MONTHLY", "Monthly"), ("YEARLY", "Yearly")],
                default="MONTHLY",
                max_length=20,
            ),
        ),
    ]
