import itertools
import json
import unittest.mock as mock
from datetime import timedelta
from decimal import Decimal

import pytest
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from metering_billing.models import (
    BillingRecord,
    Event,
    Invoice,
    InvoiceLineItemAdjustment,
    Metric,
    PlanComponent,
    PriceAdjustment,
    PriceTier,
    SubscriptionRecord,
)
from metering_billing.serializers.serializer_utils import DjangoJSONEncoder
from metering_billing.tasks import calculate_invoice_inner
from metering_billing.utils import now_utc
from metering_billing.utils.enums import PRICE_ADJUSTMENT_TYPE
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def invoice_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_customers_to_org,
    add_product_to_org,
    add_plan_to_product,
    add_plan_version_to_plan,
    add_subscription_record_to_org,
):
    def do_invoice_test_common_setup(
        *,
        auth_method,
        make_plan_yearly=False,
    ):
        setup_dict = {}
        # set up organizations and api keys
        org, key = generate_org_and_api_key()
        org2, key2 = generate_org_and_api_key()
        setup_dict = {
            "org": org,
            "key": key,
            "org2": org2,
            "key2": key2,
        }
        org.subscription_filter_keys = ["email"]
        org.save()
        # set up the client with the appropriate api key spec
        if auth_method == "api_key":
            client = api_client_with_api_key_auth(key)
        elif auth_method == "session_auth":
            client = APIClient()
            (user,) = add_users_to_org(org, n=1)
            client.force_authenticate(user=user)
            setup_dict["user"] = user
        else:
            client = api_client_with_api_key_auth(key)
            (user,) = add_users_to_org(org, n=1)
            client.force_authenticate(user=user)
            setup_dict["user"] = user
        setup_dict["client"] = client
        (customer,) = add_customers_to_org(org, n=1)
        setup_dict["customer"] = customer
        event_properties = (
            {"num_characters": 350, "peak_bandwith": 65},
            {"num_characters": 125, "peak_bandwith": 148},
            {"num_characters": 543, "peak_bandwith": 16},
        )
        baker.make(
            Event,
            organization=org,
            event_name="email_sent",
            time_created=now_utc() - timedelta(days=1),
            properties=itertools.cycle(event_properties),
            _quantity=3,
        )
        metric_set = baker.make(
            Metric,
            billable_metric_name=itertools.cycle(
                ["Email Character Count", "Peak Bandwith", "Email Count"]
            ),
            organization=org,
            event_name="email_sent",
            property_name=itertools.cycle(["num_characters", "peak_bandwith", ""]),
            usage_aggregation_type=itertools.cycle(["sum", "max", "count"]),
            _quantity=3,
        )
        for metric in metric_set:
            metric.provision_materialized_views()
        setup_dict["metrics"] = metric_set
        product = add_product_to_org(org)
        plan = add_plan_to_product(product)
        if make_plan_yearly:
            plan.plan_duration = "yearly"
            plan.save()
        plan_version = add_plan_version_to_plan(plan)
        for i, (fmu, cpb, mupb) in enumerate(
            zip([50, 0, 1], [5, 0.05, 2], [100, 1, 1])
        ):
            pc = PlanComponent.objects.create(
                plan_version=plan_version,
                billable_metric=metric_set[i],
            )
            start = 0
            if fmu > 0:
                PriceTier.objects.create(
                    plan_component=pc,
                    type=PriceTier.PriceTierType.FREE,
                    range_start=0,
                    range_end=fmu,
                )
                start = fmu
            PriceTier.objects.create(
                plan_component=pc,
                type=PriceTier.PriceTierType.PER_UNIT,
                range_start=start,
                cost_per_batch=cpb,
                metric_units_per_batch=mupb,
            )
        setup_dict["billing_plan"] = plan_version
        subscription_record = add_subscription_record_to_org(
            org, plan_version, customer, now_utc() - timedelta(days=3)
        )
        setup_dict["subscription_record"] = subscription_record

        return setup_dict

    return do_invoice_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestGenerateInvoice:
    def test_generate_invoice(self, invoice_test_common_setup):
        setup_dict = invoice_test_common_setup(auth_method="api_key")

        prev_invoices_len = Invoice.objects.filter(
            payment_status=Invoice.PaymentStatus.DRAFT
        ).count()
        response = setup_dict["client"].get(
            reverse(
                "customer-draft_invoice",
                kwargs={"customer_id": setup_dict["customer"].customer_id},
            )
        )
        assert response.status_code == status.HTTP_200_OK
        new_invoices_len = Invoice.objects.filter(
            payment_status=Invoice.PaymentStatus.DRAFT
        ).count()

        assert new_invoices_len == prev_invoices_len  # don't generate from drafts

    def test_generate_invoice_with_price_adjustments(self, invoice_test_common_setup):
        # deleting inv objects because it marks it as already paid and we get 0s everywhere

        setup_dict = invoice_test_common_setup(auth_method="api_key")
        Invoice.objects.all().delete()
        br = BillingRecord.objects.filter(recurring_charge__isnull=False).first()
        br.next_invoicing_date = br.invoicing_dates[0]
        br.save()
        response = setup_dict["client"].get(
            reverse(
                "customer-draft_invoice",
                kwargs={"customer_id": setup_dict["customer"].customer_id},
            )
        )
        assert response.status_code == status.HTTP_200_OK
        before_cost = response.data["invoices"][0]["amount"]
        pct_price_adjustment = PriceAdjustment.objects.create(
            organization=setup_dict["org"],
            price_adjustment_name=r"1% discount",
            price_adjustment_description=r"1% discount for being a valued customer",
            price_adjustment_type=PRICE_ADJUSTMENT_TYPE.PERCENTAGE,
            price_adjustment_amount=-1,
        )
        setup_dict["billing_plan"].price_adjustment = pct_price_adjustment
        setup_dict["billing_plan"].save()

        response = setup_dict["client"].get(
            reverse(
                "customer-draft_invoice",
                kwargs={"customer_id": setup_dict["customer"].customer_id},
            ),
        )
        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["amount"]
        assert (before_cost * Decimal("0.99") - after_cost) < Decimal("0.01")

        fixed_price_adjustment = PriceAdjustment.objects.create(
            organization=setup_dict["org"],
            price_adjustment_name=r"$1 discount",
            price_adjustment_description=r"$1 discount for being a valued customer",
            price_adjustment_type=PRICE_ADJUSTMENT_TYPE.FIXED,
            price_adjustment_amount=-1,
        )
        setup_dict["billing_plan"].price_adjustment = fixed_price_adjustment
        setup_dict["billing_plan"].save()

        response = setup_dict["client"].get(
            reverse(
                "customer-draft_invoice",
                kwargs={"customer_id": setup_dict["customer"].customer_id},
            ),
        )

        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["amount"]
        assert before_cost - Decimal("1") == after_cost

        override_price_adjustment = PriceAdjustment.objects.create(
            organization=setup_dict["org"],
            price_adjustment_name=r"$20 negoatiated price",
            price_adjustment_description=r"$20 price negotiated with sales team",
            price_adjustment_type=PRICE_ADJUSTMENT_TYPE.PRICE_OVERRIDE,
            price_adjustment_amount=20,
        )
        setup_dict["billing_plan"].price_adjustment = override_price_adjustment
        setup_dict["billing_plan"].save()

        response = setup_dict["client"].get(
            reverse(
                "customer-draft_invoice",
                kwargs={"customer_id": setup_dict["customer"].customer_id},
            ),
        )

        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["amount"]
        assert Decimal("20") == after_cost

    def test_generate_invoice_with_taxes(self, invoice_test_common_setup):
        setup_dict = invoice_test_common_setup(auth_method="api_key")

        payload = {
            "include_next_period": False,
        }
        response = setup_dict["client"].get(
            reverse(
                "customer-draft_invoice",
                kwargs={"customer_id": setup_dict["customer"].customer_id},
            ),
            payload,
        )
        assert response.status_code == status.HTTP_200_OK
        before_cost = response.data["invoices"][0]["amount"]

        setup_dict["org"].tax_rate = Decimal("10")
        setup_dict["org"].save()
        response = setup_dict["client"].get(
            reverse(
                "customer-draft_invoice",
                kwargs={"customer_id": setup_dict["customer"].customer_id},
            ),
            payload,
        )
        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["amount"]
        assert (before_cost * Decimal("1.1") - after_cost) < Decimal("0.01")

        setup_dict["customer"].tax_rate = Decimal("20")
        setup_dict["customer"].save()
        response = setup_dict["client"].get(
            reverse(
                "customer-draft_invoice",
                kwargs={"customer_id": setup_dict["customer"].customer_id},
            ),
            payload,
        )
        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["amount"]
        assert (before_cost * Decimal("1.2") - after_cost) < Decimal("0.01")

    def test_generate_invoice_pdf(self, invoice_test_common_setup):
        setup_dict = invoice_test_common_setup(auth_method="api_key")
        SubscriptionRecord.objects.all().delete()
        Event.objects.all().delete()
        payload = {
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": setup_dict["customer"].customer_id,
            "version_id": setup_dict["billing_plan"].version_id,
        }
        for i in range(5):
            payload["subscription_filters"] = [
                {"property_name": "email", "value": f"{i}"}
            ]

            response = setup_dict["client"].post(
                reverse("subscription-list"),
                data=json.dumps(payload, cls=DjangoJSONEncoder),
                content_type="application/json",
            )
            assert response.status_code == status.HTTP_201_CREATED

            event_properties = (
                {"num_characters": 350, "peak_bandwith": 65, "email": f"{i}"},
                {"num_characters": 125, "peak_bandwith": 148, "email": f"{i}"},
                {"num_characters": 543, "peak_bandwith": 16, "email": f"{i}"},
            )
            baker.make(
                Event,
                organization=setup_dict["org"],
                event_name="email_sent",
                time_created=now_utc() - timedelta(days=1),
                properties=itertools.cycle(event_properties),
                cust_id=setup_dict["customer"].customer_id,
                _quantity=3,
            )

        result_invoice = Invoice.objects.order_by("-invoice_number").first()
        assert result_invoice.invoice_pdf != ""


@pytest.mark.django_db(transaction=True)
class TestOneOffInvoice:
    def test_create_one_off_invoice_success(self, invoice_test_common_setup):
        setup_dict = invoice_test_common_setup(auth_method="api_key")
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "currency_code": "USD",
            "line_items": [
                {"name": "Setup fee", "amount": "500.00", "tax_rate": "8"},
                {"name": "Professional services", "amount": "1200.00"},
            ],
        }
        response = setup_dict["client"].post(
            reverse("invoice-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        invoice = Invoice.objects.get(invoice_id=response.data["invoice_id"])
        assert invoice.payment_status == Invoice.PaymentStatus.UNPAID
        assert invoice.customer == setup_dict["customer"]
        assert invoice.line_items.count() == 2
        # 500 + 40 (8% tax) + 1200 = 1740
        assert invoice.amount == Decimal("1740.0000000000")
        taxed_line_item = invoice.line_items.get(name="Setup fee")
        assert taxed_line_item.adjustments.count() == 1
        adjustment = taxed_line_item.adjustments.first()
        assert (
            adjustment.adjustment_type
            == InvoiceLineItemAdjustment.AdjustmentType.SALES_TAX
        )
        assert adjustment.amount == Decimal("40.0000000000")
        untaxed_line_item = invoice.line_items.get(name="Professional services")
        assert untaxed_line_item.adjustments.count() == 0

    def test_create_one_off_invoice_no_line_items(self, invoice_test_common_setup):
        setup_dict = invoice_test_common_setup(auth_method="api_key")
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "currency_code": "USD",
            "line_items": [],
        }
        response = setup_dict["client"].post(
            reverse("invoice-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_one_off_invoice_nonpositive_amount(self, invoice_test_common_setup):
        setup_dict = invoice_test_common_setup(auth_method="api_key")
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "currency_code": "USD",
            "line_items": [{"name": "Bad line item", "amount": "0.00"}],
        }
        response = setup_dict["client"].post(
            reverse("invoice-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_one_off_invoice_negative_tax_rate(self, invoice_test_common_setup):
        setup_dict = invoice_test_common_setup(auth_method="api_key")
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "currency_code": "USD",
            "line_items": [{"name": "Bad tax", "amount": "10.00", "tax_rate": "-5"}],
        }
        response = setup_dict["client"].post(
            reverse("invoice-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_one_off_invoice_due_before_issue(self, invoice_test_common_setup):
        setup_dict = invoice_test_common_setup(auth_method="api_key")
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "currency_code": "USD",
            "issue_date": now_utc(),
            "due_date": now_utc() - timedelta(days=1),
            "line_items": [{"name": "Setup fee", "amount": "100.00"}],
        }
        response = setup_dict["client"].post(
            reverse("invoice-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_one_off_invoice_wrong_org_customer(
        self, invoice_test_common_setup, add_customers_to_org
    ):
        setup_dict = invoice_test_common_setup(auth_method="api_key")
        (other_org_customer,) = add_customers_to_org(setup_dict["org2"], n=1)
        payload = {
            "customer_id": other_org_customer.customer_id,
            "currency_code": "USD",
            "line_items": [{"name": "Setup fee", "amount": "100.00"}],
        }
        response = setup_dict["client"].post(
            reverse("invoice-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_one_off_invoice_send_to_processor(self, invoice_test_common_setup):
        setup_dict = invoice_test_common_setup(auth_method="api_key")
        setup_dict["customer"].payment_provider = "stripe"
        setup_dict["customer"].save()
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "currency_code": "USD",
            "line_items": [{"name": "Setup fee", "amount": "100.00"}],
        }
        with mock.patch(
            "metering_billing.invoice.generate_external_payment_obj"
        ) as mock_send:
            response = setup_dict["client"].post(
                reverse("invoice-list"),
                data=json.dumps(payload, cls=DjangoJSONEncoder),
                content_type="application/json",
            )
        assert response.status_code == status.HTTP_201_CREATED
        mock_send.assert_called_once()

    def test_get_and_send_created_invoice(self, invoice_test_common_setup):
        setup_dict = invoice_test_common_setup(auth_method="api_key")
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "currency_code": "USD",
            "line_items": [{"name": "Setup fee", "amount": "100.00"}],
        }
        response = setup_dict["client"].post(
            reverse("invoice-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        invoice_id = response.data["invoice_id"]

        get_response = setup_dict["client"].get(
            reverse("invoice-detail", kwargs={"invoice_id": invoice_id})
        )
        assert get_response.status_code == status.HTTP_200_OK

        send_response = setup_dict["client"].post(
            reverse("invoice-send", kwargs={"invoice_id": invoice_id})
        )
        assert send_response.status_code == status.HTTP_200_OK


@pytest.mark.django_db(transaction=True)
class TestInvoiceTask:
    def test_call_invoice_on_subscription_end(self, invoice_test_common_setup):
        setup_dict = invoice_test_common_setup(auth_method="api_key")
        mock_date = setup_dict["subscription_record"].end_date + relativedelta(
            minutes=30, seconds=1
        )
        invoices_before = len(Invoice.objects.all())
        with (
            mock.patch(
                "metering_billing.tasks.now_utc",
                return_value=mock_date,
            ),
            mock.patch(
                "metering_billing.invoice.now_utc",
                return_value=mock_date,
            ),
        ):
            calculate_invoice_inner()
        invoices_after = len(Invoice.objects.all())
        assert invoices_after == invoices_before + 1

    def test_call_invoice_on_intermediate_billing_record(
        self, invoice_test_common_setup
    ):
        setup_dict = invoice_test_common_setup(
            auth_method="api_key", make_plan_yearly=True
        )
        sr_start_plus_month = (
            setup_dict["subscription_record"].start_date
            + relativedelta(months=1)
            + relativedelta(minutes=30, seconds=1)
        )
        assert sr_start_plus_month < setup_dict["subscription_record"].end_date
        mock_date = sr_start_plus_month + relativedelta(minutes=30)
        invoices_before = len(Invoice.objects.all())
        with (
            mock.patch(
                "metering_billing.tasks.now_utc",
                return_value=mock_date,
            ),
            mock.patch(
                "metering_billing.invoice.now_utc",
                return_value=mock_date,
            ),
        ):
            calculate_invoice_inner()
        invoices_after = len(Invoice.objects.all())
        assert invoices_after == invoices_before + 1
