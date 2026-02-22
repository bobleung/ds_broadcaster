from django.urls import path

from . import views

app_name = "ds_broadcaster"

urlpatterns = [
    path("test/", views.test_page, name="test"),
    path("test/api/new/", views.test_new, name="test_new"),
    path("test/api/kill/", views.test_kill, name="test_kill"),
    path("test/api/send-elements/", views.test_send_elements, name="test_send_elements"),
    path("test/api/send-signals/", views.test_send_signals, name="test_send_signals"),
    path("test/api/status/", views.test_status, name="test_status"),
    path("test/sse/<str:channel>/", views.test_sse, name="test_sse"),
]
