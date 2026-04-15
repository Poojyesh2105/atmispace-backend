from rest_framework.routers import DefaultRouter

from .views import DocumentTypeViewSet, EmployeeDocumentViewSet, MandatoryDocumentRuleViewSet

router = DefaultRouter()
router.register("types", DocumentTypeViewSet, basename="document-type")
router.register("rules", MandatoryDocumentRuleViewSet, basename="mandatory-document-rule")
router.register("employee-documents", EmployeeDocumentViewSet, basename="employee-document")

urlpatterns = router.urls

