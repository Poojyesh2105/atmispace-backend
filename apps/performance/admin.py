from django.contrib import admin

from apps.performance.models import PerformanceCycle, PerformanceGoal, PerformanceReview, RatingScale

admin.site.register(RatingScale)
admin.site.register(PerformanceCycle)
admin.site.register(PerformanceGoal)
admin.site.register(PerformanceReview)

