from rest_framework import decorators, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.responses import success_response
from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user).order_by("-created_at")
        unread = self.request.query_params.get("unread")
        if unread == "true":
            queryset = queryset.filter(is_read=False)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return success_response(data=self.get_serializer(queryset, many=True).data)

    @decorators.action(detail=False, methods=["get"])
    def unread_count(self, request):
        return success_response(data={"count": self.get_queryset().filter(is_read=False).count()})

    @decorators.action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read", "updated_at"])
        return success_response(data=self.get_serializer(notification).data, message="Notification marked as read.")

    @decorators.action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return success_response(message="Notifications marked as read.")
