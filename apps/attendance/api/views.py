from django.http import HttpResponse
from rest_framework import decorators, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.attendance.models import BiometricAttendanceEvent, BiometricDevice
from apps.attendance.selectors import AttendanceSelectors
from apps.attendance.serializers import (
    AttendanceActionSerializer,
    AttendanceRegularizationApplySerializer,
    AttendanceRegularizationDecisionSerializer,
    AttendanceRegularizationSerializer,
    AttendanceSerializer,
    BiometricAttendanceEventSerializer,
    BiometricAttendanceIngestSerializer,
    BiometricDeviceSerializer,
)
from apps.attendance.services.attendance_service import AttendanceService
from apps.attendance.services.biometric_service import BiometricAttendanceService
from apps.attendance.services.regularization_service import AttendanceRegularizationService
from apps.core.permissions import IsAdminOrHR, IsManagerOrAbove
from apps.core.responses import success_response
from apps.core.services import OrganizationService


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


class BiometricDeviceViewSet(viewsets.ModelViewSet):
    serializer_class = BiometricDeviceSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    def get_queryset(self):
        return AttendanceSelectors.get_biometric_device_queryset(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = serializer.save(organization=OrganizationService.resolve_for_actor(request.user))
        return success_response(
            data=self.get_serializer(device).data,
            message="Biometric device added successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    def update(self, request, *args, **kwargs):
        device = self.get_object()
        serializer = self.get_serializer(device, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(data=self.get_serializer(device).data, message="Biometric device updated successfully.")

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return success_response(message="Biometric device deleted successfully.")


class BiometricAttendanceEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BiometricAttendanceEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AttendanceSelectors.get_biometric_event_queryset_for_user(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class BiometricIngestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BiometricAttendanceIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = BiometricAttendanceService.ingest_event(serializer.validated_data)
        return success_response(
            data=BiometricAttendanceEventSerializer(event).data,
            message=event.message or "Biometric attendance event received.",
            status_code=status.HTTP_202_ACCEPTED,
        )

class BioMaxBridgeIngestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if request.headers.get('X-BioMax-Bridge') != '1':
            return HttpResponse(status=403)

        data = request.data
        try:
            event, created = BiometricAttendanceService.ingest_event_idempotent({
                "device_id": data.get("device_id", "BIOMAX"),
                "employee_code": str(data.get("employee_code", "")),
                "punch_time": data.get("punch_time"),
                "punch_type": data.get("punch_type", "AUTO"),
                "verify_mode": data.get("verify_mode", "UNKNOWN"),
                "raw_payload": data.get("raw_payload", {}),
            })
            return success_response(
                data={"event_id": event.id, "created": created},
                message="Punch received.",
            )
        except Exception as e:
            return success_response(data={}, message=str(e))
        

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
