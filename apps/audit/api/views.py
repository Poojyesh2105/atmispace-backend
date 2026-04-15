from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.core.permissions import IsAdminOrHR
from apps.core.responses import success_response


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("actor").all()
        entity_type = self.request.query_params.get("entity_type")
        entity_id = self.request.query_params.get("entity_id")
        action = self.request.query_params.get("action")
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        if entity_id:
            queryset = queryset.filter(entity_id=entity_id)
        if action:
            queryset = queryset.filter(action=action)
        return queryset

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)
