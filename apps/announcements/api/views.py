from rest_framework import decorators, status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.announcements.permissions import CanManageAnnouncements
from apps.announcements.selectors.announcement_selectors import AnnouncementSelectors
from apps.announcements.serializers import AnnouncementAcknowledgementSerializer, AnnouncementSerializer
from apps.announcements.services.announcement_service import AnnouncementService
from apps.core.responses import success_response


class AnnouncementViewSet(viewsets.ModelViewSet):
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = AnnouncementSelectors.get_queryset_for_user(self.request.user)
        dashboard = self.request.query_params.get("dashboard")
        if dashboard == "true":
            queryset = queryset.filter(show_on_dashboard=True)
        return queryset

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "publish"}:
            return [IsAuthenticated(), CanManageAnnouncements()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = AnnouncementService.create(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(announcement, context={"request": request}).data, message="Announcement created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        announcement = AnnouncementService.update(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(announcement, context={"request": request}).data, message="Announcement updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object(), context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        announcement = AnnouncementService.publish(self.get_object(), request.user)
        return success_response(data=self.get_serializer(announcement, context={"request": request}).data, message="Announcement published.")

    @decorators.action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        acknowledgement = AnnouncementService.acknowledge(self.get_object(), request.user)
        return success_response(data=AnnouncementAcknowledgementSerializer(acknowledgement).data, message="Announcement acknowledged.")

