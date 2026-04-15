from rest_framework import decorators, status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.responses import success_response
from apps.documents.permissions import IsDocumentAdmin
from apps.documents.selectors.document_selectors import DocumentSelectors
from apps.documents.serializers import (
    DocumentTypeSerializer,
    DocumentVerificationSerializer,
    EmployeeDocumentSerializer,
    MandatoryDocumentRuleSerializer,
)
from apps.documents.services.document_service import DocumentTypeService, EmployeeDocumentService, MandatoryDocumentRuleService


class DocumentTypeViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DocumentSelectors.get_document_type_queryset()

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsDocumentAdmin()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_type = DocumentTypeService.create_type(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(document_type).data, message="Document type created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        document_type = DocumentTypeService.update_type(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(document_type).data, message="Document type updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class MandatoryDocumentRuleViewSet(viewsets.ModelViewSet):
    serializer_class = MandatoryDocumentRuleSerializer
    permission_classes = [IsAuthenticated, IsDocumentAdmin]

    def get_queryset(self):
        return DocumentSelectors.get_mandatory_rule_queryset()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = MandatoryDocumentRuleService.create_rule(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(rule).data, message="Mandatory document rule created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        rule = MandatoryDocumentRuleService.update_rule(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(rule).data, message="Mandatory document rule updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class EmployeeDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = DocumentSelectors.get_document_queryset_for_user(self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = EmployeeDocumentService.create_document(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(document).data, message="Document uploaded.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        document = EmployeeDocumentService.update_document(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(document).data, message="Document updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    @decorators.action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        serializer = DocumentVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = EmployeeDocumentService.verify_document(request.user, self.get_object(), serializer.validated_data.get("remarks", ""))
        return success_response(data=self.get_serializer(document).data, message="Document verified.")

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = DocumentVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = EmployeeDocumentService.reject_document(request.user, self.get_object(), serializer.validated_data.get("remarks", ""))
        return success_response(data=self.get_serializer(document).data, message="Document rejected.")

