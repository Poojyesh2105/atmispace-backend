from rest_framework import decorators, status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.responses import success_response
from apps.helpdesk.permissions import CanManageHelpdeskCategories
from apps.helpdesk.selectors.helpdesk_selectors import HelpdeskSelectors
from apps.helpdesk.serializers import HelpdeskCategorySerializer, HelpdeskCommentCreateSerializer, HelpdeskCommentSerializer, HelpdeskTicketSerializer
from apps.helpdesk.services.helpdesk_service import HelpdeskCategoryService, HelpdeskService


class HelpdeskCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = HelpdeskCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return HelpdeskSelectors.get_category_queryset()

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), CanManageHelpdeskCategories()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = HelpdeskCategoryService.create_category(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(category).data, message="Helpdesk category created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        category = HelpdeskCategoryService.update_category(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(category).data, message="Helpdesk category updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class HelpdeskTicketViewSet(viewsets.ModelViewSet):
    serializer_class = HelpdeskTicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = HelpdeskSelectors.get_ticket_queryset_for_user(self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = HelpdeskService.create_ticket(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(ticket).data, message="Helpdesk ticket created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        ticket = HelpdeskService.update_ticket(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(ticket).data, message="Helpdesk ticket updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    @decorators.action(detail=True, methods=["post"])
    def add_comment(self, request, pk=None):
        serializer = HelpdeskCommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = HelpdeskService.add_comment(
            self.get_object(),
            request.user,
            serializer.validated_data["message"],
            serializer.validated_data["is_internal"],
        )
        return success_response(data=HelpdeskCommentSerializer(comment).data, message="Comment added.")

    @decorators.action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        ticket = HelpdeskService.resolve(self.get_object(), request.user, request.data.get("resolution_notes", ""))
        return success_response(data=self.get_serializer(ticket).data, message="Ticket resolved.")

    @decorators.action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        ticket = HelpdeskService.close(self.get_object(), request.user)
        return success_response(data=self.get_serializer(ticket).data, message="Ticket closed.")

