from django.contrib import admin
from django.urls import include, path, re_path

from candidates.views import CandidateViewSet
from core.routers import OptionalSlashRouter
from messaging import views as messaging_views

# Optional trailing slash: works with and without it (the Next.js proxy drops it).
router = OptionalSlashRouter()
router.register("candidates", CandidateViewSet, basename="candidate")
router.register("message-batches", messaging_views.BatchViewSet, basename="message-batch")
router.register("templates", messaging_views.TemplateViewSet, basename="template")

message_detail = messaging_views.MessageViewSet.as_view({"get": "retrieve"})
message_retry = messaging_views.MessageViewSet.as_view({"post": "retry"})
message_cancel = messaging_views.MessageViewSet.as_view({"post": "cancel"})

api_patterns = [
    re_path(r"^health/?$", messaging_views.health, name="health"),
    re_path(r"^candidates/(?P<candidate_id>\d+)/messages/?$", messaging_views.CandidateMessagesView.as_view(), name="candidate-messages"),
    re_path(r"^messages/(?P<pk>[0-9a-f-]{36})/?$", message_detail, name="message-detail"),
    re_path(r"^messages/(?P<pk>[0-9a-f-]{36})/retry/?$", message_retry, name="message-retry"),
    re_path(r"^messages/(?P<pk>[0-9a-f-]{36})/cancel/?$", message_cancel, name="message-cancel"),
    re_path(r"^template-variables/?$", messaging_views.template_variables, name="template-variables"),
    re_path(r"^provider/health/?$", messaging_views.ProviderHealthView.as_view(), name="provider-health"),
    re_path(r"^provider/simulator/outage/?$", messaging_views.SimulatorOutageView.as_view(), name="simulator-outage"),
    re_path(r"^webhooks/provider/(?P<provider_name>[a-z0-9_-]+)/?$", messaging_views.provider_webhook, name="provider-webhook"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns + router.urls)),
]
