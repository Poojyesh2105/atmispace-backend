from apps.holidays.models import EmployeeHolidayAssignment, Holiday, HolidayCalendar


class HolidayService:
    @staticmethod
    def get_calendar_for_employee(employee):
        assignment = getattr(employee, "holiday_assignment", None)
        if assignment:
            return assignment.calendar
        return HolidayCalendar.objects.filter(is_default=True).order_by("id").first()

    @staticmethod
    def get_holiday_dates_for_employee(employee, start_date, end_date):
        calendar = HolidayService.get_calendar_for_employee(employee)
        if not calendar:
            return set()
        return set(
            Holiday.objects.filter(calendar=calendar, date__gte=start_date, date__lte=end_date).values_list("date", flat=True)
        )

    @staticmethod
    def create_calendar(validated_data):
        if validated_data.get("is_default"):
            HolidayCalendar.objects.filter(is_default=True).update(is_default=False)
        return HolidayCalendar.objects.create(**validated_data)

    @staticmethod
    def update_calendar(instance, validated_data):
        if validated_data.get("is_default"):
            HolidayCalendar.objects.exclude(pk=instance.pk).filter(is_default=True).update(is_default=False)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @staticmethod
    def assign_calendar(employee, calendar):
        assignment, _ = EmployeeHolidayAssignment.objects.update_or_create(employee=employee, defaults={"calendar": calendar})
        return assignment
