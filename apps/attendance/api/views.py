from rest_framework import decorators, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.attendance.serializers import (
    AttendanceActionSerializer,
    AttendanceRegularizationApplySerializer,
    AttendanceRegularizationDecisionSerializer,
    AttendanceRegularizationSerializer,
    AttendanceSerializer,
)
from apps.attendance.services.attendance_service import AttendanceService
from apps.attendance.services.regularization_service import AttendanceRegularizationService
from apps.core.permissions import IsManagerOrAbove
from apps.core.responses import success_response


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = AttendanceService.get_queryset_for_user(self.request.user)
        mine = self.request.query_params.get("mine")
        employee_id = self.request.query_params.get("employee")
        attendance_date = self.request.query_params.get("attendance_date")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if mine == "true":
            employee = getattr(self.request.user, "employee_profile", None)
            queryset = queryset.filter(employee=employee) if employee else queryset.none()
        elif employee_id and self.request.user.role in {"HR", "ACCOUNTS", "ADMIN", "MANAGER"}:
            queryset = queryset.filter(employee_id=employee_id)
        if attendance_date:
            queryset = queryset.filter(attendance_date=attendance_date)
        if date_from:
            queryset = queryset.filter(attendance_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(attendance_date__lte=date_to)
        return queryset

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return success_response(data=self.get_serializer(instance).data)

    @decorators.action(detail=False, methods=["post"], url_path="check-in")
    def check_in(self, request):
        serializer = AttendanceActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attendance = AttendanceService.check_in(request.user, **serializer.validated_data)
        return success_response(data=self.get_serializer(attendance).data, message="Check-in successful.")

    @decorators.action(detail=False, methods=["post"], url_path="check-out")
    def check_out(self, request):
        serializer = AttendanceActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attendance = AttendanceService.check_out(request.user, notes=serializer.validated_data.get("notes", ""))
        return success_response(data=self.get_serializer(attendance).data, message="Check-out successful.")

    @decorators.action(detail=False, methods=["post"], url_path="start-break")
    def start_break(self, request):
        serializer = AttendanceActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attendance = AttendanceService.start_break(request.user, notes=serializer.validated_data.get("notes", ""))
        return success_response(data=self.get_serializer(attendance).data, message="Break started.")

    @decorators.action(detail=False, methods=["post"], url_path="end-break")
    def end_break(self, request):
        serializer = AttendanceActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attendance = AttendanceService.end_break(request.user, notes=serializer.validated_data.get("notes", ""))
        return success_response(data=self.get_serializer(attendance).data, message="Break ended.")


class AttendanceRegularizationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AttendanceRegularizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = AttendanceRegularizationService.get_queryset_for_user(self.request.user)
        mine = self.request.query_params.get("mine")
        status_filter = self.request.query_params.get("status")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if mine == "true":
            employee = getattr(self.request.user, "employee_profile", None)
            queryset = queryset.filter(employee=employee) if employee else queryset.none()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        return queryset

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    @decorators.action(detail=False, methods=["post"], url_path="apply")
    def apply(self, request):
        serializer = AttendanceRegularizationApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        regularization = AttendanceRegularizationService.apply_regularization(request.user, serializer.validated_data)
        return success_response(
            data=self.get_serializer(regularization).data,
            message="Attendance regularization submitted successfully.",
        )

    @decorators.action(detail=True, methods=["post"], url_path="approve", permission_classes=[IsAuthenticated, IsManagerOrAbove])
    def approve(self, request, pk=None):
        serializer = AttendanceRegularizationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        regularization = AttendanceRegularizationService.approve_regularization(
            request.user,
            self.get_object(),
            approver_note=serializer.validated_data.get("approver_note", ""),
        )
        return success_response(data=self.get_serializer(regularization).data, message="Attendance regularization approved.")

    @decorators.action(detail=True, methods=["post"], url_path="reject", permission_classes=[IsAuthenticated, IsManagerOrAbove])
    def reject(self, request, pk=None):
        serializer = AttendanceRegularizationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        regularization = AttendanceRegularizationService.reject_regularization(
            request.user,
            self.get_object(),
            approver_note=serializer.validated_data.get("approver_note", ""),
        )
        return success_response(data=self.get_serializer(regularization).data, message="Attendance regularization rejected.")
