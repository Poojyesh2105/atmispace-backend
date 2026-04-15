from django.urls import path

from .views import AttendanceReportView, EmployeeReportView, LeaveReportView

urlpatterns = [
    path("attendance/", AttendanceReportView.as_view(), name="attendance-report"),
    path("leave/", LeaveReportView.as_view(), name="leave-report"),
    path("employees/", EmployeeReportView.as_view(), name="employee-report"),
]
