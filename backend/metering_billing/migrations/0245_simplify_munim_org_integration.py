from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("metering_billing", "0244_munim_integration"),
    ]

    operations = [
        # Drop the unique constraint that included munim_account_id
        migrations.RemoveConstraint(
            model_name="munimorganizationintegration",
            name="unique_munim_account_id",
        ),
        # Remove the munim_account_id field
        migrations.RemoveField(
            model_name="munimorganizationintegration",
            name="munim_account_id",
        ),
        # Enforce one integration per org at the DB level
        migrations.AlterField(
            model_name="munimorganizationintegration",
            name="organization",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="munim_organization_links",
                to="metering_billing.organization",
            ),
        ),
    ]
