from django.contrib import admin

from apps.announcements.models import Announcement, AnnouncementAcknowledgement

admin.site.register(Announcement)
admin.site.register(AnnouncementAcknowledgement)

