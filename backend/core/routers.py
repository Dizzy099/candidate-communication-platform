from rest_framework.routers import SimpleRouter


class OptionalSlashRouter(SimpleRouter):
    """Routes match with or without a trailing slash (``/api/candidates`` and ``/api/candidates/``)."""

    def __init__(self):
        super().__init__()
        self.trailing_slash = "/?"
