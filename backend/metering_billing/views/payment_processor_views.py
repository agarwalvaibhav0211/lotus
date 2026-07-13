import secrets

from django.conf import settings
from drf_spectacular.utils import extend_schema
from metering_billing.payment_processors import PAYMENT_PROCESSOR_MAP
from metering_billing.permissions import ValidOrganization
from metering_billing.utils.enums import PAYMENT_PROCESSORS
from metering_billing.serializers.payment_processor_serializers import (
    MunimWebhookSecretResponseSerializer,
    PaymentProcesorPostRequestSerializer,
    PaymentProcesorPostResponseSerializer,
    SinglePaymentProcesorSerializer,
)
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

SELF_HOSTED = settings.SELF_HOSTED


class PaymentProcesorView(APIView):
    permission_classes = [IsAuthenticated & ValidOrganization]

    @extend_schema(
        request=None,
        responses={200: SinglePaymentProcesorSerializer(many=True)},
    )
    def get(self, request, format=None):
        organization = request.organization
        response = []
        for payment_processor_name, pp_obj in PAYMENT_PROCESSOR_MAP.items():
            # Munim has its own UI connect flow (per-org API key) regardless of
            # whether this Lotus instance is self-hosted, unlike Stripe/Braintree's
            # OAuth flows which need to be disabled in self-hosted deployments.
            self_hosted = (
                False if payment_processor_name == PAYMENT_PROCESSORS.MUNIM else SELF_HOSTED
            )
            pp_response = {
                "payment_provider_name": payment_processor_name,
                "working": pp_obj.working(organization),
                "connected": pp_obj.organization_connected(organization),
                "redirect_url": pp_obj.get_redirect_url(organization),
                "self_hosted": self_hosted,
                "connection_id": pp_obj.get_connection_id(organization),
                "account_id": pp_obj.get_account_id(organization),
            }
            response.append(pp_response)
        serializer = SinglePaymentProcesorSerializer(data=response, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    @extend_schema(
        request=PaymentProcesorPostRequestSerializer,
        responses={200: PaymentProcesorPostResponseSerializer},
    )
    def post(self, request, format=None):
        organization = request.organization
        # parse outer level request
        serializer = PaymentProcesorPostRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment_processor_name = serializer.validated_data["pp_info"][
            "payment_processor"
        ]
        data = serializer.validated_data["pp_info"]["data"]
        # validate payment processor specific data
        data_serializer = PAYMENT_PROCESSOR_MAP[
            payment_processor_name
        ].get_post_data_serializer()
        data_serializer = data_serializer(data=data)
        data_serializer.is_valid(raise_exception=True)
        data = data_serializer.validated_data

        # call payment processor specific post method
        response = PAYMENT_PROCESSOR_MAP[payment_processor_name].handle_post(
            data, organization
        )

        return response


class MunimWebhookSecretView(APIView):
    """
    Rotates the Munim webhook secret for the organization's existing
    integration. Since the secret is only ever returned once (at generation
    time), this is how a user retrieves it again if lost, or replaces it if
    compromised.
    """

    permission_classes = [IsAuthenticated & ValidOrganization]

    @extend_schema(
        request=None,
        responses={200: MunimWebhookSecretResponseSerializer},
    )
    def post(self, request, format=None):
        from metering_billing.models import MunimOrganizationIntegration

        organization = request.organization
        integration = MunimOrganizationIntegration.objects.filter(
            organizations=organization
        ).first()
        if integration is None:
            return Response(
                {"detail": "Organization is not connected to Munim"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        integration.webhook_secret = secrets.token_urlsafe(32)
        integration.save()

        response = {
            "webhook_path": "/api/munim/webhook/",
            "webhook_secret": integration.webhook_secret,
        }
        serializer = MunimWebhookSecretResponseSerializer(data=response)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
