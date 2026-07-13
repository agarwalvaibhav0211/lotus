"""
Tests for the Munim payment processor integration.

All HTTP calls to the Munim API are mocked via unittest.mock.patch so
these tests run offline without a real Munim instance. Munim credentials
are per-organization (stored, encrypted, on MunimOrganizationIntegration)
rather than a single instance-wide API key.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from rest_framework import status

from metering_billing.models import (
    Customer,
    Invoice,
    InvoiceLineItem,
    MunimCustomerIntegration,
    MunimOrganizationIntegration,
    Organization,
    PricingUnit,
)
from metering_billing.payment_processors import MunimConnector
from metering_billing.utils.enums import PAYMENT_PROCESSORS

# ─────────────────────────────────────────────────────────────────────────────
# Helpers / shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

MUNIM_ACCOUNT_ID = "munim_acct_test123"
MUNIM_CUSTOMER_ID = "munim_cust_abc"
MUNIM_INVOICE_ID = "munim_inv_xyz"


def _make_connector():
    """Return a plain MunimConnector (no per-instance credentials anymore)."""
    return MunimConnector()


def _connect_org_to_munim(
    org, api_key="test-munim-key", account_id=MUNIM_ACCOUNT_ID, account_name="Test Org"
):
    """Attach a MunimOrganizationIntegration (per-org credentials) to an org."""
    integration = MunimOrganizationIntegration.objects.create(
        organization=org,
        api_key=api_key,
        account_id=account_id,
        account_name=account_name,
    )
    org.munim_integration = integration
    org.save()
    return integration


def _make_munim_customer_response(**kwargs):
    """Minimal Munim customer payload as returned by GET /customers/{id}."""
    base = {
        "customerId": MUNIM_CUSTOMER_ID,
        "name": "Test Customer",
        "email": "test@example.com",
        "billingAddress": {
            "line1": "1 Test St",
            "line2": None,
            "city": "Karachi",
            "state": "Sindh",
            "postalCode": "75500",
            "country": "PK",
        },
        "shippingAddress": None,
    }
    base.update(kwargs)
    return base


def _make_munim_invoice_response(invoice_status="paid"):
    return {
        "invoiceId": MUNIM_INVOICE_ID,
        "customerId": MUNIM_CUSTOMER_ID,
        "amount": 100.00,
        "currency": "USD",
        "status": invoice_status,
        "lineItems": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fixture that assembles org + customer + integration objects
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def munim_setup(generate_org_and_api_key, add_customers_to_org):
    org, _ = generate_org_and_api_key()
    org.gen_cust_in_munim_after_lotus = True
    org.save()

    (customer,) = add_customers_to_org(org, n=1)
    customer.email = "test@example.com"
    customer.save()

    _connect_org_to_munim(org)

    connector = _make_connector()

    return {
        "org": org,
        "customer": customer,
        "connector": connector,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Connector management methods
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimConnectorManagement:
    def test_working_returns_true_when_org_connected(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        assert connector.working(org) is True

    def test_working_returns_false_when_no_organization_given(self):
        connector = _make_connector()
        assert connector.working() is False

    def test_working_returns_false_when_org_not_connected(
        self, generate_org_and_api_key
    ):
        connector = _make_connector()
        org, _ = generate_org_and_api_key()
        assert connector.working(org) is False

    def test_working_returns_false_when_account_id_missing(
        self, generate_org_and_api_key
    ):
        connector = _make_connector()
        org, _ = generate_org_and_api_key()
        _connect_org_to_munim(org, account_id=None)
        assert connector.working(org) is False

    def test_customer_connected_false_without_integration(self, munim_setup):
        connector = munim_setup["connector"]
        customer = munim_setup["customer"]
        assert connector.customer_connected(customer) is False

    def test_customer_connected_true_with_integration(self, munim_setup):
        connector = munim_setup["connector"]
        customer = munim_setup["customer"]
        org = munim_setup["org"]

        integration = MunimCustomerIntegration.objects.create(
            organization=org, munim_customer_id=MUNIM_CUSTOMER_ID
        )
        customer.munim_integration = integration
        customer.save()

        assert connector.customer_connected(customer) is True

    def test_organization_connected_false_without_integration(
        self, generate_org_and_api_key
    ):
        connector = _make_connector()
        org, _ = generate_org_and_api_key()
        assert connector.organization_connected(org) is False

    def test_organization_connected_true_with_integration(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        assert connector.organization_connected(org) is True

    def test_get_connection_id_returns_org_uuid(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        assert connector.get_connection_id(org) == org.organization_id.hex

    def test_get_account_id_returns_orgs_account_id(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        assert connector.get_account_id(org) == MUNIM_ACCOUNT_ID

    def test_get_account_id_returns_none_when_not_connected(
        self, generate_org_and_api_key
    ):
        connector = _make_connector()
        org, _ = generate_org_and_api_key()
        assert connector.get_account_id(org) is None

    def test_get_redirect_url_returns_empty_string(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        assert connector.get_redirect_url(org) == ""


# ─────────────────────────────────────────────────────────────────────────────
# 2. import_customers
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimImportCustomers:
    def test_import_creates_new_customer(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        Customer.objects.filter(organization=org).delete()

        list_response = {
            "customers": [_make_munim_customer_response()],
            "total": 1,
            "page": 1,
            "page_size": 100,
        }

        with patch.object(connector, "_get", return_value=list_response):
            count = connector.import_customers(org)

        assert count == 1
        assert Customer.objects.filter(
            organization=org,
            munim_integration__munim_customer_id=MUNIM_CUSTOMER_ID,
        ).exists()
        new_cust = Customer.objects.get(
            organization=org,
            munim_integration__munim_customer_id=MUNIM_CUSTOMER_ID,
        )
        assert new_cust.payment_provider == PAYMENT_PROCESSORS.MUNIM
        assert new_cust.email == "test@example.com"

    def test_import_updates_existing_customer_by_email(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        customer = munim_setup["customer"]
        # customer already exists in Lotus with matching email
        customer.email = "test@example.com"
        customer.save()

        list_response = {
            "customers": [_make_munim_customer_response(email="test@example.com")],
            "total": 1,
            "page": 1,
            "page_size": 100,
        }

        with patch.object(connector, "_get", return_value=list_response):
            count = connector.import_customers(org)

        # no new customer should be created, existing one updated
        assert count == 0
        customer.refresh_from_db()
        assert customer.payment_provider == PAYMENT_PROCESSORS.MUNIM

    def test_import_handles_api_error_gracefully(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]

        with patch.object(connector, "_get", side_effect=Exception("network error")):
            count = connector.import_customers(org)

        assert count == 0

    def test_import_paginates_through_all_pages(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        Customer.objects.filter(organization=org).delete()

        # total=150 > page_size=100, so connector must fetch a second page
        page1 = {
            "customers": [
                _make_munim_customer_response(
                    customerId="munim_cust_p1",
                    email="p1@example.com",
                )
            ],
            "total": 150,
            "page": 1,
            "page_size": 100,
        }
        page2 = {
            "customers": [
                _make_munim_customer_response(
                    customerId="munim_cust_p2",
                    email="p2@example.com",
                )
            ],
            "total": 150,
            "page": 2,
            "page_size": 100,
        }

        responses = iter([page1, page2])

        with patch.object(connector, "_get", side_effect=responses):
            count = connector.import_customers(org)

        assert count == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. create_customer_flow
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimCreateCustomerFlow:
    def test_creates_customer_in_munim_when_flag_enabled(self, munim_setup):
        connector = munim_setup["connector"]
        customer = munim_setup["customer"]
        org = munim_setup["org"]
        org.gen_cust_in_munim_after_lotus = True
        org.save()

        post_response = {
            "customerId": MUNIM_CUSTOMER_ID,
            "name": customer.customer_name,
            "email": customer.email,
        }

        with patch.object(connector, "_post", return_value=post_response):
            connector.create_customer_flow(customer)

        customer.refresh_from_db()
        assert customer.munim_integration is not None
        assert customer.munim_integration.munim_customer_id == MUNIM_CUSTOMER_ID

    def test_skips_creation_when_flag_disabled(self, munim_setup):
        connector = munim_setup["connector"]
        customer = munim_setup["customer"]
        org = munim_setup["org"]
        org.gen_cust_in_munim_after_lotus = False
        org.save()

        with patch.object(connector, "_post") as mock_post:
            connector.create_customer_flow(customer)
            mock_post.assert_not_called()

        customer.refresh_from_db()
        assert customer.munim_integration is None

    def test_skips_creation_when_already_connected(self, munim_setup):
        connector = munim_setup["connector"]
        customer = munim_setup["customer"]
        org = munim_setup["org"]

        integration = MunimCustomerIntegration.objects.create(
            organization=org, munim_customer_id=MUNIM_CUSTOMER_ID
        )
        customer.munim_integration = integration
        customer.save()

        with patch.object(connector, "_post") as mock_post:
            connector.create_customer_flow(customer)
            mock_post.assert_not_called()

    def test_handles_api_error_gracefully(self, munim_setup):
        connector = munim_setup["connector"]
        customer = munim_setup["customer"]

        with patch.object(connector, "_post", side_effect=Exception("api error")):
            connector.create_customer_flow(customer)  # must not raise

        customer.refresh_from_db()
        assert customer.munim_integration is None


# ─────────────────────────────────────────────────────────────────────────────
# 4. connect_customer
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimConnectCustomer:
    def test_connect_customer_links_integration(self, munim_setup):
        connector = munim_setup["connector"]
        customer = munim_setup["customer"]

        with patch.object(
            connector,
            "retrieve_customer_by_external_id",
            return_value=_make_munim_customer_response(),
        ):
            result = connector.connect_customer(customer, MUNIM_CUSTOMER_ID)

        assert result is True
        customer.refresh_from_db()
        assert customer.munim_integration is not None
        assert customer.munim_integration.munim_customer_id == MUNIM_CUSTOMER_ID

    def test_connect_customer_returns_false_on_api_error(self, munim_setup):
        connector = munim_setup["connector"]
        customer = munim_setup["customer"]

        with patch.object(
            connector,
            "retrieve_customer_by_external_id",
            side_effect=Exception("not found"),
        ):
            result = connector.connect_customer(customer, "bad-id")

        assert result is False
        customer.refresh_from_db()
        assert customer.munim_integration is None


# ─────────────────────────────────────────────────────────────────────────────
# 5. create_payment_object (invoice)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimCreatePaymentObject:
    def _make_invoice(self, org, customer):
        """Create a minimal Invoice + one InvoiceLineItem."""
        currency = PricingUnit.objects.get(organization=org, code="USD")
        invoice = Invoice.objects.create(
            organization=org,
            customer=customer,
            amount=Decimal("100.00"),
            currency=currency,
            payment_status=Invoice.PaymentStatus.UNPAID,
            invoice_number="TEST-001",
        )
        InvoiceLineItem.objects.create(
            organization=org,
            invoice=invoice,
            name="Pro Plan",
            base=Decimal("100.00"),
            amount=Decimal("100.00"),
            quantity=Decimal("1.00"),
        )
        return invoice

    def test_create_payment_object_success(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        customer = munim_setup["customer"]

        # Link a Munim customer integration
        integration = MunimCustomerIntegration.objects.create(
            organization=org, munim_customer_id=MUNIM_CUSTOMER_ID
        )
        customer.munim_integration = integration
        customer.save()

        invoice = self._make_invoice(org, customer)

        post_response = _make_munim_invoice_response(invoice_status="pending")

        with patch.object(connector, "_post", return_value=post_response):
            invoice_id, invoice_status = connector.create_payment_object(invoice)

        assert invoice_id == MUNIM_INVOICE_ID
        assert invoice_status == "pending"
        invoice.refresh_from_db()
        assert invoice.external_payment_obj_id == MUNIM_INVOICE_ID
        assert invoice.external_payment_obj_status == "pending"

    def test_create_payment_object_returns_none_on_api_error(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        customer = munim_setup["customer"]

        integration = MunimCustomerIntegration.objects.create(
            organization=org, munim_customer_id=MUNIM_CUSTOMER_ID
        )
        customer.munim_integration = integration
        customer.save()

        invoice = self._make_invoice(org, customer)

        with patch.object(connector, "_post", side_effect=Exception("server error")):
            invoice_id, invoice_status = connector.create_payment_object(invoice)

        assert invoice_id is None
        assert invoice_status is None

    def test_create_payment_object_asserts_no_existing_external_id(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        customer = munim_setup["customer"]

        integration = MunimCustomerIntegration.objects.create(
            organization=org, munim_customer_id=MUNIM_CUSTOMER_ID
        )
        customer.munim_integration = integration
        customer.save()

        invoice = self._make_invoice(org, customer)
        invoice.external_payment_obj_id = "already-exists"
        invoice.save()

        with pytest.raises(AssertionError, match="already has an external ID"):
            connector.create_payment_object(invoice)

    def test_create_payment_object_sends_correct_payload(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        customer = munim_setup["customer"]

        integration = MunimCustomerIntegration.objects.create(
            organization=org, munim_customer_id=MUNIM_CUSTOMER_ID
        )
        customer.munim_integration = integration
        customer.save()

        invoice = self._make_invoice(org, customer)

        post_response = _make_munim_invoice_response(invoice_status="processing")

        with patch.object(connector, "_post", return_value=post_response) as mock_post:
            connector.create_payment_object(invoice)

        _, call_kwargs = mock_post.call_args
        payload = call_kwargs["payload"]
        assert payload["customerId"] == MUNIM_CUSTOMER_ID
        assert payload["amount"] == 100.00
        assert len(payload["lineItems"]) == 1
        assert payload["lineItems"][0]["kind"] == "debit"
        assert payload["lineItems"][0]["name"] == "Pro Plan"


# ─────────────────────────────────────────────────────────────────────────────
# 6. update_payment_object_status
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimUpdatePaymentObjectStatus:
    def test_returns_paid_when_status_is_paid(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]

        with patch.object(
            connector, "_get", return_value=_make_munim_invoice_response("paid")
        ):
            result = connector.update_payment_object_status(org, MUNIM_INVOICE_ID)

        assert result == Invoice.PaymentStatus.PAID

    def test_returns_unpaid_when_status_is_pending(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]

        with patch.object(
            connector, "_get", return_value=_make_munim_invoice_response("pending")
        ):
            result = connector.update_payment_object_status(org, MUNIM_INVOICE_ID)

        assert result == Invoice.PaymentStatus.UNPAID

    def test_returns_unpaid_on_api_error(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]

        with patch.object(connector, "_get", side_effect=Exception("network error")):
            result = connector.update_payment_object_status(org, MUNIM_INVOICE_ID)

        assert result == Invoice.PaymentStatus.UNPAID


# ─────────────────────────────────────────────────────────────────────────────
# 7. retrieve_customer_by_external_id
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimRetrieveCustomer:
    def test_returns_customer_data(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        expected = _make_munim_customer_response()

        with patch.object(connector, "_get", return_value=expected):
            result = connector.retrieve_customer_by_external_id(org, MUNIM_CUSTOMER_ID)

        assert result == expected
        assert result["customerId"] == MUNIM_CUSTOMER_ID

    def test_returns_none_on_api_error(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]

        with patch.object(connector, "_get", side_effect=Exception("404")):
            result = connector.retrieve_customer_by_external_id(org, "bad-id")

        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# 8. has_payment_method
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimHasPaymentMethod:
    def test_always_returns_false(self, munim_setup):
        # Munim does not support auto-charge
        connector = munim_setup["connector"]
        customer = munim_setup["customer"]
        assert connector.has_payment_method(customer) is False


# ─────────────────────────────────────────────────────────────────────────────
# 9. get_customer_address
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimGetCustomerAddress:
    def test_billing_address_returned(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]
        customer = munim_setup["customer"]

        integration = MunimCustomerIntegration.objects.create(
            organization=org, munim_customer_id=MUNIM_CUSTOMER_ID
        )
        customer.munim_integration = integration
        customer.save()

        cust_data = _make_munim_customer_response()

        with patch.object(connector, "_get", return_value=cust_data):
            address = connector.get_customer_address(customer, "billing")

        assert address.city == "Karachi"
        assert address.country == "PK"
        assert address.line1 == "1 Test St"
        assert address.postal_code == "75500"

    def test_returns_empty_address_on_api_error(self, munim_setup):
        from metering_billing.models import Address

        connector = munim_setup["connector"]
        org = munim_setup["org"]
        customer = munim_setup["customer"]

        integration = MunimCustomerIntegration.objects.create(
            organization=org, munim_customer_id=MUNIM_CUSTOMER_ID
        )
        customer.munim_integration = integration
        customer.save()

        with patch.object(connector, "_get", side_effect=Exception("error")):
            address = connector.get_customer_address(customer, "billing")

        assert isinstance(address, Address)


# ─────────────────────────────────────────────────────────────────────────────
# 10. get_organization_address
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimGetOrganizationAddress:
    def test_returns_account_address(self, munim_setup):
        connector = munim_setup["connector"]
        org = munim_setup["org"]

        acct_data = {
            "account_id": MUNIM_ACCOUNT_ID,
            "name": "Test Org",
            "address": {
                "line1": "99 Business Ave",
                "line2": "Floor 5",
                "city": "Lahore",
                "state": "Punjab",
                "postal_code": "54000",
                "country": "PK",
            },
        }

        with patch.object(connector, "_get", return_value=acct_data):
            address = connector.get_organization_address(org)

        assert address.city == "Lahore"
        assert address.line1 == "99 Business Ave"
        assert address.country == "PK"

    def test_returns_empty_address_on_api_error(self, munim_setup):
        from metering_billing.models import Address

        connector = munim_setup["connector"]
        org = munim_setup["org"]

        with patch.object(connector, "_get", side_effect=Exception("error")):
            address = connector.get_organization_address(org)

        assert isinstance(address, Address)


# ─────────────────────────────────────────────────────────────────────────────
# 11. handle_post (connect org to Munim from frontend, with an org-supplied key)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimHandlePost:
    def test_handle_post_creates_integration_and_returns_success(
        self, generate_org_and_api_key
    ):
        connector = _make_connector()
        org, _ = generate_org_and_api_key()

        account_response = MagicMock()
        account_response.raise_for_status = lambda: None
        account_response.json = lambda: {
            "accountId": MUNIM_ACCOUNT_ID,
            "name": "Test Org",
        }

        with patch(
            "metering_billing.payment_processors.requests.get",
            return_value=account_response,
        ):
            response = connector.handle_post({"api_key": "new-org-key"}, org)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert response.data["payment_processor"] == PAYMENT_PROCESSORS.MUNIM

        org.refresh_from_db()
        assert org.munim_integration is not None
        assert org.munim_integration.api_key == "new-org-key"
        assert org.munim_integration.account_id == MUNIM_ACCOUNT_ID

    def test_handle_post_is_idempotent(self, generate_org_and_api_key):
        """Calling handle_post twice must not create a duplicate integration."""
        connector = _make_connector()
        org, _ = generate_org_and_api_key()

        account_response = MagicMock()
        account_response.raise_for_status = lambda: None
        account_response.json = lambda: {
            "accountId": MUNIM_ACCOUNT_ID,
            "name": "Test Org",
        }

        with patch(
            "metering_billing.payment_processors.requests.get",
            return_value=account_response,
        ):
            connector.handle_post({"api_key": "new-org-key"}, org)
            response = connector.handle_post({"api_key": "new-org-key"}, org)

        assert response.status_code == status.HTTP_200_OK
        assert (
            MunimOrganizationIntegration.objects.filter(organization=org).count() == 1
        )

    def test_handle_post_returns_400_when_api_key_invalid(
        self, generate_org_and_api_key
    ):
        """If the org-supplied API key fails Munim's own validation, reject the connect."""
        connector = _make_connector()
        org, _ = generate_org_and_api_key()

        with patch(
            "metering_billing.payment_processors.requests.get",
            side_effect=Exception("unauthorized"),
        ):
            response = connector.handle_post({"api_key": "bad-key"}, org)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["success"] is False

        org.refresh_from_db()
        assert org.munim_integration is None


# ─────────────────────────────────────────────────────────────────────────────
# 12. get_post_data_serializer
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimGetPostDataSerializer:
    def test_serializer_requires_api_key(self):
        connector = _make_connector()
        SerializerClass = connector.get_post_data_serializer()

        empty_serializer = SerializerClass(data={})
        assert not empty_serializer.is_valid()
        assert "api_key" in empty_serializer.errors

        filled_serializer = SerializerClass(data={"api_key": "some-key"})
        assert filled_serializer.is_valid()


# ─────────────────────────────────────────────────────────────────────────────
# 13. PAYMENT_PROCESSOR_MAP registration
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMunimRegisteredInProcessorMap:
    def test_munim_in_payment_processor_map(self):
        from metering_billing.payment_processors import PAYMENT_PROCESSOR_MAP

        assert PAYMENT_PROCESSORS.MUNIM in PAYMENT_PROCESSOR_MAP

    def test_registered_connector_is_munim_connector(self):
        from metering_billing.payment_processors import PAYMENT_PROCESSOR_MAP

        connector = PAYMENT_PROCESSOR_MAP[PAYMENT_PROCESSORS.MUNIM]
        assert isinstance(connector, MunimConnector)


# ─────────────────────────────────────────────────────────────────────────────
# 14. munim_webhook_endpoint
# ─────────────────────────────────────────────────────────────────────────────

from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestMunimWebhookEndpoint:
    def _make_invoice(self, org, customer, payment_status=Invoice.PaymentStatus.UNPAID):
        currency = PricingUnit.objects.get(organization=org, code="USD")
        invoice = Invoice.objects.create(
            organization=org,
            customer=customer,
            amount=Decimal("100.00"),
            currency=currency,
            payment_status=payment_status,
            invoice_number="TEST-WEBHOOK-001",
            external_payment_obj_type=PAYMENT_PROCESSORS.MUNIM,
            external_payment_obj_id=MUNIM_INVOICE_ID,
        )
        InvoiceLineItem.objects.create(
            organization=org,
            invoice=invoice,
            name="Pro Plan",
            base=Decimal("100.00"),
            amount=Decimal("100.00"),
            quantity=Decimal("1.00"),
        )
        return invoice

    def _post(self, client, token, body):
        headers = {}
        if token is not None:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return client.post(
            reverse("munim-webhook"), data=body, format="json", **headers
        )

    def test_missing_bearer_token_returns_401(self, munim_setup):
        client = APIClient()
        response = self._post(
            client, None, {"invoice_id": MUNIM_INVOICE_ID, "status": "paid"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_bearer_token_returns_401(self, munim_setup):
        integration = MunimOrganizationIntegration.objects.get(
            organization=munim_setup["org"]
        )
        integration.webhook_secret = "correct-secret"
        integration.save()

        client = APIClient()
        response = self._post(
            client,
            "wrong-secret",
            {"invoice_id": MUNIM_INVOICE_ID, "status": "paid"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_token_updates_matching_invoice_to_paid(self, munim_setup):
        org = munim_setup["org"]
        customer = munim_setup["customer"]
        integration = MunimOrganizationIntegration.objects.get(organization=org)
        integration.webhook_secret = "correct-secret"
        integration.save()

        invoice = self._make_invoice(org, customer)

        client = APIClient()
        with patch(
            "metering_billing.views.webhook_views.kafka_producer"
        ) as mock_kafka:
            response = self._post(
                client,
                "correct-secret",
                {"invoice_id": MUNIM_INVOICE_ID, "status": "paid"},
            )
            assert response.status_code == status.HTTP_200_OK
            invoice.refresh_from_db()
            assert invoice.payment_status == Invoice.PaymentStatus.PAID
            mock_kafka.produce_invoice_pay_in_full.assert_called_once()

    def test_unknown_invoice_id_is_noop_200(self, munim_setup):
        org = munim_setup["org"]
        integration = MunimOrganizationIntegration.objects.get(organization=org)
        integration.webhook_secret = "correct-secret"
        integration.save()

        client = APIClient()
        response = self._post(
            client,
            "correct-secret",
            {"invoice_id": "does-not-exist", "status": "paid"},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_already_paid_invoice_is_idempotent(self, munim_setup):
        org = munim_setup["org"]
        customer = munim_setup["customer"]
        integration = MunimOrganizationIntegration.objects.get(organization=org)
        integration.webhook_secret = "correct-secret"
        integration.save()

        invoice = self._make_invoice(
            org, customer, payment_status=Invoice.PaymentStatus.PAID
        )

        client = APIClient()
        with patch(
            "metering_billing.views.webhook_views.kafka_producer"
        ) as mock_kafka:
            response = self._post(
                client,
                "correct-secret",
                {"invoice_id": MUNIM_INVOICE_ID, "status": "paid"},
            )
            assert response.status_code == status.HTTP_200_OK
            mock_kafka.produce_invoice_pay_in_full.assert_not_called()

    def test_token_valid_for_other_org_does_not_leak_invoice(
        self, munim_setup, generate_org_and_api_key, add_customers_to_org
    ):
        org_a = munim_setup["org"]
        customer_a = munim_setup["customer"]
        integration_a = MunimOrganizationIntegration.objects.get(organization=org_a)
        integration_a.webhook_secret = "org-a-secret"
        integration_a.save()

        org_b, _ = generate_org_and_api_key()
        (customer_b,) = add_customers_to_org(org_b, n=1)
        _connect_org_to_munim(org_b, api_key="org-b-key", account_id="acct-b")
        integration_b = MunimOrganizationIntegration.objects.get(organization=org_b)
        integration_b.webhook_secret = "org-b-secret"
        integration_b.save()

        # Invoice belongs to org_b, but caller authenticates as org_a.
        invoice = self._make_invoice(org_b, customer_b)

        client = APIClient()
        response = self._post(
            client,
            "org-a-secret",
            {"invoice_id": MUNIM_INVOICE_ID, "status": "paid"},
        )
        assert response.status_code == status.HTTP_200_OK
        invoice.refresh_from_db()
        assert invoice.payment_status == Invoice.PaymentStatus.UNPAID


@pytest.mark.django_db
class TestMunimRegenerateWebhookSecret:
    def _post(self, client):
        return client.post(reverse("munim_regenerate_webhook_secret"))

    def test_regenerate_returns_new_secret_and_updates_lookup(
        self, munim_setup, add_users_to_org
    ):
        org = munim_setup["org"]
        (user,) = add_users_to_org(org, 1)
        integration = MunimOrganizationIntegration.objects.get(organization=org)
        integration.webhook_secret = "old-secret"
        integration.save()
        old_lookup = integration.webhook_secret_lookup

        client = APIClient()
        client.force_authenticate(user=user)
        response = self._post(client)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["webhook_path"] == "/api/munim/webhook/"
        new_secret = response.data["webhook_secret"]
        assert new_secret and new_secret != "old-secret"

        integration.refresh_from_db()
        assert integration.webhook_secret_lookup != old_lookup

    def test_regenerate_without_connection_returns_400(self, add_users_to_org):
        from metering_billing.models import Organization

        org = Organization.objects.create(organization_name="No Munim Org")
        (user,) = add_users_to_org(org, 1)

        client = APIClient()
        client.force_authenticate(user=user)
        response = self._post(client)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_regenerate_requires_authentication(self):
        client = APIClient()
        response = self._post(client)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
