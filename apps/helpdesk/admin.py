from django.contrib import admin

from apps.helpdesk.models import HelpdeskCategory, HelpdeskComment, HelpdeskTicket

admin.site.register(HelpdeskCategory)
admin.site.register(HelpdeskTicket)
admin.site.register(HelpdeskComment)

