from apps.accounts.models import User
from apps.policy_engine.models import PolicyEvaluationLog, PolicyRule


class PolicyRuleSelectors:
    @staticmethod
    def get_rule_queryset_for_user(user):
        queryset = PolicyRule.objects.for_current_org(user)
        if user.role in {User.Role.HR, User.Role.ADMIN, User.Role.MANAGER, User.Role.ACCOUNTS}:
            return queryset
        return queryset.filter(is_active=True)

    @staticmethod
    def get_log_queryset_for_user(user):
        queryset = PolicyEvaluationLog.objects.for_current_org(user).select_related("rule", "actor", "content_type")
        if user.role in {User.Role.HR, User.Role.ADMIN, User.Role.ACCOUNTS}:
            return queryset
        if user.role == User.Role.MANAGER:
            return queryset.filter(module__in=[PolicyRule.Module.ATTENDANCE, PolicyRule.Module.LEAVE, PolicyRule.Module.LIFECYCLE])
        return queryset.none()
