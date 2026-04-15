from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.responses import success_response
from apps.core.services import DashboardService


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = DashboardService.get_summary(request.user)
        return success_response(data=data)

