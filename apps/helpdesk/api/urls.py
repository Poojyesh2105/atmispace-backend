from rest_framework.routers import DefaultRouter

from .views import HelpdeskCategoryViewSet, HelpdeskTicketViewSet

router = DefaultRouter()
router.register("categories", HelpdeskCategoryViewSet, basename="helpdesk-category")
router.register("tickets", HelpdeskTicketViewSet, basename="helpdesk-ticket")

urlpatterns = router.urls

