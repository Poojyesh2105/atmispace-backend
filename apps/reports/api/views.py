import csv

from django.http import HttpResponse
from rest_framework import exceptions
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.pagination import StandardResultsSetPagination
from apps.core.responses import success_response
from apps.reports.serializers import AttendanceReportRowSerializer, EmployeeReportRowSerializer, LeaveReportRowSerializer
from apps.reports.services.report_service import ReportService


class BaseReportView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    report_type = ""
    serializer_class = None

    def get_queryset(self, request):
        raise NotImplementedError

    def _build_export_response(self, serializer):
        report_name = f"{self.report_type}-report.csv"
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{report_name}"'

        writer = csv.writer(response)
        columns = ReportService.get_report_columns(self.report_type)
        writer.writerow([column["label"] for column in columns])
        for row in serializer.data:
            writer.writerow([row.get(column["key"], "") for column in columns])
        return response

    def get(self, request):
        queryset = self.get_queryset(request)
        export_format = request.query_params.get("export")
        if export_format == "csv":
            if request.user.role not in {"MANAGER", "HR", "ACCOUNTS", "ADMIN"}:
                raise exceptions.PermissionDenied("You are not allowed to export this report.")
            serializer = self.serializer_class(queryset, many=True)
            return self._build_export_response(serializer)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = self.serializer_class(page, many=True)
        paginated = paginator.get_paginated_response(serializer.data).data
        paginated["data"]["columns"] = ReportService.get_report_columns(self.report_type)
        return success_response(data=paginated["data"])


class AttendanceReportView(BaseReportView):
    report_type = "attendance"
    serializer_class = AttendanceReportRowSerializer

    def get_queryset(self, request):
        return ReportService.get_attendance_queryset(request.user, request.query_params)


class LeaveReportView(BaseReportView):
    report_type = "leave"
    serializer_class = LeaveReportRowSerializer

    def get_queryset(self, request):
        return ReportService.get_leave_queryset(request.user, request.query_params)


class EmployeeReportView(BaseReportView):
    report_type = "employee"
    serializer_class = EmployeeReportRowSerializer

    def get_queryset(self, request):
        return ReportService.get_employee_queryset(request.user, request.query_params)
