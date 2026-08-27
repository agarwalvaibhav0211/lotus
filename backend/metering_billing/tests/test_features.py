import json

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from metering_billing.models import Feature, PlanVersion
from metering_billing.serializers.serializer_utils import DjangoJSONEncoder


@pytest.fixture
def feature_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    add_product_to_org,
    add_plan_to_product,
):
    def do_feature_test_common_setup():
        org, key = generate_org_and_api_key()
        org2, key2 = generate_org_and_api_key()
        client = APIClient()
        (user,) = add_users_to_org(org, n=1)
        client.force_authenticate(user=user)

        feature = Feature.objects.create(
            feature_name="test_feature",
            feature_description="test_description",
            organization=org,
        )
        return {
            "org": org,
            "org2": org2,
            "user": user,
            "client": client,
            "feature": feature,
            "product": add_product_to_org(org),
        }

    return do_feature_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestUpdateFeature:
    def test_update_name_and_description(self, feature_test_common_setup):
        setup_dict = feature_test_common_setup()
        feature = setup_dict["feature"]

        payload = {
            "feature_name": "renamed_feature",
            "feature_description": "new_description",
        }
        response = setup_dict["client"].patch(
            reverse("feature-detail", kwargs={"feature_id": feature.feature_id}),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["feature_name"] == "renamed_feature"
        assert response.data["feature_description"] == "new_description"
        feature.refresh_from_db()
        assert feature.feature_name == "renamed_feature"
        assert feature.feature_description == "new_description"

    def test_update_description_only_leaves_name_alone(self, feature_test_common_setup):
        setup_dict = feature_test_common_setup()
        feature = setup_dict["feature"]

        payload = {"feature_description": "only_the_description_changed"}
        response = setup_dict["client"].patch(
            reverse("feature-detail", kwargs={"feature_id": feature.feature_id}),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        feature.refresh_from_db()
        assert feature.feature_name == "test_feature"
        assert feature.feature_description == "only_the_description_changed"

    def test_update_to_duplicate_name_in_org_fails(self, feature_test_common_setup):
        setup_dict = feature_test_common_setup()
        feature = setup_dict["feature"]
        Feature.objects.create(
            feature_name="taken_name",
            feature_description="other",
            organization=setup_dict["org"],
        )

        payload = {"feature_name": "taken_name"}
        response = setup_dict["client"].patch(
            reverse("feature-detail", kwargs={"feature_id": feature.feature_id}),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        feature.refresh_from_db()
        assert feature.feature_name == "test_feature"

    def test_duplicate_name_in_other_org_is_allowed(self, feature_test_common_setup):
        setup_dict = feature_test_common_setup()
        feature = setup_dict["feature"]
        Feature.objects.create(
            feature_name="taken_in_org2",
            feature_description="other",
            organization=setup_dict["org2"],
        )

        payload = {"feature_name": "taken_in_org2"}
        response = setup_dict["client"].patch(
            reverse("feature-detail", kwargs={"feature_id": feature.feature_id}),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        feature.refresh_from_db()
        assert feature.feature_name == "taken_in_org2"

    def test_cannot_update_feature_in_another_org(self, feature_test_common_setup):
        setup_dict = feature_test_common_setup()
        other_org_feature = Feature.objects.create(
            feature_name="org2_feature",
            feature_description="org2_description",
            organization=setup_dict["org2"],
        )

        payload = {"feature_name": "hijacked"}
        response = setup_dict["client"].patch(
            reverse(
                "feature-detail",
                kwargs={"feature_id": other_org_feature.feature_id},
            ),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        other_org_feature.refresh_from_db()
        assert other_org_feature.feature_name == "org2_feature"

    def test_rename_propagates_to_attached_plan_versions(
        self, feature_test_common_setup, add_plan_to_product
    ):
        setup_dict = feature_test_common_setup()
        feature = setup_dict["feature"]
        plan = add_plan_to_product(setup_dict["product"])
        version = PlanVersion.objects.create(
            organization=setup_dict["org"],
            plan=plan,
            localized_name="v1",
        )
        version.features.add(feature)

        payload = {"feature_name": "renamed_feature"}
        response = setup_dict["client"].patch(
            reverse("feature-detail", kwargs={"feature_id": feature.feature_id}),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        # the M2M points at the same row, so live versions see the new name
        assert version.features.first().feature_name == "renamed_feature"
