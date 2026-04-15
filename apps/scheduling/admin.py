from django.contrib import admin

from apps.scheduling.models import ScheduleConflict, ShiftRosterEntry, ShiftRotationRule

admin.site.register(ShiftRotationRule)
admin.site.register(ShiftRosterEntry)
admin.site.register(ScheduleConflict)

