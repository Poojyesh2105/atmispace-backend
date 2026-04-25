from datetime import date
from decimal import Decimal
from typing import Optional

from django.db import transaction

from apps.employees.models import Employee
from apps.leave_management.models import LeaveBalance, LeaveCarryForwardLog, LeavePolicy
from apps.leave_management.services.leave_service import LeavePolicyService


def _subtract_one_month(d: date) -> date:
    """Return the first day of the month preceding the given date's month."""
    if d.month == 1:
        return d.replace(year=d.year - 1, month=12, day=1)
    return d.replace(month=d.month - 1, day=1)


def _previous_year_start(d: date) -> date:
    """Return the first day of the previous carry-forward year."""
    return d.replace(year=d.year - 1, month=1, day=1)


class LeaveCarryForwardService:
    @staticmethod
    @transaction.atomic
    def process_carry_forward(target_month: date, organization=None) -> int:
        """
        Process leave carry-forward for employees in the given month.

        Args:
            target_month: The month RECEIVING the carry-forward
                          (e.g. February receives January's unused days).
            organization: If provided, only process employees belonging to this
                          organization.  None = process all orgs (legacy behaviour).

        Returns:
            Count of employees processed.
        """
        policy = LeavePolicyService.get_policy(organization=organization)

        if not policy.enable_carry_forward:
            return 0

        eligible_leave_types = policy.carry_forward_leave_types or []
        if not eligible_leave_types:
            return 0

        max_carry = policy.max_carry_forward_days
        target_first = target_month.replace(day=1)
        if policy.carry_forward_frequency == LeavePolicy.CarryForwardFrequency.YEARLY:
            target_first = target_first.replace(month=1, day=1)
            from_first = _previous_year_start(target_first)
        else:
            from_first = _subtract_one_month(target_first)

        employee_qs = Employee.objects.filter(is_active=True).select_related("user")
        if organization is not None:
            employee_qs = employee_qs.filter(organization=organization)

        count = 0

        for employee in employee_qs:
            employee_processed = False
            for leave_type in eligible_leave_types:
                already_processed = LeaveCarryForwardLog.objects.filter(
                    employee=employee,
                    leave_type=leave_type,
                    from_month=from_first,
                ).exists()
                if already_processed:
                    continue

                try:
                    balance = LeaveBalance.objects.get(employee=employee, leave_type=leave_type)
                except LeaveBalance.DoesNotExist:
                    continue

                unused = max(balance.allocated_days - balance.used_days, Decimal("0"))
                carried = min(unused, max_carry)

                balance.allocated_days += carried
                balance.save(update_fields=["allocated_days"])

                LeaveCarryForwardLog.objects.create(
                    employee=employee,
                    leave_type=leave_type,
                    from_month=from_first,
                    to_month=target_first,
                    unused_days=unused,
                    carried_forward_days=carried,
                )
                employee_processed = True

            if employee_processed:
                count += 1

        return count
