from rest_framework import decorators, status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.responses import success_response
from apps.performance.permissions import IsPerformanceAdmin
from apps.performance.selectors.performance_selectors import PerformanceSelectors
from apps.performance.serializers import (
    HRReviewSubmissionSerializer,
    ManagerReviewSubmissionSerializer,
    PerformanceCycleSerializer,
    PerformanceGoalSerializer,
    PerformanceReviewSerializer,
    RatingScaleSerializer,
    SelfReviewSubmissionSerializer,
)
from apps.performance.services.performance_service import (
    PerformanceCycleService,
    PerformanceGoalService,
    PerformanceReviewService,
    RatingScaleService,
)


class RatingScaleViewSet(viewsets.ModelViewSet):
    serializer_class = RatingScaleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PerformanceSelectors.get_rating_scale_queryset()

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsPerformanceAdmin()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scale = RatingScaleService.create_scale(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(scale).data, message="Rating scale created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        scale = RatingScaleService.update_scale(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(scale).data, message="Rating scale updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class PerformanceCycleViewSet(viewsets.ModelViewSet):
    serializer_class = PerformanceCycleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PerformanceSelectors.get_cycle_queryset()

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsPerformanceAdmin()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cycle = PerformanceCycleService.create_cycle(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(cycle).data, message="Performance cycle created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        cycle = PerformanceCycleService.update_cycle(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(cycle).data, message="Performance cycle updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class PerformanceGoalViewSet(viewsets.ModelViewSet):
    serializer_class = PerformanceGoalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PerformanceSelectors.get_goal_queryset_for_user(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        goal = PerformanceGoalService.create_goal(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(goal).data, message="Performance goal created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        goal = PerformanceGoalService.update_goal(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(goal).data, message="Performance goal updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class PerformanceReviewViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PerformanceReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = PerformanceSelectors.get_review_queryset_for_user(self.request.user)
        inbox = self.request.query_params.get("inbox")
        cycle_id = self.request.query_params.get("cycle")
        if inbox == "true":
            return PerformanceSelectors.get_review_inbox_for_user(self.request.user)
        if cycle_id:
            queryset = queryset.filter(cycle_id=cycle_id)
        return queryset

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    @decorators.action(detail=True, methods=["post"])
    def submit_self_review(self, request, pk=None):
        serializer = SelfReviewSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = PerformanceReviewService.submit_self_review(request.user, self.get_object(), serializer.validated_data)
        return success_response(data=self.get_serializer(review).data, message="Self review submitted.")

    @decorators.action(detail=True, methods=["post"])
    def submit_manager_review(self, request, pk=None):
        serializer = ManagerReviewSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = PerformanceReviewService.submit_manager_review(request.user, self.get_object(), serializer.validated_data)
        return success_response(data=self.get_serializer(review).data, message="Manager review submitted.")

    @decorators.action(detail=True, methods=["post"])
    def submit_hr_review(self, request, pk=None):
        serializer = HRReviewSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = PerformanceReviewService.submit_hr_review(request.user, self.get_object(), serializer.validated_data)
        return success_response(data=self.get_serializer(review).data, message="Final review submitted.")

