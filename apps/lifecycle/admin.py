from django.contrib import admin

from apps.lifecycle.models import EmployeeChangeRequest, EmployeeOnboarding, EmployeeOnboardingTask, OffboardingCase, OffboardingTask, OnboardingPlan, OnboardingTaskTemplate

admin.site.register(OnboardingPlan)
admin.site.register(OnboardingTaskTemplate)
admin.site.register(EmployeeOnboarding)
admin.site.register(EmployeeOnboardingTask)
admin.site.register(OffboardingCase)
admin.site.register(OffboardingTask)
admin.site.register(EmployeeChangeRequest)

