from django.urls import path

from sim import views

urlpatterns = [
    path("v1/messages", views.submit_message, name="submit-message"),
    path("v1/messages/<str:message_id>", views.message_detail, name="message-detail"),
    path("v1/health", views.health, name="health"),
    path("v1/simulator/outage", views.set_outage, name="set-outage"),
]
