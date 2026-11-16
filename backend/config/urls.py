from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    """Used by the hosting platform to check that the service is alive."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/", include("accounts.urls")),
    path("api/", include("attendance.urls")),
]
