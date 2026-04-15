from django.contrib import admin

from apps.policy_engine.models import PolicyEvaluationLog, PolicyRule

admin.site.register(PolicyRule)
admin.site.register(PolicyEvaluationLog)

