import django.db.models.deletion
import metering_billing.utils.utils
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metering_billing", "0243_alter_backtest_backtest_name_and_more"),
    ]

    operations = [
        # ── New standalone integration tables ─────────────────────────────────
        migrations.CreateModel(
            name="MunimCustomerIntegration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("munim_customer_id", models.TextField()),
                (
                    "created",
                    models.DateTimeField(default=metering_billing.utils.utils.now_utc),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="munim_customer_links",
                        to="metering_billing.organization",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="munimcustomerintegration",
            constraint=models.UniqueConstraint(
                fields=["organization", "munim_customer_id"],
                name="unique_munim_customer_id",
            ),
        ),
        migrations.CreateModel(
            name="MunimOrganizationIntegration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("munim_account_id", models.TextField()),
                (
                    "created",
                    models.DateTimeField(default=metering_billing.utils.utils.now_utc),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="munim_organization_links",
                        to="metering_billing.organization",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="munimorganizationintegration",
            constraint=models.UniqueConstraint(
                fields=["organization", "munim_account_id"],
                name="unique_munim_account_id",
            ),
        ),
        # ── New FK fields on Organization ─────────────────────────────────────
        migrations.AddField(
            model_name="organization",
            name="munim_integration",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="organizations",
                to="metering_billing.munimorganizationintegration",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="gen_cust_in_munim_after_lotus",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="historicalorganization",
            name="gen_cust_in_munim_after_lotus",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="historicalorganization",
            name="munim_integration",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="metering_billing.munimorganizationintegration",
            ),
        ),
        # ── New FK fields on Customer ─────────────────────────────────────────
        migrations.AddField(
            model_name="customer",
            name="munim_integration",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="customers",
                to="metering_billing.munimcustomerintegration",
            ),
        ),
        migrations.AddField(
            model_name="historicalcustomer",
            name="munim_integration",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="metering_billing.munimcustomerintegration",
            ),
        ),
        # ── PAYMENT_PROCESSORS enum — alter affected fields ───────────────────
        migrations.AlterField(
            model_name="customer",
            name="payment_provider",
            field=models.CharField(
                blank=True,
                choices=[
                    ("stripe", "Stripe"),
                    ("braintree", "Braintree"),
                    ("munim", "Munim"),
                ],
                max_length=40,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="historicalcustomer",
            name="payment_provider",
            field=models.CharField(
                blank=True,
                choices=[
                    ("stripe", "Stripe"),
                    ("braintree", "Braintree"),
                    ("munim", "Munim"),
                ],
                max_length=40,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="organization",
            name="default_payment_provider",
            field=models.CharField(
                blank=True,
                choices=[
                    ("stripe", "Stripe"),
                    ("braintree", "Braintree"),
                    ("munim", "Munim"),
                ],
                max_length=40,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="historicalorganization",
            name="default_payment_provider",
            field=models.CharField(
                blank=True,
                choices=[
                    ("stripe", "Stripe"),
                    ("braintree", "Braintree"),
                    ("munim", "Munim"),
                ],
                max_length=40,
                null=True,
            ),
        ),
    ]
