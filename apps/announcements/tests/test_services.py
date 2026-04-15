from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.announcements.models import Announcement
from apps.announcements.services.announcement_service import AnnouncementService


class AnnouncementServiceTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin-announcement@test.com",
            password="Admin@123",
            first_name="Admin",
            last_name="User",
            role=User.Role.ADMIN,
        )
        self.employee = User.objects.create_user(
            email="employee-announcement@test.com",
            password="Employee@123",
            first_name="Employee",
            last_name="User",
            role=User.Role.EMPLOYEE,
        )
        self.announcement = Announcement.objects.create(
            title="Policy update",
            body="Read the new policy.",
            summary="New policy released",
            created_by=self.admin,
            starts_at=timezone.now(),
            requires_acknowledgement=True,
        )

    def test_acknowledge_creates_acknowledgement(self):
        acknowledgement = AnnouncementService.acknowledge(self.announcement, self.employee)
        self.assertEqual(acknowledgement.user_id, self.employee.pk)

