from rest_framework import status
from rest_framework.exceptions import APIException


class UpstreamError(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "An upstream service failed. Please try again."
    default_code = "upstream_error"


class UpstreamRateLimited(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "A data provider's rate limit was reached. Please retry in a minute."
    default_code = "upstream_rate_limited"


class NoRouteFound(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "No truck route could be found between these places."
    default_code = "no_route"


class NotConfigured(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The server is missing an API key."
    default_code = "not_configured"
