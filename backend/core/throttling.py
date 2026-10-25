from rest_framework.throttling import SimpleRateThrottle


class WriteRateThrottle(SimpleRateThrottle):
    """Throttle unsafe methods per client IP; reads stay unthrottled for polling."""

    scope = "writes"

    def get_cache_key(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
