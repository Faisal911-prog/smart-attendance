from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import CourseViewSet, LectureSessionViewSet, MyAttendanceView, OverviewView, ScanView

router = SimpleRouter()
router.register("courses", CourseViewSet, basename="course")
router.register("sessions", LectureSessionViewSet, basename="session")

urlpatterns = [
    path("attendance/scan/", ScanView.as_view(), name="scan"),
    path("attendance/my/", MyAttendanceView.as_view(), name="my-attendance"),
    path("analytics/overview/", OverviewView.as_view(), name="analytics-overview"),
    path("", include(router.urls)),
]
