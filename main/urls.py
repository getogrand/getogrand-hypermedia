from django.urls import path

from .views import index, sentry_tunnel

app_name = "main"
urlpatterns = [
    path("sentry_tunnel", sentry_tunnel, name="sentry_tunnel"),
    path("", index, name="index"),
]
