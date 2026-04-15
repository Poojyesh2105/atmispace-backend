from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.responses import success_response
from apps.policy_engine.permissions import CanManagePolicyRules
from apps.policy_engine.selectors.policy_rule_selectors import PolicyRuleSelectors
from apps.policy_engine.serializers import PolicyEvaluationLogSerializer, PolicyRuleSerializer
from apps.policy_engine.services.policy_rule_service import PolicyRuleService


class PolicyRuleViewSet(viewsets.ModelViewSet):
    serializer_class = PolicyRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PolicyRuleSelectors.get_rule_queryset_for_user(self.request.user)

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), CanManagePolicyRules()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = PolicyRuleService.create_rule(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(rule).data, message="Policy rule created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        rule = PolicyRuleService.update_rule(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(rule).data, message="Policy rule updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class PolicyEvaluationLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PolicyEvaluationLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = PolicyRuleSelectors.get_log_queryset_for_user(self.request.user)
        module = self.request.query_params.get("module")
        if module:
            queryset = queryset.filter(module=module)
        return queryset

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

