import logging
import re

from django.core.cache import cache
from metering_billing.models import APIToken, Organization
from metering_billing.permissions import HasUserAPIKey
from metering_billing.utils import now_utc

logger = logging.getLogger("django.server")

_BRACKET_KEY_RE = re.compile(r"^(?P<base>.+?)(\[\]|\[\d*\])$")


class QueryParamArrayNormalizationMiddleware:
    """
    Some HTTP clients (e.g. axios's default paramsSerializer) serialize array
    query params as repeated `key[]=` or indexed `key[0]=` entries rather than
    plain repeated `key=a&key=b`. DRF's ListField only picks up values via
    QueryDict.getlist(field_name) on the bare key, so those forms are
    silently dropped. Normalize them onto the bare key here, once, for every
    view, instead of requiring each view/serializer to handle it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        query_dict = request.GET
        bracket_keys = [k for k in query_dict.keys() if _BRACKET_KEY_RE.match(k)]
        if bracket_keys:
            query_dict._mutable = True
            for key in bracket_keys:
                base = _BRACKET_KEY_RE.match(key).group("base")
                values = query_dict.pop(key)
                query_dict.setlist(base, query_dict.getlist(base) + values)
            query_dict._mutable = False
        return self.get_response(request)


class OrganizationInsertMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if request.user.is_authenticated:
                organization = request.user.organization
            else:
                api_key_checker = HasUserAPIKey()
                api_key = api_key_checker.get_key(request)
                if api_key is None:
                    organization = None
                else:
                    organization_pk = cache.get(api_key)
                    if not organization_pk:
                        try:
                            api_token = APIToken.objects.get_from_key(api_key)
                            organization = api_token.organization
                            organization_pk = api_token.organization.pk
                            expiry_date = api_token.expiry_date
                            timeout = (
                                60 * 60 * 24
                                if expiry_date is None
                                else (expiry_date - now_utc()).total_seconds()
                            )
                            cache.set(api_key, organization_pk, timeout)
                        except Exception:
                            organization = None
                    else:
                        organization = Organization.objects.get(pk=organization_pk)
            logger.debug(
                f"OrganizationInsertMiddleware: {organization}, {request.user}"
            )
            request.organization = organization
        except Exception as e:
            logger.error(f"OrganizationInsertMiddleware: {e}")
            request.organization = None
            pass
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        response = self.get_response(request)

        return response
