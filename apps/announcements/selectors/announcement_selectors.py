from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.announcements.models import Announcement


class AnnouncementSelectors:
    @staticmethod
    def get_queryset_for_user(user):
        now = timezone.now()
        queryset = Announcement.objects.for_current_org(user).select_related("created_by", "department", "target_user").prefetch_related("acknowledgements")

        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return queryset

        employee = getattr(user, "employee_profile", None)
        filters = Q(audience_type=Announcement.AudienceType.ALL)
        filters |= Q(audience_type=Announcement.AudienceType.ROLE, role=user.role)
        if employee and employee.department_id:
            filters |= Q(audience_type=Announcement.AudienceType.DEPARTMENT, department_id=employee.department_id)
        filters |= Q(audience_type=Announcement.AudienceType.INDIVIDUAL, target_user=user)
        return queryset.filter(
            filters,
            is_published=True,
            starts_at__lte=now,
        ).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now)).distinct()

    @staticmethod
    def get_dashboard_queryset_for_user(user):
        return AnnouncementSelectors.get_queryset_for_user(user).filter(show_on_dashboard=True)
