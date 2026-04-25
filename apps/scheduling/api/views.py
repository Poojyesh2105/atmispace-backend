from rest_framework import decorators, status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.responses import success_response
from apps.scheduling.permissions import IsSchedulingManager
from apps.scheduling.selectors.scheduling_selectors import SchedulingSelectors
from apps.scheduling.serializers import BulkShiftAssignmentSerializer, ScheduleConflictSerializer, ShiftRosterEntrySerializer, ShiftRotationRuleSerializer
from apps.scheduling.services.scheduling_service import SchedulingService, ShiftRotationRuleService


class ShiftRotationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = ShiftRotationRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SchedulingSelectors.get_rotation_rule_queryset(self.request.user)

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "apply"}:
            return [IsAuthenticated(), IsSchedulingManager()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = ShiftRotationRuleService.create_rule(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(rule).data, message="Shift rotation rule created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        rule = ShiftRotationRuleService.update_rule(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(rule).data, message="Shift rotation rule updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    @decorators.action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        serializer = BulkShiftAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entries = SchedulingService.apply_rotation(
            self.get_object(),
            serializer.validated_data["employees"],
            serializer.validated_data["start_date"],
            serializer.validated_data["end_date"],
            request.user,
        )
        return success_response(data=ShiftRosterEntrySerializer(entries, many=True).data, message="Rotation rule applied.")


class ShiftRosterEntryViewSet(viewsets.ModelViewSet):
    serializer_class = ShiftRosterEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = SchedulingSelectors.get_roster_queryset_for_user(self.request.user)
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(roster_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(roster_date__lte=date_to)
        return queryset

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "bulk_assign"}:
            return [IsAuthenticated(), IsSchedulingManager()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = SchedulingService.assign_shift(
            serializer.validated_data["employee"],
            serializer.validated_data["roster_date"],
            serializer.validated_data["shift_template"],
            request.user,
            notes=serializer.validated_data.get("notes", ""),
        )
        return success_response(data=self.get_serializer(entry).data, message="Roster entry saved.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        entry = SchedulingService.assign_shift(
            serializer.validated_data.get("employee", self.get_object().employee),
            serializer.validated_data.get("roster_date", self.get_object().roster_date),
            serializer.validated_data.get("shift_template", self.get_object().shift_template),
            request.user,
            source=self.get_object().source,
            notes=serializer.validated_data.get("notes", self.get_object().notes),
        )
        return success_response(data=self.get_serializer(entry).data, message="Roster entry updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    @decorators.action(detail=False, methods=["post"])
    def bulk_assign(self, request):
        serializer = BulkShiftAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entries = SchedulingService.bulk_assign(
            serializer.validated_data["employees"],
            serializer.validated_data["shift_template"],
            serializer.validated_data["start_date"],
            serializer.validated_data["end_date"],
            request.user,
        )
        return success_response(data=ShiftRosterEntrySerializer(entries, many=True).data, message="Bulk shift assignment completed.")


class ScheduleConflictViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScheduleConflictSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = SchedulingSelectors.get_conflict_queryset_for_user(self.request.user)
        is_resolved = self.request.query_params.get("is_resolved")
        if is_resolved:
            queryset = queryset.filter(is_resolved=is_resolved.lower() == "true")
        return queryset

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)
