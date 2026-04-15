from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsAdminOrHR
from apps.core.responses import success_response
from apps.employees.models import Employee
from apps.holidays.models import EmployeeHolidayAssignment, Holiday, HolidayCalendar
from apps.holidays.serializers import EmployeeHolidayAssignmentSerializer, HolidayCalendarSerializer, HolidaySerializer
from apps.holidays.services.holiday_service import HolidayService


class HolidayCalendarViewSet(viewsets.ModelViewSet):
    serializer_class = HolidayCalendarSerializer
    queryset = HolidayCalendar.objects.prefetch_related("holidays").all()
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsAdminOrHR()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        calendar = HolidayService.create_calendar(serializer.validated_data)
        return success_response(data=self.get_serializer(calendar).data, message="Holiday calendar created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        calendar = HolidayService.update_calendar(self.get_object(), serializer.validated_data)
        return success_response(data=self.get_serializer(calendar).data, message="Holiday calendar updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class HolidayViewSet(viewsets.ModelViewSet):
    serializer_class = HolidaySerializer
    queryset = Holiday.objects.select_related("calendar").all()
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsAdminOrHR()]
        return super().get_permissions()

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class EmployeeHolidayAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeHolidayAssignmentSerializer
    queryset = EmployeeHolidayAssignment.objects.select_related("employee__user", "calendar").all()
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = Employee.objects.get(pk=serializer.validated_data["employee"].pk)
        assignment = HolidayService.assign_calendar(employee, serializer.validated_data["calendar"])
        return success_response(data=self.get_serializer(assignment).data, message="Holiday calendar assigned.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        assignment = HolidayService.assign_calendar(serializer.validated_data["employee"], serializer.validated_data["calendar"])
        return success_response(data=self.get_serializer(assignment).data, message="Holiday calendar assignment updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)
